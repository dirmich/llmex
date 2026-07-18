# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
import hashlib
import json
import os
import socket
import threading
import time
import unicodedata
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from llmex.chat.data import load_chat_jsonl
from llmex.cli import app
from llmex.config import DistillationConfig, load_yaml
from llmex.data.io import write_jsonl_zst
from llmex.distill import collect, export, preflight, prepare, status, validate
from llmex.distill.client import completion, request_body
from llmex.distill.filters import canonical_response, filter_response, repetition_ratio
from llmex.errors import ConflictError, InputError, IntegrityError
from llmex.fingerprint import fingerprint


def _source_row(identifier: str, prompt: str, split: str = "train") -> dict[str, Any]:
    messages = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "기존 공개 답변"},
    ]
    provenance = {
        "dataset": "CarrotAI/ko-instruction-dataset",
        "source": "https://huggingface.co/datasets/CarrotAI/ko-instruction-dataset",
        "license": "Apache-2.0",
        "collected_at": "2026-07-17",
    }
    basis = {"id": identifier, "messages": messages, "provenance": provenance, "split": split}
    return {"schema_version": 1, **basis, "sha256": fingerprint(basis)}


def _inputs(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source.jsonl"
    rows = [_source_row(f"source-{index}", f"고유 질문 {index}") for index in range(10)]
    rows.append(_source_row("source-duplicate", "  고유   질문  0  "))
    rows.append(_source_row("source-heldout", "원본 heldout 질문", "heldout"))
    rows.append(_source_row("source-heldout-collision", "고유 질문 1", "heldout"))
    source.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    corpus = tmp_path / "corpus.jsonl.zst"
    write_jsonl_zst(
        corpus,
        (
            {
                "split": "train",
                "title": f"위키 주제 {index}",
                "source_url": f"https://ko.wikipedia.org/?curid={index}",
                "license": "CC BY-SA 4.0",
                "page_id": index,
                "revision_id": index + 100,
                "dump_date": "20260701",
                "sha256": hashlib.sha256(f"wiki-{index}".encode()).hexdigest(),
            }
            for index in range(1, 31)
        ),
    )
    return source, corpus


class _TeacherHandler(BaseHTTPRequestHandler):
    calls = 0
    retry_once = True
    authorizations: ClassVar[list[str | None]] = []
    payloads: ClassVar[list[dict[str, Any]]] = []
    message_extra: ClassVar[dict[str, Any]] = {}
    role = "assistant"
    response_override: ClassVar[str | None] = None
    retry_after = "0"

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_GET(self) -> None:
        assert self.path == "/v1/models"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"id": "qwen36mtp"}]}).encode())

    def do_POST(self) -> None:
        type(self).calls += 1
        type(self).authorizations.append(self.headers.get("Authorization"))
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        type(self).payloads.append(payload)
        if type(self).retry_once:
            type(self).retry_once = False
            self.send_response(429)
            self.send_header("Retry-After", type(self).retry_after)
            self.end_headers()
            return
        prompt = payload["messages"][-1]["content"]
        content = type(self).response_override or (
            f"{prompt}의 핵심 개념과 배경을 정확하고 간결하게 정리한 답변입니다."
        )
        response = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": type(self).role,
                        "content": content,
                        "reasoning_content": "",
                        **type(self).message_extra,
                    },
                }
            ]
        }
        raw = json.dumps(response, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@contextmanager
def _server() -> Generator[str]:
    _TeacherHandler.calls = 0
    _TeacherHandler.retry_once = True
    _TeacherHandler.authorizations = []
    _TeacherHandler.payloads = []
    _TeacherHandler.message_extra = {}
    _TeacherHandler.role = "assistant"
    _TeacherHandler.response_override = None
    _TeacherHandler.retry_after = "0"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TeacherHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        thread.join()


def _config(tmp_path: Path, endpoint: str, *, target: int = 16) -> DistillationConfig:
    source, corpus = _inputs(tmp_path)
    return DistillationConfig(
        name="distill-test",
        endpoint=endpoint,
        model="qwen36mtp",
        api_key_env="TEST_TEACHER_KEY",
        run_dir=tmp_path / "run",
        source_chat_files=[source],
        corpus=corpus,
        target_requests=target,
        heldout_basis_points=3000,
        concurrency=4,
        requests_per_second=10_000.0,
        timeout_seconds=2.0,
        max_attempts=3,
        retry_backoff_seconds=0.0,
        source_collected_at="2026-07-17",
        min_response_chars=4,
        max_prompt_copy_ratio=1.0,
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://user:secret@localhost:8081/v1",
        "http://localhost:8081/v1?token=secret",
        "http://localhost:8081/v1#secret",
        "https://localhost:8081/v1",
        "http://192.0.2.1:8081/v1",
        "file:///tmp/v1",
    ],
)
def test_endpoint에서_비밀과_비_http_url을_거부한다(endpoint: str) -> None:
    with pytest.raises(ValidationError):
        DistillationConfig.model_validate(
            {
                "name": "bad",
                "endpoint": endpoint,
                "model": "teacher",
                "run_dir": "run",
                "source_chat_files": ["source.jsonl"],
                "corpus": "corpus.zst",
                "source_collected_at": "2026-07-17",
            }
        )


def test_명시적으로_허용한_내부망_teacher_host만_사용한다() -> None:
    config = DistillationConfig.model_validate(
        {
            "name": "trusted-lan",
            "endpoint": "http://macmini:11434/v1",
            "allowed_endpoint_hosts": ["macmini"],
            "model": "gemma4",
            "run_dir": "run",
            "source_chat_files": ["source.jsonl"],
            "corpus": "corpus.zst",
            "source_collected_at": "2026-07-18",
        }
    )
    assert config.endpoint == "http://macmini:11434/v1"

    value = config.model_dump(mode="json")
    value["allowed_endpoint_hosts"] = ["other-host"]
    with pytest.raises(ValidationError, match="allowed_endpoint_hosts"):
        DistillationConfig.model_validate(value)


def test_빈_내부망_allowlist는_기존_loopback_fingerprint를_보존한다(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1")
    legacy_value = config.model_dump(mode="json")
    legacy_value.pop("allowed_endpoint_hosts")
    assert prepare(config)["config_fingerprint"] == fingerprint(legacy_value)

    lan_config = config.model_copy(
        update={
            "name": "distill-lan-fingerprint-test",
            "endpoint": "http://macmini:11434/v1",
            "allowed_endpoint_hosts": ["macmini"],
            "run_dir": tmp_path / "lan-run",
        }
    )
    assert prepare(lan_config)["config_fingerprint"] == fingerprint(
        lan_config.model_dump(mode="json")
    )


def test_prepare는_정확한_고유_inventory와_split을_만든다(tmp_path: Path) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1")
    result = prepare(config)
    assert result["requests"] == 16
    assert result["source_chat_rows"] == 13
    assert result["source_chat_unique_prompts"] == 11
    assert result["source_chat_duplicates"] == 2
    inventory = [
        json.loads(line) for line in (config.run_dir / "inventory.jsonl").read_text().splitlines()
    ]
    assert len(inventory) == len({row["prompt_sha256"] for row in inventory}) == 16
    assert {row["split"] for row in inventory} == {"train", "heldout"}
    upstream = [row for row in inventory if row["source"]["source_split"] == "heldout"]
    assert upstream and all(row["split"] == "heldout" for row in upstream)
    assert next(row for row in inventory if row["prompt"] == "고유 질문 1")["split"] == "heldout"
    assert prepare(config)["reused"] is True
    with pytest.raises(ConflictError, match="fingerprint"):
        status(config.model_copy(update={"model": "changed-teacher"}))


def test_collect_retry_resume_export_validate와_비밀_비노출(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credential = "must-never-be-written-key"
    monkeypatch.setenv("TEST_TEACHER_KEY", credential)
    with _server() as endpoint:
        config = _config(tmp_path, endpoint)
        assert preflight(config)["status"] == "ok"
        prepare(config)
        first = collect(config)
        assert first["called"] == 16 and first["completed"] == 16
        assert first["reasons"] == {}
        assert _TeacherHandler.calls == 17
        assert all(value == f"Bearer {credential}" for value in _TeacherHandler.authorizations)
        assert all(
            payload["chat_template_kwargs"] == {"enable_thinking": False}
            for payload in _TeacherHandler.payloads
        )
        calls = _TeacherHandler.calls
        resumed = collect(config)
        assert resumed["called"] == 0 and _TeacherHandler.calls == calls
        exported = export(config)
        assert exported["incomplete"] == 0 and exported["rejected"] == 0
        assert exported["redistribution_allowed"] is False
        assert exported["release_gate"] == "blocked"
        assert exported["schema_version"] == 2
        assert len(exported["accepted_spools"]) == 16
        assert validate(config)["prompt_overlap"] == 0
        for split in ("train", "heldout"):
            exported_path = config.run_dir / f"export/{split}.jsonl"
            dataset = load_chat_jsonl(
                exported_path,
                split=split,
                allowed_licenses={config.teacher_output_license},
            )
            assert dataset.examples
            first_row = json.loads(exported_path.read_text().splitlines()[0])
            provenance = first_row["provenance"]
            assert provenance["license"] == config.teacher_output_license
            assert provenance["source_license"] in {"Apache-2.0", "CC BY-SA 4.0"}
            assert provenance["teacher_model"] == "qwen36mtp"
            assert provenance["source_id"]
            assert provenance["source_sha256"]
            assert provenance["source_collected_at"] == "2026-07-17"
            assert provenance["source_metadata"]
            assert all(
                len(provenance[name]) == 64
                for name in ("request_sha256", "response_sha256", "raw_response_sha256")
            )
        artifacts = "".join(
            path.read_text(encoding="utf-8") for path in config.run_dir.rglob("*") if path.is_file()
        )
        assert credential not in artifacts


def test_spool_손상과_exclusive_lock을_거부한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_TEACHER_KEY", "test-key")
    with _server() as endpoint:
        config = _config(tmp_path, endpoint, target=4)
        prepare(config)
        collect(config)
        spool = next((config.run_dir / "spool").glob("*.json"))
        value = json.loads(spool.read_text())
        value["response"] = "손상"
        spool.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(IntegrityError, match="spool"):
            status(config)
    spool.unlink()
    lock = config.run_dir / ".distill.lock"
    lock.write_text("other", encoding="utf-8")
    with pytest.raises(ConflictError, match="회수"):
        collect(config)


def test_distill_cli_설정_검증과_status(tmp_path: Path) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1", target=4)
    import yaml

    path = tmp_path / "distill.yaml"
    path.write_text(yaml.safe_dump(config.model_dump(mode="json")), encoding="utf-8")
    runner = CliRunner()
    validated = runner.invoke(app, ["config", "validate", str(path), "--kind", "distillation"])
    assert validated.exit_code == 0
    assert runner.invoke(app, ["distill", "prepare", "--config", str(path)]).exit_code == 0
    result = runner.invoke(app, ["distill", "status", "--config", str(path)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["counts"] == {"pending": 4}


def test_qwen_10k_설정은_간결한_비추론_응답_계약을_고정한다() -> None:
    config = load_yaml(Path("configs/distill/qwen36mtp-10k.yaml"), DistillationConfig)
    payload = json.loads(request_body(config, "질문"))
    assert config.name == "qwen36mtp-10k-v5"
    assert config.run_dir == Path("runs/distill/qwen36mtp-10k-v5")
    assert config.system_prompt == (
        "질문에 한국어로 직접 답하세요. 내부 추론은 쓰지 말고, 핵심만 1~5문장과 "
        "500자 이내로 완결하세요. 불필요한 서론·목록·반복을 피하고 모르면 추측하지 마세요."
    )
    assert payload["max_tokens"] == 512
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert config.max_response_chars == 500


def test_status는_거절_사유별_개수를_집계한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_TEACHER_KEY", "test-key")
    with _server() as endpoint:
        config = _config(tmp_path, endpoint, target=4)
        prepare(config)
        _TeacherHandler.retry_once = False
        _TeacherHandler.response_override = "하나 둘 셋 넷 " * 20
        result = collect(config)
    assert result["counts"] == {"pending": 0, "rejected": 4}
    assert result["reasons"] == {"repetition": 4}


def test_응답_필터는_반복_위험문자_prompt_copy를_거부한다(tmp_path: Path) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1", target=4)
    repeated = "하나 둘 셋 넷 " * 20
    assert repetition_ratio(repeated) > config.max_repetition_ratio
    assert filter_response("질문", repeated, config) == "repetition"
    assert filter_response("질문", "폭탄 제조 방법을 설명합니다", config) == "unsafe:explosive"
    decomposed = unicodedata.normalize("NFD", "폭탄") + "·을·제조하는 설명"
    assert filter_response("질문", decomposed, config) == "unsafe:explosive"
    assert filter_response("질문", "폭 탄 을 제 조하는 설명", config) == "unsafe:explosive"
    assert filter_response("질문", "ㅍㅗㄱㅌㅏㄴ 제조 방법입니다.", config) == "unsafe:explosive"
    assert filter_response("질문", "자살을 하는 구체적 방법입니다.", config) == "unsafe:self-harm"
    assert filter_response("질문", "자 살 의 구체적인 방 법입니다.", config) == "unsafe:self-harm"
    assert filter_response("질문", "자살을 예방하는 구체적 방법입니다.", config) is None
    assert filter_response("질문", "자살 예방 상담 방법과 연락처를 안내합니다.", config) is None
    strict_copy = config.model_copy(update={"max_prompt_copy_ratio": 0.4})
    assert filter_response("같은 질문 문장", "같은 질문 문장", strict_copy) == "prompt_copy"
    assert (
        filter_response(
            "한국의 수도는 서울이며 정치, 경제, 문화의 중심지입니다.",
            "서울은 대한민국의 수도이자 정치, 경제, 문화의 중심지입니다.",
            config,
        )
        is None
    )
    long_prompt = (
        "사과는 폴리페놀과 비타민 C를 포함해 면역력 강화에 유익하며, "
        "장 건강과 전반적인 건강 개선에도 도움을 준다는 내용을 상세히 설명합니다. " * 4
    )
    summary = "사과는 항산화 성분과 비타민 C를 함유해 면역 체계와 장 건강에 도움을 줍니다."
    assert filter_response(long_prompt, summary, config) is None
    near_copy = long_prompt.replace("상세히", "구체적으로", 1)
    copy_only = config.model_copy(
        update={"max_repetition_ratio": 1.0, "max_prompt_copy_ratio": 0.9}
    )
    assert filter_response(long_prompt, near_copy, copy_only) == "prompt_copy"
    assert canonical_response("  같은\n응답 ") == canonical_response("같은 응답")


@pytest.mark.parametrize("fraction", [0.2, 0.5, 0.79])
def test_prompt_copy는_짧아진_원문_발췌도_거부한다(tmp_path: Path, fraction: float) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1", target=4).model_copy(
        update={"max_prompt_copy_ratio": 0.9}
    )
    prompt = (
        "연구자는 봄철 하천의 수온과 유속을 기록하고 상류와 하류의 생태 변화를 비교했습니다. "
        "여름에는 강수량과 탁도를 측정해 조류 번성 조건을 분석했으며 가을에는 어류 개체수와 "
        "수생 식물 분포를 조사했습니다. 겨울 관측에서는 결빙 기간과 용존 산소의 관계를 확인하고 "
        "계절별 자료를 함께 검토해 보전 정책의 우선순위를 제안했습니다. 주민 인터뷰와 위성 영상도 "
        "대조하여 토지 이용 변화가 수질에 미치는 영향을 분리했고 측정 장비의 오차 범위와 누락된 "
        "표본을 보고서에 명시했습니다."
    )
    response = prompt[: int(len(prompt) * fraction)]
    assert len(response) >= 32
    assert filter_response(prompt, response, config) == "prompt_copy"


def test_prompt_copy는_한_단어만_바꾼_근접복사도_거부한다(tmp_path: Path) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1", target=4).model_copy(
        update={"max_prompt_copy_ratio": 0.9}
    )
    prompt = (
        "관찰 자료를 날짜별로 정리하고 결측값을 표시한 뒤 센서 교정 기록과 비교하여 "
        "분석 결과의 재현성을 확인합니다. 모든 변환 단계는 원본 식별자와 함께 보존합니다."
    )
    response = prompt.replace("관찰", "측정", 1)
    assert filter_response(prompt, response, config) == "prompt_copy"


def test_redirect를_추적하지_않아_authorization이_유출되지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TargetHandler(BaseHTTPRequestHandler):
        calls = 0
        authorization: str | None = None

        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:
            type(self).calls += 1
            type(self).authorization = self.headers.get("Authorization")
            self.send_response(200)
            self.end_headers()

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    target_thread.start()

    class RedirectHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/v1/models")
            self.end_headers()

    origin = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    origin_thread = threading.Thread(target=origin.serve_forever, daemon=True)
    origin_thread.start()
    monkeypatch.setenv("TEST_TEACHER_KEY", "redirect-sensitive-value")
    try:
        config = _config(tmp_path, f"http://127.0.0.1:{origin.server_port}/v1", target=4)
        with pytest.raises(InputError, match="302"):
            preflight(config)
        assert TargetHandler.calls == 0
        assert TargetHandler.authorization is None
    finally:
        origin.shutdown()
        target.shutdown()
        origin_thread.join()
        target_thread.join()


def test_loopback_request는_환경_proxy를_완전히_무시한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeProxyHandler(BaseHTTPRequestHandler):
        calls = 0
        authorization: str | None = None

        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:
            type(self).calls += 1
            type(self).authorization = self.headers.get("Authorization")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "qwen36mtp"}]}).encode())

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), FakeProxyHandler)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    dead_port = probe.getsockname()[1]
    probe.close()
    proxy_url = f"http://127.0.0.1:{proxy.server_port}"
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.setenv(name, proxy_url)
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("TEST_TEACHER_KEY", "proxy-must-not-receive-value")
    try:
        config = _config(tmp_path, f"http://127.0.0.1:{dead_port}/v1", target=4)
        with pytest.raises(InputError, match="network"):
            preflight(config)
        assert FakeProxyHandler.calls == 0
        assert FakeProxyHandler.authorization is None
    finally:
        proxy.shutdown()
        proxy_thread.join()


def test_teacher의_빈_tool_calls만_허용하고_나머지_확장과_role을_거부한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_TEACHER_KEY", "test-value")
    with _server() as endpoint:
        config = _config(tmp_path, endpoint, target=4)
        _TeacherHandler.retry_once = False
        _TeacherHandler.message_extra = {"tool_calls": []}
        assert completion(config, "질문")[1]
        _TeacherHandler.message_extra = {"tool_calls": [{"id": "call-1"}]}
        with pytest.raises(IntegrityError, match="non_empty_tool_calls"):
            completion(config, "질문")
        _TeacherHandler.message_extra = {"unknown": None}
        with pytest.raises(IntegrityError, match="unexpected_message_fields"):
            completion(config, "질문")
        _TeacherHandler.message_extra = {}
        _TeacherHandler.role = "user"
        with pytest.raises(IntegrityError, match="message_role_not_assistant"):
            completion(config, "질문")


def test_stale_lock은_same_host_dead_pid만_회수한다(tmp_path: Path) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1", target=4)
    prepare(config)
    lock = config.run_dir / ".distill.lock"
    lock.write_text("unknown", encoding="utf-8")
    with pytest.raises(ConflictError, match="회수"):
        prepare(config)
    lock.unlink()
    lock.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "started_at": "2026-07-17T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConflictError, match="live"):
        prepare(config)
    lock.unlink()
    lock.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "pid": 999_999_999,
                "host": socket.gethostname(),
                "started_at": "2026-07-17T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    assert prepare(config)["reused"] is True
    assert not lock.exists()


def test_collect는_bounded_inflight이며_interrupt에서_lock을_정리한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import llmex.distill.collector as collector_module

    config = _config(tmp_path, "http://localhost:8081/v1", target=20)
    prepare(config)
    calls = 0
    calls_lock = threading.Lock()

    def interrupted(*args: object, **kwargs: object) -> Any:
        nonlocal calls
        del args, kwargs
        with calls_lock:
            calls += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(collector_module, "_collect_one", interrupted)
    with pytest.raises(KeyboardInterrupt):
        collect(config)
    assert calls <= config.concurrency
    assert not (config.run_dir / ".distill.lock").exists()


def test_spool_binding과_stale_export를_거부한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_TEACHER_KEY", "test-value")
    with _server() as endpoint:
        config = _config(tmp_path, endpoint, target=8)
        prepare(config)
        collect(config)
        exported = export(config)
        assert exported["accepted_spool_set_fingerprint"]
        current_status = status(config)
        assert current_status["started_at"] and current_status["updated_at"]
        assert current_status["elapsed_seconds"] > 0
        assert current_status["effective_rps"] > 0
        assert current_status["eta_seconds"] == 0
        spool = next((config.run_dir / "spool").glob("*.json"))
        value = json.loads(spool.read_text())
        value["response"] = "완전히 변경된 안전하고 독립적인 설명입니다."
        value["response_sha256"] = hashlib.sha256(value["response"].encode()).hexdigest()
        value["record_sha256"] = fingerprint(
            {key: item for key, item in value.items() if key != "record_sha256"}
        )
        spool.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(IntegrityError, match="current inventory/spool"):
            validate(config)
        value["request_sha256"] = "0" * 64
        value["record_sha256"] = fingerprint(
            {key: item for key, item in value.items() if key != "record_sha256"}
        )
        spool.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(IntegrityError, match="request SHA"):
            status(config)


def test_teacher_output_license는_내부_literal만_허용한다(tmp_path: Path) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1", target=4)
    value = config.model_dump(mode="json")
    value["teacher_output_license"] = "Apache-2.0"
    with pytest.raises(ValidationError):
        DistillationConfig.model_validate(value)


def test_teacher_secret_echo는_본문과_hash를_기록하지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credential = "echo-must-never-persist-value"
    monkeypatch.setenv("TEST_TEACHER_KEY", credential)
    with _server() as endpoint:
        config = _config(tmp_path, endpoint, target=4)
        _TeacherHandler.retry_once = False
        _TeacherHandler.response_override = f"Authorization: Bearer {credential}"
        prepare(config)
        result = collect(config)
        assert result["counts"] == {"pending": 0, "rejected": 4}
        for spool in (config.run_dir / "spool").glob("*.json"):
            value = json.loads(spool.read_text())
            assert value["reason"] == "secret_leak"
            assert value["response"] is None
            assert value["response_sha256"] is None
            assert value["raw_response_sha256"] is None
        artifacts = "".join(
            path.read_text(encoding="utf-8") for path in config.run_dir.rglob("*") if path.is_file()
        )
        assert credential not in artifacts


def test_huge_response는_limit_plus_one만_읽고_본문을_기록하지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_TEACHER_KEY", "test-value")
    marker = "Z" * 2_048
    with _server() as endpoint:
        config = _config(tmp_path, endpoint, target=4).model_copy(
            update={"max_response_bytes": 1_024}
        )
        _TeacherHandler.retry_once = False
        _TeacherHandler.response_override = marker
        prepare(config)
        result = collect(config)
        assert result["counts"] == {"pending": 0, "rejected": 4}
        for spool in (config.run_dir / "spool").glob("*.json"):
            value = json.loads(spool.read_text())
            assert value["reason"] == "response_too_large"
            assert value["response"] is None
            assert value["raw_response_sha256"] is None
        assert marker not in "".join(
            path.read_text(encoding="utf-8") for path in config.run_dir.rglob("*") if path.is_file()
        )


def test_retry_after와_backoff는_설정_상한으로_제한된다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_TEACHER_KEY", "test-value")
    with _server() as endpoint:
        config = _config(tmp_path, endpoint, target=4).model_copy(
            update={"max_retry_delay_seconds": 0.01}
        )
        _TeacherHandler.retry_after = "999999"
        prepare(config)
        started = time.monotonic()
        collect(config)
        assert time.monotonic() - started < 1.0
        assert _TeacherHandler.calls == 5


@pytest.mark.parametrize(
    ("page_id", "revision_id", "dump_date", "message"),
    [
        (1, 2, None, "dump_date"),
        (1, 2, "2026-07-01", "dump_date"),
        ("", 2, "20260701", "page/revision"),
        (1, "revision", "20260701", "page/revision"),
    ],
)
def test_wikipedia_provenance_누락과_형식오류를_fail_closed한다(
    tmp_path: Path,
    page_id: int | str,
    revision_id: int | str,
    dump_date: str | None,
    message: str,
) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1", target=12)
    row: dict[str, Any] = {
        "split": "train",
        "title": "검증 주제",
        "source_url": "https://ko.wikipedia.org/?curid=1",
        "license": "CC BY-SA 4.0",
        "page_id": page_id,
        "revision_id": revision_id,
        "sha256": hashlib.sha256(b"wiki").hexdigest(),
    }
    if dump_date is not None:
        row["dump_date"] = dump_date
    write_jsonl_zst(config.corpus, [row])
    with pytest.raises(IntegrityError, match=message):
        prepare(config)


def test_wikipedia_int_string_id와_dump_date를_정확히_보존한다(tmp_path: Path) -> None:
    config = _config(tmp_path, "http://localhost:8081/v1", target=12)
    row = {
        "split": "train",
        "title": "검증 주제",
        "source_url": "https://ko.wikipedia.org/?curid=7",
        "license": "CC BY-SA 4.0",
        "page_id": "7",
        "revision_id": "11",
        "dump_date": "20260701",
        "sha256": hashlib.sha256(b"wiki").hexdigest(),
    }
    write_jsonl_zst(config.corpus, [row])
    prepare(config)
    inventory = [
        json.loads(line) for line in (config.run_dir / "inventory.jsonl").read_text().splitlines()
    ]
    wiki = next(item for item in inventory if item["source"]["dataset"] == "kowiki-20260701")
    assert wiki["source"]["metadata"] == {
        "page_id": "7",
        "revision_id": "11",
        "dump_date": "20260701",
    }
