"""SFT checkpoint를 Hugging Face Llama 형식과 GGUF로 안전하게 내보낸다."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import cast

import torch
from torch import Tensor

from llmex.chat.runtime import SFTTrainer
from llmex.config import ModelConfig, SFTConfig
from llmex.errors import ConflictError, InputError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.train.checkpoint import load_checkpoint_snapshot, validate_model_state

_GGUF_OUTTYPES = {"f32", "f16", "bf16", "q8_0"}
_HF_ARTIFACTS = {
    "README.md",
    "config.json",
    "pytorch_model.bin",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
}


def _inverse_llama_rope_permute(weight: Tensor, heads: int) -> Tensor:
    """인접 쌍 RoPE projection을 HF Llama의 half-split 배열로 바꾼다."""

    if weight.ndim != 2 or weight.shape[0] % (heads * 2) != 0:
        raise IntegrityError("attention projection의 RoPE 순열 shape이 올바르지 않습니다")
    return (
        weight.reshape(heads, weight.shape[0] // heads // 2, 2, weight.shape[1])
        .swapaxes(1, 2)
        .reshape(weight.shape)
        .contiguous()
    )


def _hf_state(state: dict[str, Tensor], model: ModelConfig) -> dict[str, Tensor]:
    expected = {"token_embedding.weight", "final_norm.weight", "lm_head.weight"}
    for index in range(model.n_layers):
        prefix = f"blocks.{index}"
        expected.update(
            {
                f"{prefix}.attention_norm.weight",
                f"{prefix}.attention.q_proj.weight",
                f"{prefix}.attention.k_proj.weight",
                f"{prefix}.attention.v_proj.weight",
                f"{prefix}.attention.out_proj.weight",
                f"{prefix}.ffn_norm.weight",
                f"{prefix}.ffn.gate.weight",
                f"{prefix}.ffn.up.weight",
                f"{prefix}.ffn.down.weight",
            }
        )
    if set(state) != expected:
        raise IntegrityError("checkpoint model tensor 집합이 LLMEX Llama export 계약과 다릅니다")
    if not torch.equal(state["token_embedding.weight"], state["lm_head.weight"]):
        raise IntegrityError("checkpoint tied embedding과 lm_head가 다릅니다")
    result: dict[str, Tensor] = {
        "model.embed_tokens.weight": state["token_embedding.weight"].contiguous(),
        "model.norm.weight": state["final_norm.weight"].contiguous(),
        "lm_head.weight": state["token_embedding.weight"].contiguous(),
    }
    for index in range(model.n_layers):
        source = f"blocks.{index}"
        target = f"model.layers.{index}"
        result[f"{target}.input_layernorm.weight"] = state[
            f"{source}.attention_norm.weight"
        ].contiguous()
        result[f"{target}.self_attn.q_proj.weight"] = _inverse_llama_rope_permute(
            state[f"{source}.attention.q_proj.weight"], model.n_heads
        )
        result[f"{target}.self_attn.k_proj.weight"] = _inverse_llama_rope_permute(
            state[f"{source}.attention.k_proj.weight"], model.n_kv_heads
        )
        result[f"{target}.self_attn.v_proj.weight"] = state[
            f"{source}.attention.v_proj.weight"
        ].contiguous()
        result[f"{target}.self_attn.o_proj.weight"] = state[
            f"{source}.attention.out_proj.weight"
        ].contiguous()
        result[f"{target}.post_attention_layernorm.weight"] = state[
            f"{source}.ffn_norm.weight"
        ].contiguous()
        result[f"{target}.mlp.gate_proj.weight"] = state[f"{source}.ffn.gate.weight"].contiguous()
        result[f"{target}.mlp.up_proj.weight"] = state[f"{source}.ffn.up.weight"].contiguous()
        result[f"{target}.mlp.down_proj.weight"] = state[f"{source}.ffn.down.weight"].contiguous()
    return result


def _validate_state(state: dict[str, Tensor], expected: dict[str, Tensor]) -> None:
    if set(state) != set(expected):
        raise IntegrityError("checkpoint model tensor 집합이 현재 모델과 다릅니다")
    for name, tensor in state.items():
        reference = expected[name]
        if tensor.shape != reference.shape or tensor.dtype != reference.dtype:
            raise IntegrityError(f"checkpoint model tensor 형상 또는 dtype이 다릅니다: {name}")


def _hf_config(model: ModelConfig) -> dict[str, object]:
    return {
        "architectures": ["LlamaForCausalLM"],
        "attention_bias": False,
        "attention_dropout": model.dropout,
        "bos_token_id": 1,
        "eos_token_id": 2,
        "head_dim": model.d_model // model.n_heads,
        "hidden_act": "silu",
        "hidden_size": model.d_model,
        "initializer_range": model.init_std,
        "intermediate_size": model.ffn_hidden_size,
        "max_position_embeddings": model.max_seq_len,
        "mlp_bias": False,
        "model_type": "llama",
        "num_attention_heads": model.n_heads,
        "num_hidden_layers": model.n_layers,
        "num_key_value_heads": model.n_kv_heads,
        "pad_token_id": 0,
        "pretraining_tp": 1,
        "rms_norm_eps": model.norm_eps,
        "rope_theta": model.rope_theta,
        "tie_word_embeddings": True,
        "torch_dtype": "float32",
        "transformers_version": "4.0.0",
        "use_cache": True,
        "vocab_size": model.vocab_size,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _hf_chat_template() -> str:
    return (
        "{{ bos_token }}{% for message in messages %}"
        "{{ '<|' + message['role'] + '|>\\n' "
        "+ message['content'].rstrip('\\r\\n') + '\\n' }}"
        "{% if message['role'] == 'assistant' %}{{ eos_token }}{% endif %}"
        "{% endfor %}{% if add_generation_prompt %}"
        "{{ '<|assistant|>\\n' }}{% endif %}"
    )


def export_hf(
    config: SFTConfig,
    checkpoint: Path,
    expected_checkpoint_sha256: str,
    output_dir: Path,
) -> dict[str, object]:
    """검증된 SFT checkpoint를 private HF Llama 디렉터리로 원자 게시한다."""

    if output_dir.exists():
        raise ConflictError("HF export 출력 경로는 존재하지 않는 디렉터리여야 합니다")
    trainer = SFTTrainer(config)
    payload, checkpoint_sha256 = load_checkpoint_snapshot(
        checkpoint,
        trainer.fingerprints,
        supported_schema_versions={2},
    )
    if checkpoint_sha256 != expected_checkpoint_sha256:
        raise IntegrityError("HF export checkpoint SHA-256이 예상값과 다릅니다")
    if (
        payload.get("release_gate") != "blocked"
        or payload.get("redistribution_allowed") is not False
    ):
        raise IntegrityError("내부 teacher 파생 checkpoint의 release 차단이 없습니다")
    checkpoint_state = validate_model_state(payload["model"], context="HF export checkpoint model")
    _validate_state(checkpoint_state, trainer.model.state_dict())
    state = _hf_state(checkpoint_state, config.model)
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-staging-", dir=parent))
    try:
        staging.chmod(0o700)
        chat_template = _hf_chat_template()
        torch.save(state, staging / "pytorch_model.bin")
        shutil.copyfile(config.tokenizer_dir / "tokenizer.json", staging / "tokenizer.json")
        _write_json(staging / "config.json", _hf_config(config.model))
        _write_json(
            staging / "tokenizer_config.json",
            {
                "add_bos_token": False,
                "add_eos_token": False,
                "add_prefix_space": False,
                "bos_token": "<bos>",
                "chat_template": chat_template,
                "clean_up_tokenization_spaces": False,
                "eos_token": "<eos>",
                "model_max_length": config.model.max_seq_len,
                "pad_token": "<pad>",
                "tokenizer_class": "PreTrainedTokenizerFast",
                "unk_token": "<unk>",
            },
        )
        _write_json(
            staging / "special_tokens_map.json",
            {
                "bos_token": "<bos>",
                "eos_token": "<eos>",
                "pad_token": "<pad>",
                "unk_token": "<unk>",
            },
        )
        (staging / "README.md").write_text(
            "# LLMEX 한국어·영어·일본어 대화 모델\n\n"
            "이 모델은 내부 전용 teacher 증류 출력에서 파생됐습니다. 공개·재배포하지 말고 "
            "Hugging Face에서는 private 저장소로만 사용하세요.\n",
            encoding="utf-8",
        )
        for path in staging.iterdir():
            if path.is_file():
                path.chmod(0o600)
        artifacts = {
            path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sorted(staging.iterdir())
            if path.is_file()
        }
        manifest: dict[str, object] = {
            "schema_version": 1,
            "kind": "llmex-huggingface-llama-export",
            "checkpoint": {"path": str(checkpoint), "sha256": expected_checkpoint_sha256},
            "sft_config_fingerprint": trainer.fingerprints["config"],
            "model_fingerprint": trainer.fingerprints["model"],
            "tokenizer_sha256": trainer.fingerprints["tokenizer"],
            "parameter_count": trainer.model.parameter_count(),
            "redistribution_allowed": False,
            "release_gate": "blocked",
            "hub_visibility": "private",
            "artifacts": artifacts,
        }
        manifest["fingerprint"] = fingerprint(manifest)
        _write_json(staging / "export-manifest.json", manifest)
        (staging / "export-manifest.json").chmod(0o600)
        for path in staging.iterdir():
            if path.is_file():
                with path.open("rb") as stream:
                    os.fsync(stream.fileno())
        os.replace(staging, output_dir)
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def export_gguf(
    hf_dir: Path,
    expected_hf_manifest_sha256: str,
    llama_cpp_dir: Path,
    output: Path,
    *,
    outtype: str = "f16",
) -> dict[str, object]:
    """HF export를 llama.cpp 공식 converter로 GGUF로 변환한다."""

    if outtype not in _GGUF_OUTTYPES:
        raise InputError(f"지원하지 않는 GGUF outtype입니다: {outtype}")
    manifest_path = hf_dir / "export-manifest.json"
    if not manifest_path.is_file():
        raise InputError("검증할 HF export manifest가 없습니다")
    if sha256_file(manifest_path) != expected_hf_manifest_sha256:
        raise IntegrityError("HF export manifest SHA-256이 예상값과 다릅니다")
    try:
        raw_manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise IntegrityError(f"HF export manifest를 읽을 수 없습니다: {error}") from error
    if not isinstance(raw_manifest, dict):
        raise IntegrityError("HF export manifest가 매핑이 아닙니다")
    manifest = cast(dict[str, object], raw_manifest)
    if (
        manifest.get("schema_version") != 1
        or manifest.get("kind") != "llmex-huggingface-llama-export"
        or manifest.get("release_gate") != "blocked"
        or manifest.get("redistribution_allowed") is not False
        or manifest.get("hub_visibility") != "private"
        or manifest.get("fingerprint")
        != fingerprint({key: value for key, value in manifest.items() if key != "fingerprint"})
    ):
        raise IntegrityError("HF export manifest 결속이 올바르지 않습니다")
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, dict):
        raise IntegrityError("HF export artifact 목록이 없습니다")
    artifacts = cast(dict[str, object], raw_artifacts)
    if set(artifacts) != _HF_ARTIFACTS:
        raise IntegrityError("HF export artifact 집합이 올바르지 않습니다")
    for name, raw_metadata in artifacts.items():
        if not isinstance(raw_metadata, dict):
            raise IntegrityError("HF export artifact metadata가 올바르지 않습니다")
        metadata = cast(dict[str, object], raw_metadata)
        artifact = hf_dir / name
        if (
            not artifact.is_file()
            or metadata.get("bytes") != artifact.stat().st_size
            or metadata.get("sha256") != sha256_file(artifact)
        ):
            raise IntegrityError(f"HF export artifact 무결성이 깨졌습니다: {name}")
    converter = llama_cpp_dir / "convert_hf_to_gguf.py"
    if not converter.is_file():
        raise InputError("llama.cpp convert_hf_to_gguf.py가 없습니다")
    if output.exists():
        raise ConflictError("GGUF 출력 파일이 이미 존재합니다")
    output.parent.mkdir(parents=True, exist_ok=True)
    wrapper = Path(__file__).resolve().parents[3] / "scripts/convert_llmex_hf_to_gguf.py"
    if not wrapper.is_file():
        raise InputError("LLMEX GGUF converter wrapper가 없습니다")
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-staging-", dir=output.parent))
    staged_output = staging / output.name
    command = [
        "uv",
        "run",
        "--with",
        "transformers",
        "--with",
        "sentencepiece",
        "python",
        str(wrapper),
        "--llama-cpp-dir",
        str(llama_cpp_dir),
        "--hf-dir",
        str(hf_dir),
        "--expected-tokenizer-sha256",
        str(cast(dict[str, object], artifacts["tokenizer.json"])["sha256"]),
        "--outfile",
        str(staged_output),
        "--outtype",
        outtype,
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if completed.returncode != 0 or not staged_output.is_file():
            raise IntegrityError(f"GGUF 변환 실패: {completed.stderr[-2000:]}")
        with staged_output.open("rb") as stream:
            if stream.read(4) != b"GGUF":
                raise IntegrityError("GGUF magic이 올바르지 않습니다")
        staged_output.chmod(0o600)
        try:
            os.link(staged_output, output)
        except FileExistsError as error:
            raise ConflictError("변환 중 GGUF 출력 파일이 생성됐습니다") from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise IntegrityError(f"GGUF 변환 실행 실패: {error}") from error
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return {
        "schema_version": 1,
        "status": "ok",
        "path": str(output),
        "sha256": sha256_file(output),
        "bytes": output.stat().st_size,
        "outtype": outtype,
        "hf_manifest_sha256": expected_hf_manifest_sha256,
        "redistribution_allowed": False,
        "release_gate": "blocked",
    }
