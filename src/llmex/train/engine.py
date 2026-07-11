"""결정적 단일 장치 사전학습 엔진."""
# pyright: reportUnknownMemberType=false

import json
import math
import os
import random
import signal
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

from llmex.config import TrainingConfig
from llmex.data.io import write_json
from llmex.errors import ConfigError, IntegrityError
from llmex.fingerprint import fingerprint
from llmex.model import CausalLM, GenerationConfig
from llmex.train.checkpoint import (
    load_checkpoint,
    restore_rng_state,
    rng_state,
    save_checkpoint,
)
from llmex.train.data import DeterministicBatchSampler, TokenShardDataset, batch
from llmex.train.optim import learning_rate, parameter_groups


def _device(name: str) -> torch.device:
    if name == "auto":
        name = (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
    if name == "cuda" and not torch.cuda.is_available():
        raise ConfigError("CUDA를 사용할 수 없습니다")
    if name == "mps" and not torch.backends.mps.is_available():
        raise ConfigError("MPS를 사용할 수 없습니다")
    return torch.device(name)


def _precision(requested: str, device: torch.device) -> tuple[str, torch.dtype | None, bool]:
    if requested == "auto":
        if device.type == "cuda" and torch.cuda.is_bf16_supported():
            requested = "bf16"
        elif device.type == "cuda":
            requested = "fp16"
        else:
            requested = "fp32"
    if requested == "bf16":
        supported = device.type == "cuda" and torch.cuda.is_bf16_supported()
        supported |= device.type == "cpu"
        if not supported:
            raise ConfigError("선택한 장치가 bf16 autocast를 지원하지 않습니다")
        return requested, torch.bfloat16, False
    if requested == "fp16":
        if device.type != "cuda":
            raise ConfigError("fp16 학습은 CUDA에서만 지원합니다")
        return requested, torch.float16, True
    return "fp32", None, False


def _seed_everything(seed: int, deterministic: bool) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(deterministic)
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.benchmark = False


class Trainer:
    """학습, 검증, checkpoint와 중단 재개를 한 상태 기계로 관리한다."""

    def __init__(self, config: TrainingConfig) -> None:
        self.config = config
        _seed_everything(config.seed, config.deterministic)
        self.device = _device(config.device)
        self.precision, self.autocast_dtype, use_scaler = _precision(config.precision, self.device)
        manifest = json.loads(config.shards_manifest.read_text(encoding="utf-8"))
        self.fingerprints = {
            "config": fingerprint(config.model_dump(mode="json")),
            "corpus": fingerprint(manifest["corpus"]),
            "tokenizer": str(manifest["tokenizer_fingerprint"]),
            "model": fingerprint(config.model.model_dump(mode="json")),
            "shards": str(manifest["fingerprint"]),
        }
        if (
            int(manifest.get("splits", {}).get("train", {}).get("tokens", 0))
            <= config.sequence_length
        ):
            raise IntegrityError("train token 수가 sequence_length보다 작습니다")
        self.train_data = TokenShardDataset(config.shards_manifest, "train", config.sequence_length)
        self.validation_data = TokenShardDataset(
            config.shards_manifest, "validation", config.sequence_length
        )
        self.sampler = DeterministicBatchSampler(
            self.train_data.window_count, config.micro_batch_size, config.seed
        )
        self.validation_sampler = DeterministicBatchSampler(
            self.validation_data.window_count, config.micro_batch_size, config.seed + 1_000_003
        )
        self.model = CausalLM(config.model).to(self.device)
        opt = config.optimizer
        self.optimizer = torch.optim.AdamW(
            parameter_groups(self.model, opt.weight_decay),
            lr=opt.learning_rate,
            betas=(opt.beta1, opt.beta2),
            eps=opt.eps,
        )
        self.scaler = torch.amp.GradScaler("cuda", enabled=use_scaler)
        self.step = 0
        self.best_validation_loss = math.inf
        self.terminate_requested = False
        self.last_loss: float | None = None
        self.accumulated_wall_seconds = 0.0
        self._session_started: float | None = None
        self.run_dir = config.run_dir
        self.checkpoint_dir = self.run_dir / "checkpoints"
        self.metrics_path = self.run_dir / "metrics.jsonl"

    def _autocast(self) -> Any:
        if self.autocast_dtype is None:
            return nullcontext()
        return torch.autocast(self.device.type, dtype=self.autocast_dtype)

    def _checkpoint_payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "step": self.step,
            "best_validation_loss": self.best_validation_loss,
            "fingerprints": self.fingerprints,
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "scheduler": {"step": self.step},
            "scaler": self.scaler.state_dict(),
            "sampler": self.sampler.state_dict(),
            "validation_sampler": self.validation_sampler.state_dict(),
            "rng": rng_state(),
            "precision": self.precision,
            "accumulated_wall_seconds": self.accumulated_wall_seconds
            + (
                time.perf_counter() - self._session_started
                if self._session_started is not None
                else 0.0
            ),
        }

    def save(self, *, best: bool = False) -> Path:
        return save_checkpoint(
            self.checkpoint_dir, self._checkpoint_payload(), step=self.step, best=best
        )

    def resume(self, path: Path | None = None) -> None:
        checkpoint = load_checkpoint(path or self.checkpoint_dir / "latest.pt", self.fingerprints)
        self.model.load_state_dict(checkpoint["model"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.scaler.load_state_dict(checkpoint["scaler"])
        self.sampler.load_state_dict(checkpoint["sampler"])
        self.validation_sampler.load_state_dict(checkpoint["validation_sampler"])
        self.step = int(checkpoint["step"])
        self.best_validation_loss = float(checkpoint.get("best_validation_loss", math.inf))
        self.accumulated_wall_seconds = float(checkpoint.get("accumulated_wall_seconds", 0.0))
        if checkpoint["scheduler"] != {"step": self.step}:
            raise IntegrityError("scheduler 상태가 checkpoint step과 다릅니다")
        restore_rng_state(checkpoint["rng"])

    def _metric(self, event: dict[str, object]) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self.metrics_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def validate(self) -> float:
        was_training = self.model.training
        self.model.eval()
        losses: list[float] = []
        with torch.no_grad():
            for _ in range(self.config.validation_batches):
                tokens = batch(self.validation_data, self.validation_sampler).to(self.device)
                with self._autocast():
                    loss = self.model(tokens, targets=tokens).loss
                if loss is None or not bool(torch.isfinite(loss)):
                    raise IntegrityError(f"검증 loss가 유한하지 않습니다: step={self.step}")
                losses.append(float(loss))
        self.model.train(was_training)
        return sum(losses) / len(losses)

    def _on_sigterm(self, _signum: int, _frame: object) -> None:
        self.terminate_requested = True

    def run(self) -> dict[str, object]:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.run_dir / "resolved-config.json", self.config.model_dump(mode="json"))
        write_json(self.run_dir / "fingerprints.json", self.fingerprints)
        previous = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, self._on_sigterm)
        started = time.perf_counter()
        self._session_started = started
        session_start_step = self.step
        try:
            self.model.train()
            while self.step < self.config.max_steps:
                self.optimizer.zero_grad(set_to_none=True)
                total_loss = 0.0
                for _ in range(self.config.gradient_accumulation_steps):
                    tokens = batch(self.train_data, self.sampler).to(self.device)
                    with self._autocast():
                        loss = self.model(tokens, targets=tokens).loss
                        if loss is None:
                            raise IntegrityError("모델이 학습 loss를 반환하지 않았습니다")
                        scaled_loss: Tensor = loss / self.config.gradient_accumulation_steps
                    if not bool(torch.isfinite(loss)):
                        diagnostic: dict[str, object] = {
                            "step": self.step,
                            "loss": float(loss.detach()),
                            "batch": str(tokens.cpu()),
                        }
                        write_json(self.run_dir / "failure.json", diagnostic)
                        raise IntegrityError(f"학습 loss가 유한하지 않습니다: step={self.step}")
                    self.scaler.scale(scaled_loss).backward()
                    total_loss += float(loss.detach())
                lr = learning_rate(self.step, self.config.max_steps, self.config.optimizer)
                for group in self.optimizer.param_groups:
                    group["lr"] = lr
                self.scaler.unscale_(self.optimizer)
                grad_norm = torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), self.config.gradient_clip_norm
                )
                if not bool(torch.isfinite(grad_norm)):
                    write_json(
                        self.run_dir / "failure.json",
                        {"step": self.step, "gradient_norm": float(grad_norm)},
                    )
                    raise IntegrityError(f"gradient norm이 유한하지 않습니다: step={self.step}")
                self.scaler.step(self.optimizer)
                self.scaler.update()
                self.step += 1
                self.last_loss = total_loss / self.config.gradient_accumulation_steps
                if self.step % self.config.log_interval == 0:
                    elapsed = time.perf_counter() - started
                    cumulative_tokens = (
                        self.step
                        * self.config.micro_batch_size
                        * self.config.gradient_accumulation_steps
                        * (self.config.sequence_length - 1)
                    )
                    session_tokens = (
                        (self.step - session_start_step)
                        * self.config.micro_batch_size
                        * self.config.gradient_accumulation_steps
                        * (self.config.sequence_length - 1)
                    )
                    metric: dict[str, object] = {
                        "event": "train",
                        "step": self.step,
                        "loss": self.last_loss,
                        "learning_rate": lr,
                        "gradient_norm": float(grad_norm),
                        "tokens": cumulative_tokens,
                        "session_tokens": session_tokens,
                        "session_tokens_per_second": session_tokens / max(elapsed, 1e-9),
                        "tokens_per_second": cumulative_tokens
                        / max(self.accumulated_wall_seconds + elapsed, 1e-9),
                        "precision": self.precision,
                        "device": self.device.type,
                    }
                    if self.device.type == "cuda":
                        metric["peak_memory_bytes"] = torch.cuda.max_memory_allocated(self.device)
                    self._metric(metric)
                if (
                    self.step % self.config.validation_interval == 0
                    or self.step == self.config.max_steps
                ):
                    validation_loss = self.validate()
                    improved = validation_loss < self.best_validation_loss
                    self.best_validation_loss = min(self.best_validation_loss, validation_loss)
                    self._metric(
                        {
                            "event": "validation",
                            "step": self.step,
                            "loss": validation_loss,
                            "perplexity": math.exp(min(validation_loss, 80.0)),
                        }
                    )
                    prompt = self.validation_data.window(0)[
                        : min(4, self.config.sequence_length - 1)
                    ]
                    generated = self.model.generate(
                        prompt.unsqueeze(0).to(self.device),
                        GenerationConfig(
                            max_new_tokens=min(4, self.config.model.max_seq_len - len(prompt)),
                            temperature=0,
                        ),
                    )
                    self._metric(
                        {
                            "event": "생성_표본",
                            "step": self.step,
                            "prompt_token_ids": prompt.tolist(),
                            "generated_token_ids": generated[0].cpu().tolist(),
                        }
                    )
                    if improved:
                        self.save(best=True)
                if self.step % self.config.checkpoint_interval == 0:
                    self.save()
                if self.terminate_requested:
                    self.save()
                    self._metric({"event": "중단", "step": self.step, "reason": "SIGTERM"})
                    break
            self.save()
        finally:
            self.accumulated_wall_seconds += time.perf_counter() - started
            self._session_started = None
            signal.signal(signal.SIGTERM, previous)
        return {
            "step": self.step,
            "loss": self.last_loss,
            "best_validation_loss": self.best_validation_loss,
            "terminated": self.terminate_requested,
            "checkpoint": str(self.checkpoint_dir / "latest.pt"),
        }


def train(config: TrainingConfig, *, resume: Path | None = None) -> dict[str, object]:
    trainer = Trainer(config)
    if resume is not None:
        trainer.resume(resume)
    return trainer.run()
