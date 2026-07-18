# pyright: reportPrivateUsage=false
import json
import subprocess
from pathlib import Path

import pytest
from torch import Tensor
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import ModelConfig
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.model import CausalLM
from llmex.model.export import (
    _hf_chat_template,
    _hf_state,
    _inverse_llama_rope_permute,
    export_gguf,
)


def _llama_cpp_permute(weight: Tensor, heads: int) -> Tensor:
    return (
        weight.reshape(heads, 2, weight.shape[0] // heads // 2, weight.shape[1])
        .swapaxes(1, 2)
        .reshape(weight.shape)
        .contiguous()
    )


def test_hf_export는_qk_RoPE_배열을_roundtrip하고_tensor를_완전_매핑한다() -> None:
    config = ModelConfig(
        name="export-test",
        vocab_size=32,
        max_seq_len=64,
        n_layers=1,
        d_model=16,
        n_heads=4,
        n_kv_heads=2,
        ffn_hidden_size=32,
        dropout=0.0,
    )
    state = CausalLM(config).state_dict()
    hf = _hf_state(state, config)
    assert len(hf) == 12
    assert hf["model.embed_tokens.weight"].data_ptr() == hf["lm_head.weight"].data_ptr()
    for source, target, heads in (
        (
            "blocks.0.attention.q_proj.weight",
            "model.layers.0.self_attn.q_proj.weight",
            config.n_heads,
        ),
        (
            "blocks.0.attention.k_proj.weight",
            "model.layers.0.self_attn.k_proj.weight",
            config.n_kv_heads,
        ),
    ):
        exported = _inverse_llama_rope_permute(state[source], heads)
        assert hf[target].equal(exported)
        assert _llama_cpp_permute(exported, heads).equal(state[source])


def test_model_export_CLI가_HF와_GGUF_명령을_노출한다() -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["model", "export-hf", "--help"]).exit_code == 0
    assert runner.invoke(app, ["model", "export-gguf", "--help"]).exit_code == 0


def test_HF_chat_template가_학습_BOS_EOS와_줄바꿈_계약을_보존한다() -> None:
    template = _hf_chat_template()
    assert template.startswith("{{ bos_token }}")
    assert "message['content'].rstrip('\\r\\n')" in template
    assert "message['role'] == 'assistant' %}{{ eos_token }}" in template
    assert template.endswith("{{ '<|assistant|>\\n' }}{% endif %}")


def _hf_fixture(root: Path) -> str:
    artifacts: dict[str, dict[str, object]] = {}
    for name in (
        "README.md",
        "config.json",
        "pytorch_model.bin",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
    ):
        path = root / name
        path.write_bytes(f"fixture:{name}".encode())
        artifacts[name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    manifest: dict[str, object] = {
        "schema_version": 1,
        "kind": "llmex-huggingface-llama-export",
        "release_gate": "blocked",
        "redistribution_allowed": False,
        "hub_visibility": "private",
        "artifacts": artifacts,
    }
    manifest["fingerprint"] = fingerprint(manifest)
    manifest_path = root / "export-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sha256_file(manifest_path)


def test_GGUF_export가_manifest를_pin하고_private_파일로_원자_게시한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hf_dir = tmp_path / "hf"
    hf_dir.mkdir()
    expected_manifest = _hf_fixture(hf_dir)
    llama_cpp = tmp_path / "llama.cpp"
    llama_cpp.mkdir()
    (llama_cpp / "convert_hf_to_gguf.py").write_text("# fixture\n", encoding="utf-8")
    output = tmp_path / "model.gguf"

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        outfile = Path(command[command.index("--outfile") + 1])
        outfile.write_bytes(b"GGUFfixture")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = export_gguf(hf_dir, expected_manifest, llama_cpp, output)
    assert result["hf_manifest_sha256"] == expected_manifest
    assert result["redistribution_allowed"] is False
    assert output.read_bytes() == b"GGUFfixture"
    assert output.stat().st_mode & 0o777 == 0o600


def test_GGUF_export가_HF_artifact_변조를_거부한다(tmp_path: Path) -> None:
    hf_dir = tmp_path / "hf"
    hf_dir.mkdir()
    expected_manifest = _hf_fixture(hf_dir)
    (hf_dir / "tokenizer.json").write_text("변조", encoding="utf-8")
    with pytest.raises(IntegrityError, match="artifact 무결성"):
        export_gguf(hf_dir, expected_manifest, tmp_path / "llama.cpp", tmp_path / "model.gguf")
