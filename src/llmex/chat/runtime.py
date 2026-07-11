"""Assistant-only SFT trainer, 원자 재개, held-out gate와 chat 생성."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import json
import math
import os
import random
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch

from llmex.chat.data import ChatDataset, Message, load_chat_jsonl
from llmex.chat.template import render_chat, tokenize_chat
from llmex.config import SFTConfig
from llmex.data.io import write_json
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.inference.runtime import resolve_device
from llmex.model import CausalLM, GenerationConfig
from llmex.tokenizer.core import SPECIAL_IDS, load_tokenizer
from llmex.train.checkpoint import load_checkpoint, restore_rng_state, rng_state, save_checkpoint
from llmex.train.optim import learning_rate, parameter_groups


def _datasets(config: SFTConfig) -> tuple[ChatDataset, ChatDataset]:
    allowed = set(config.allowed_licenses)
    train = load_chat_jsonl(config.train_data, split="train", allowed_licenses=allowed)
    heldout = load_chat_jsonl(config.heldout_data, split="heldout", allowed_licenses=allowed)
    overlap = {item.sha256 for item in train.examples} & {item.sha256 for item in heldout.examples}
    if overlap:
        raise IntegrityError("train/heldout 대화 hash 누출을 발견했습니다")
    return train, heldout


def _fingerprints(config: SFTConfig, train: ChatDataset, heldout: ChatDataset) -> dict[str, str]:
    manifest = config.tokenizer_dir / "tokenizer-manifest.json"
    return {
        "config": fingerprint(config.model_dump(mode="json", exclude={"max_steps"})),
        "model": fingerprint(config.model.model_dump(mode="json")),
        "tokenizer": sha256_file(manifest),
        "train": train.fingerprint,
        "heldout": heldout.fingerprint,
    }


def _load_base(model: CausalLM, path: Path) -> None:
    try:
        value = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise IntegrityError("base checkpoint schema가 올바르지 않습니다")
        state = cast(dict[str, Any], value).get("model")
        if not isinstance(state, dict):
            raise IntegrityError("base checkpoint model 상태가 없습니다")
        model.load_state_dict(cast(dict[str, torch.Tensor], state), strict=True)
    except (OSError, RuntimeError, KeyError) as exc:
        raise IntegrityError(f"base checkpoint를 재사용할 수 없습니다: {exc}") from exc


def _batch(
    tokenizer: Any, examples: list[Any], max_length: int
) -> tuple[torch.Tensor, torch.Tensor]:
    encoded = [
        tokenize_chat(tokenizer, example.messages, max_length=max_length) for example in examples
    ]
    width = max(len(item.input_ids) for item in encoded)
    inputs, labels = [], []
    for item in encoded:
        padding = width - len(item.input_ids)
        inputs.append(list(item.input_ids) + [SPECIAL_IDS["<pad>"]] * padding)
        labels.append(list(item.labels) + [-100] * padding)
    return torch.tensor(inputs, dtype=torch.long), torch.tensor(labels, dtype=torch.long)


class SFTTrainer:
    def __init__(self, config: SFTConfig) -> None:
        self.config = config
        random.seed(config.seed)
        np.random.seed(config.seed)
        torch.manual_seed(config.seed)
        torch.use_deterministic_algorithms(config.deterministic)
        self.device = resolve_device(config.device)
        self.tokenizer = load_tokenizer(config.tokenizer_dir)
        if self.tokenizer.get_vocab_size() != config.model.vocab_size:
            raise IntegrityError("모델 vocab_size와 tokenizer가 다릅니다")
        self.train_data, self.heldout_data = _datasets(config)
        self.fingerprints = _fingerprints(config, self.train_data, self.heldout_data)
        self.model = CausalLM(config.model).to(self.device)
        if config.base_checkpoint is not None:
            _load_base(self.model, config.base_checkpoint)
        self.optimizer = torch.optim.AdamW(
            parameter_groups(self.model, config.optimizer.weight_decay),
            lr=config.optimizer.learning_rate,
            betas=(config.optimizer.beta1, config.optimizer.beta2),
            eps=config.optimizer.eps,
        )
        self.step = 0
        self.cursor = 0
        self.run_dir = config.run_dir

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "assistant-only-sft",
            "step": self.step,
            "fingerprints": self.fingerprints,
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "scheduler": {"step": self.step},
            "scaler": {},
            "sampler": {"cursor": self.cursor},
            "rng": rng_state(),
        }

    def save(self) -> Path:
        return save_checkpoint(self.run_dir / "checkpoints", self._payload(), step=self.step)

    def resume(self, path: Path | None = None) -> None:
        checkpoint = load_checkpoint(
            path or self.run_dir / "checkpoints/latest.pt", self.fingerprints
        )
        self.model.load_state_dict(checkpoint["model"], strict=True)
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.step = int(checkpoint["step"])
        if checkpoint["scheduler"] != {"step": self.step}:
            raise IntegrityError("SFT scheduler 상태가 step과 다릅니다")
        self.cursor = int(checkpoint["sampler"]["cursor"])
        restore_rng_state(checkpoint["rng"])

    def run(self) -> dict[str, object]:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.run_dir / "resolved-config.json", self.config.model_dump(mode="json"))
        write_json(
            self.run_dir / "data-manifest.json",
            {
                "schema_version": 1,
                "fingerprints": self.fingerprints,
                "train_file_sha256": self.train_data.file_sha256,
                "heldout_file_sha256": self.heldout_data.file_sha256,
                "licenses": sorted(set(self.train_data.licenses + self.heldout_data.licenses)),
            },
        )
        last_loss = math.nan
        while self.step < self.config.max_steps:
            indexes = [
                (self.cursor + offset) % len(self.train_data.examples)
                for offset in range(self.config.micro_batch_size)
            ]
            examples = [self.train_data.examples[index] for index in indexes]
            self.cursor = (self.cursor + self.config.micro_batch_size) % len(
                self.train_data.examples
            )
            inputs, labels = _batch(self.tokenizer, examples, self.config.sequence_length)
            inputs, labels = inputs.to(self.device), labels.to(self.device)
            self.optimizer.zero_grad(set_to_none=True)
            output = self.model(inputs, targets=labels)
            if output.loss is None or not bool(torch.isfinite(output.loss)):
                raise IntegrityError(f"SFT loss가 유한하지 않습니다: step={self.step}")
            output.loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(
                self.model.parameters(), self.config.gradient_clip_norm
            )
            if not bool(torch.isfinite(norm)):
                raise IntegrityError("SFT gradient norm이 유한하지 않습니다")
            lr = learning_rate(self.step, self.config.max_steps, self.config.optimizer)
            for group in self.optimizer.param_groups:
                group["lr"] = lr
            self.optimizer.step()
            self.step += 1
            last_loss = float(output.loss.detach())
            if self.step % self.config.log_interval == 0:
                with (self.run_dir / "metrics.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "event": "sft",
                                "step": self.step,
                                "loss": last_loss,
                                "learning_rate": lr,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    stream.flush()
                    os.fsync(stream.fileno())
            if self.step % self.config.checkpoint_interval == 0:
                self.save()
        checkpoint = self.save()
        return {"step": self.step, "loss": last_loss, "checkpoint": str(checkpoint)}


def train_sft(config: SFTConfig, *, resume: Path | None = None) -> dict[str, object]:
    trainer = SFTTrainer(config)
    if resume is not None:
        trainer.resume(resume)
    return trainer.run()


def _load_sft(
    config: SFTConfig, checkpoint: Path
) -> tuple[CausalLM, Any, ChatDataset, dict[str, str]]:
    train, heldout = _datasets(config)
    fingerprints = _fingerprints(config, train, heldout)
    payload = load_checkpoint(checkpoint, fingerprints)
    model = CausalLM(config.model).to(resolve_device(config.device))
    model.load_state_dict(payload["model"], strict=True)
    return model.eval(), load_tokenizer(config.tokenizer_dir), heldout, fingerprints


def _generated(
    model: CausalLM, tokenizer: Any, messages: tuple[Message, ...], config: SFTConfig
) -> tuple[list[int], str]:
    prompt = render_chat(messages, add_generation_prompt=True)
    ids = tokenizer.encode(prompt).ids
    if not ids or len(ids) >= config.model.max_seq_len:
        raise IntegrityError("chat prompt가 비었거나 문맥 길이를 초과합니다")
    device = next(model.parameters()).device
    output = model.generate(
        torch.tensor([ids], dtype=torch.long, device=device),
        GenerationConfig(
            max_new_tokens=config.max_new_tokens, temperature=0, eos_id=SPECIAL_IDS["<eos>"]
        ),
    )[0, len(ids) :].tolist()
    return output, tokenizer.decode(output, skip_special_tokens=True)


def generate_chat(config: SFTConfig, checkpoint: Path, prompt: str) -> dict[str, object]:
    model, tokenizer, _, fingerprints = _load_sft(config, checkpoint)
    generated, text = _generated(model, tokenizer, (Message(role="user", content=prompt),), config)
    return {
        "prompt": prompt,
        "response": text,
        "token_ids": generated,
        "eos_reached": SPECIAL_IDS["<eos>"] in generated,
        "fingerprints": fingerprints,
    }


def evaluate_chat(config: SFTConfig, checkpoint: Path) -> dict[str, object]:
    model, tokenizer, heldout, fingerprints = _load_sft(config, checkpoint)
    examples = list(heldout.examples[: config.max_eval_examples])
    losses: list[float] = []
    rows: list[dict[str, object]] = []
    unsafe = 0
    repetition_failures = 0
    eos_failures = 0
    for example in examples:
        inputs, labels = _batch(tokenizer, [example], config.sequence_length)
        device = next(model.parameters()).device
        with torch.no_grad():
            loss = model(inputs.to(device), targets=labels.to(device)).loss
        assert loss is not None
        losses.append(float(loss))
        prompt_messages = example.messages[:-1]
        generated, text = _generated(model, tokenizer, prompt_messages, config)
        repetition = 0.0 if not generated else 1.0 - len(set(generated)) / len(generated)
        unsafe_hits = [pattern for pattern in config.unsafe_patterns if pattern in text]
        unsafe += bool(unsafe_hits)
        repetition_failures += repetition > config.repetition_threshold
        eos_failures += SPECIAL_IDS["<eos>"] not in generated
        rows.append(
            {
                "id": example.id,
                "response": text,
                "loss": float(loss),
                "repetition_rate": repetition,
                "unsafe_hits": unsafe_hits,
                "eos_reached": SPECIAL_IDS["<eos>"] in generated,
            }
        )
    payload: dict[str, object] = {
        "schema_version": 1,
        "kind": "heldout-chat-evaluation",
        "examples": len(rows),
        "assistant_nll": sum(losses) / len(losses),
        "perplexity": math.exp(min(sum(losses) / len(losses), 80.0)),
        "gates": {
            "safety": "통과" if unsafe == 0 else "실패",
            "repetition": "통과" if repetition_failures == 0 else "실패",
            "eos": "통과" if eos_failures == 0 else "실패",
        },
        "rows": rows,
        "fingerprints": fingerprints,
    }
    payload["fingerprint"] = fingerprint(payload)
    write_json(config.run_dir / "heldout-evaluation.json", payload)
    return payload
