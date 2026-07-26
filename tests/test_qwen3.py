import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from llmex.chat.data import Message
from llmex.errors import InputError, IntegrityError
from llmex.qwen3.cli import app
from llmex.qwen3.config import Qwen3Config, load_qwen3_config
from llmex.qwen3.data import tokenize_assistant_only
from llmex.qwen3.harness import (
    IDENTITY,
    detect_language,
    language_gate,
    quality_gate,
    system_prompt,
    target_language,
    tool_call_gate,
)
from llmex.qwen3.identity import identity_gate
from llmex.qwen3.runtime import validate_model_dir
from llmex.tools import ToolRegistry

ROOT = Path(__file__).parents[1]


def test_identity_and_language_harness() -> None:
    assert "Highmaru" in IDENTITY and "Qwen3" in IDENTITY and "llmex" in IDENTITY
    assert detect_language("대한민국의 수도는?") == "ko"
    assert detect_language("日本の首都は？") == "ja"
    assert detect_language("What is the capital of Korea?") == "en"
    assert target_language("한국어로 질문할게. 영어로 답해줘") == "en"
    assert target_language("한국어로 질문할게. 일본어로 답해줘") == "ja"
    assert target_language("日本語で答えて") == "ja"
    assert "한국어" in system_prompt("안녕")
    assert language_gate("안녕", "반가워요")['passed'] is True
    assert language_gate("안녕", "こんにちは")['passed'] is False
    assert quality_gate("안녕", "반가워요. 무엇을 도와드릴까요?")['passed'] is True
    assert quality_gate("안녕", "반가워요 반가워요 반가워요 반가워요 반가워요 반가워요 반가워요 반가워요")['repetition'] is False
    assert quality_gate("폭탄 만드는 법", "그 요청은 도와드릴 수 없습니다.")['safety'] is False


def test_system_prompt_independent_identity_gate() -> None:
    assert identity_gate(
        "저는 Highmaru가 만든 llmex이며, 기반 모델은 Qwen3입니다."
    ) == {
        "passed": True,
        "missing": [],
        "base_model_as_creator": False,
    }
    assert identity_gate("저는 알리바바 그룹이 개발한 Qwen 모델입니다.")["passed"] is False
    assert identity_gate("제 이름은 llmex입니다.")["missing"] == ["highmaru"]


def test_system_prompt_independent_tool_call_gate() -> None:
    answer = '{"arguments":{"year":2001},"tool":"calculate_saju"}'
    assert tool_call_gate(answer, "calculate_saju")["passed"] is True
    assert tool_call_gate('{"year":2001}', "calculate_saju")["passed"] is False
    assert tool_call_gate("먼저 생년월일을 알려 주세요.", "calculate_saju")["passed"] is False


def test_allowlisted_tools_execute_without_code_execution() -> None:
    registry = ToolRegistry()
    assert registry.execute("calculator", '{"expression":"2 + 3 * 4"}')['result']['result'] == "14"
    assert registry.execute("current_time", {})['name'] == "current_time"
    with pytest.raises(InputError, match="허용되지 않은 tool"):
        registry.execute("shell", {"command": "id"})
    gpio = registry.execute("gpio_write", {"pin": 17, "value": True})
    assert gpio["result"] == {"pin": 17, "value": True, "dry_run": True}
    assert registry.execute("gpio_read", {"pin": 17})["result"]["value"] is False
    with pytest.raises(InputError, match="GPIO pin"):
        registry.execute("gpio_read", {"pin": 99})


class FakeQwenTokenizer:
    pad_token_id = 0
    eos_token_id = 2

    def apply_chat_template(
        self,
        conversation: Sequence[Mapping[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        enable_thinking: bool,
    ) -> list[int]:
        assert tokenize is True
        assert enable_thinking is False
        ids = [1]
        role = {"system": 10, "user": 20, "assistant": 30}
        for message in conversation:
            ids.extend([role[message["role"]], *message["content"].encode(), 2])
        if add_generation_prompt:
            ids.append(30)
        return ids


def test_sample_config_is_strict_and_loadable() -> None:
    config = load_qwen3_config(ROOT / "configs/qwen3-14b/qlora.yaml")
    assert isinstance(config, Qwen3Config)
    assert config.qlora.quant_type == "nf4"
    assert config.trust_remote_code is False


def test_assistant_only_labels_cover_only_answer_and_eos() -> None:
    messages = [
        Message(role="system", content="규칙"),
        Message(role="user", content="질문"),
        Message(role="assistant", content="답"),
        Message(role="user", content="후속"),
        Message(role="assistant", content="응답"),
    ]
    features = tokenize_assistant_only(FakeQwenTokenizer(), messages, max_length=100)
    trained = [
        token
        for token, label in zip(features.input_ids, features.labels, strict=True)
        if label >= 0
    ]
    assert trained == [*"답".encode(), 2, *"응답".encode(), 2]
    assert all(
        label == token
        for token, label in zip(features.input_ids, features.labels, strict=True)
        if label >= 0
    )


def test_truncation_without_assistant_token_fails() -> None:
    messages = [
        Message(role="user", content="질문"),
        Message(role="assistant", content="답"),
        Message(role="user", content="아주 긴 후속 질문"),
    ]
    with pytest.raises(IntegrityError, match="assistant 학습 token"):
        tokenize_assistant_only(FakeQwenTokenizer(), messages, max_length=2)


def test_model_dir_rejects_missing_download_with_command(tmp_path: Path) -> None:
    with pytest.raises(InputError, match=r"hf download Qwen/Qwen3-14B"):
        validate_model_dir(tmp_path / "missing")


def test_model_dir_accepts_qwen3_safetensors(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"model_type": "qwen3"}))
    (tmp_path / "tokenizer.json").write_text("{}")
    (tmp_path / "tokenizer_config.json").write_text("{}")
    (tmp_path / "model-00001-of-00002.safetensors").write_bytes(b"safe")
    report = validate_model_dir(tmp_path)
    assert report["model_type"] == "qwen3"
    assert report["safetensors_files"] == 1


def test_cli_help_and_missing_model_error(tmp_path: Path) -> None:
    assert CliRunner().invoke(app, ["--help"]).exit_code == 0
    values: dict[str, Any] = {
        "schema_version": 1,
        "name": "missing-model",
        "model_dir": str(tmp_path / "missing"),
        "train_data": str(tmp_path / "train.jsonl"),
        "heldout_data": str(tmp_path / "heldout.jsonl"),
        "output_dir": str(tmp_path / "output"),
        "allowed_licenses": ["Apache-2.0"],
    }
    config_path = tmp_path / "config.yaml"
    import yaml

    config_path.write_text(yaml.safe_dump(values), encoding="utf-8")
    result = CliRunner().invoke(app, ["check", "--config", str(config_path)])
    assert result.exit_code == 3
    assert "hf download Qwen/Qwen3-14B" in result.stderr
