# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
import json
from pathlib import Path

import torch
import yaml
from test_m4_training import _config, _manifest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import EvaluationConfig
from llmex.fingerprint import fingerprint, sha256_file
from llmex.model import CausalLM, GenerationConfig
from llmex.tokenizer.core import SPECIAL_IDS
from llmex.train.engine import Trainer


def _artifacts(tmp_path: Path) -> tuple[Path, EvaluationConfig]:
    manifest_path = _manifest(tmp_path)
    tokenizer_dir = tmp_path / "tokenizer"
    tokenizer_dir.mkdir()
    vocab = {"<pad>": 0, "<bos>": 1, "<eos>": 2, "<unk>": 3}
    vocab.update({f"토큰{index}": index for index in range(4, 16)})
    tokenizer = Tokenizer(WordLevel(vocab, unk_token="<unk>"))
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer.save(str(tokenizer_dir / "tokenizer.json"))
    artifacts = {
        "tokenizer.json": {
            "sha256": sha256_file(tokenizer_dir / "tokenizer.json"),
            "bytes": (tokenizer_dir / "tokenizer.json").stat().st_size,
        }
    }
    tokenizer_manifest: dict[str, object] = {
        "schema_version": 1,
        "vocab_size_actual": 16,
        "special_token_ids": SPECIAL_IDS,
        "artifacts": artifacts,
    }
    tokenizer_manifest["fingerprint"] = fingerprint(tokenizer_manifest)
    (tokenizer_dir / "tokenizer-manifest.json").write_text(
        json.dumps(tokenizer_manifest), encoding="utf-8"
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["tokenizer_fingerprint"] = tokenizer_manifest["fingerprint"]
    manifest.pop("fingerprint")
    manifest["fingerprint"] = fingerprint(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    training = _config(manifest_path, tmp_path / "run", max_steps=1)
    training_yaml = tmp_path / "training.yaml"
    training_yaml.write_text(
        yaml.safe_dump(training.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    Trainer(training).run()
    evaluation = EvaluationConfig(
        name="m5-test",
        checkpoint=training.run_dir / "checkpoints/latest.pt",
        training_config=training_yaml,
        tokenizer_dir=tokenizer_dir,
        shards_manifest=manifest_path,
        output_dir=tmp_path / "evaluation",
        device="cpu",
        splits=["validation", "test"],
        batch_size=2,
        max_batches=1,
        prompts=["토큰4 토큰5"],
        max_new_tokens=2,
        temperature=0.0,
        benchmark_warmup=0,
        benchmark_iterations=1,
    )
    config_path = tmp_path / "evaluation.yaml"
    config_path.write_text(
        yaml.safe_dump(evaluation.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    return config_path, evaluation


def test_sampling_cache_logits_generation_and_limits() -> None:
    torch.manual_seed(22)
    model = CausalLM(_config(Path("x"), Path("y")).model).eval()
    prompt = torch.tensor([[1, 4, 5]])
    full = model(prompt, use_cache=True)
    assert full.cache is not None
    cached_next = model(torch.tensor([[6]]), cache=full.cache, use_cache=True).logits[:, -1]
    uncached_next = model(torch.tensor([[1, 4, 5, 6]])).logits[:, -1]
    torch.testing.assert_close(cached_next, uncached_next, atol=2e-6, rtol=2e-5)
    sampled = model.generate(
        prompt,
        GenerationConfig(
            max_new_tokens=3,
            temperature=0.8,
            top_k=5,
            top_p=0.8,
            repetition_penalty=1.2,
        ),
        generator=torch.Generator().manual_seed(7),
    )
    repeated = model.generate(
        prompt,
        GenerationConfig(
            max_new_tokens=3,
            temperature=0.8,
            top_k=5,
            top_p=0.8,
            repetition_penalty=1.2,
        ),
        generator=torch.Generator().manual_seed(7),
    )
    assert torch.equal(sampled, repeated)
    assert sampled.size(1) <= model.config.max_seq_len


def test_eval_generate_benchmark_cli_e2e_and_artifacts(tmp_path: Path) -> None:
    config_path, evaluation = _artifacts(tmp_path)
    runner = CliRunner()
    for command in ("eval", "generate", "benchmark"):
        dry = runner.invoke(app, [command, "--config", str(config_path), "--dry-run"])
        assert dry.exit_code == 0, dry.output
        result = runner.invoke(app, [command, "--config", str(config_path)])
        assert result.exit_code == 0, result.output
    report = json.loads((evaluation.output_dir / "evaluation-report.json").read_text())
    assert set(report["splits"]) == {"validation", "test"}
    assert report["splits"]["test"]["perplexity"] > 0
    assert report["splits"]["test"]["bits_per_byte"] > 0
    assert report["cloze_schema"]["items"][0]["provenance"]
    assert "mean_log_likelihood" in report["cloze_schema"]["items"][0]["scores"][0]
    assert 0.0 <= report["cloze_schema"]["accuracy"] <= 1.0
    assert report["canary_exposure"]["status"] == "미실행"
    assert report["canary_exposure"]["gate"] == "실패"
    for stem in ("evaluation", "generation", "benchmark"):
        assert (evaluation.output_dir / f"{stem}-report.md").is_file()
        assert (evaluation.output_dir / f"{stem}-report.checksums.json").is_file()
    tokenizer_manifest_path = evaluation.tokenizer_dir / "tokenizer-manifest.json"
    tokenizer_manifest = json.loads(tokenizer_manifest_path.read_text())
    tokenizer_manifest["fingerprint"] = "0" * 64
    tokenizer_manifest_path.write_text(json.dumps(tokenizer_manifest), encoding="utf-8")
    rejected = runner.invoke(app, ["generate", "--config", str(config_path)])
    assert rejected.exit_code == 5
    assert "fingerprint가 다릅니다" in rejected.output
