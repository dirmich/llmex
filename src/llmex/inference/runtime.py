"""checkpoint, 모델, tokenizer 호환성을 엄격히 검증하는 추론 runtime."""

import json
from dataclasses import dataclass
from typing import Any, cast

import torch
from tokenizers import Tokenizer

from llmex.config import EvaluationConfig, TrainingConfig, load_yaml
from llmex.errors import ConfigError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.model import CausalLM
from llmex.tokenizer.core import SPECIAL_IDS, load_tokenizer
from llmex.train.checkpoint import TRAIN_CHECKPOINT_REQUIRED_STATE, load_checkpoint


@dataclass(frozen=True)
class LoadedRuntime:
    model: CausalLM
    tokenizer: Tokenizer
    device: torch.device
    checkpoint: dict[str, Any]
    fingerprints: dict[str, str]
    training: TrainingConfig


def resolve_device(name: str) -> torch.device:
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


def load_runtime(config: EvaluationConfig) -> LoadedRuntime:
    training = load_yaml(config.training_config, TrainingConfig)
    manifest_path = config.shards_manifest
    try:
        manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
        tokenizer_manifest = cast(
            dict[str, Any],
            json.loads(
                (config.tokenizer_dir / "tokenizer-manifest.json").read_text(encoding="utf-8")
            ),
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"호환성 manifest를 읽을 수 없습니다: {exc}") from exc
    if training.shards_manifest.resolve() != manifest_path.resolve():
        raise IntegrityError("평가 shard manifest가 학습 설정과 다릅니다")
    tokenizer_fingerprint = str(tokenizer_manifest.get("fingerprint", ""))
    if tokenizer_fingerprint != str(manifest.get("tokenizer_fingerprint", "")):
        raise IntegrityError("tokenizer와 shard fingerprint가 다릅니다")
    if training.model.vocab_size != int(tokenizer_manifest.get("vocab_size_actual", -1)):
        raise IntegrityError("모델 vocab_size와 tokenizer vocab 크기가 다릅니다")
    special = tokenizer_manifest.get("special_token_ids")
    if special != SPECIAL_IDS:
        raise IntegrityError("tokenizer special token ID 계약이 다릅니다")
    fingerprints = {
        "config": fingerprint(training.model_dump(mode="json")),
        "corpus": fingerprint(manifest["corpus"]),
        "tokenizer": tokenizer_fingerprint,
        "model": fingerprint(training.model.model_dump(mode="json")),
        "shards": str(manifest["fingerprint"]),
    }
    checkpoint = load_checkpoint(
        config.checkpoint, fingerprints, required_state=TRAIN_CHECKPOINT_REQUIRED_STATE
    )
    model = CausalLM(training.model)
    try:
        model.load_state_dict(checkpoint["model"], strict=True)
    except (RuntimeError, KeyError) as exc:
        raise IntegrityError(f"checkpoint 모델 가중치가 형상과 호환되지 않습니다: {exc}") from exc
    tokenizer = load_tokenizer(config.tokenizer_dir)
    device = resolve_device(config.device)
    model.to(device).eval()
    checkpoint_sha256 = sha256_file(config.checkpoint)
    return LoadedRuntime(
        model=model,
        tokenizer=tokenizer,
        device=device,
        checkpoint=checkpoint,
        fingerprints={**fingerprints, "checkpoint_sha256": checkpoint_sha256},
        training=training,
    )
