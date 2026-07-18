# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import pytest
import yaml
from tokenizers.trainers import BpeTrainer
from typer.testing import CliRunner

from llmex.chat.data import ChatRow, final_user_prompt_sha256, provenance_source_key
from llmex.chat.mixer import preflight_mix, prepare_mix, status_mix, validate_mix
from llmex.chat.runtime import SFTTrainer, _datasets, evaluate_chat, preflight_sft
from llmex.cli import app
from llmex.config import (
    ModelConfig,
    OptimizerConfig,
    SFTConfig,
    SFTMixConfig,
    SFTTeacherSourceConfig,
)
from llmex.errors import ConflictError, IntegrityError, LlmexError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.tokenizer.core import SPECIAL_TOKENS, build_tokenizer
from llmex.train.checkpoint import load_checkpoint


def _source(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _row(
    identifier: str,
    split: str,
    prompt: str,
    answer: str,
    license_name: str,
    source: str,
    *,
    source_sha256: bool = True,
) -> dict[str, object]:
    messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}]
    provenance = {
        "dataset": "teacher" if license_name.startswith("LicenseRef") else "public",
        "source": "synthetic",
        "license": license_name,
        "collected_at": "2026-07-17",
        "source_id": source,
    }
    if source_sha256:
        provenance["source_sha256"] = _source(source)
    basis = {"id": identifier, "messages": messages, "provenance": provenance, "split": split}
    return {"schema_version": 1, **basis, "sha256": fingerprint(basis)}


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _tokenizer(path: Path) -> int:
    path.mkdir()
    tokenizer = build_tokenizer()
    tokenizer.train_from_iterator(
        [
            "<|user|>\n고유 질문과 공유 질문",
            "<|assistant|>\n간결하고 안전한 답변",
            "계절별 하천 관찰 자료를 비교합니다",
        ],
        trainer=BpeTrainer(
            vocab_size=400, special_tokens=list(SPECIAL_TOKENS), show_progress=False
        ),
    )
    tokenizer.save(str(path / "tokenizer.json"))
    manifest = {
        "schema_version": 1,
        "vocab_size_actual": tokenizer.get_vocab_size(),
        "special_token_ids": {token: index for index, token in enumerate(SPECIAL_TOKENS)},
        "artifacts": {"tokenizer.json": {"sha256": sha256_file(path / "tokenizer.json")}},
    }
    (path / "tokenizer-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tokenizer.get_vocab_size()


def _fixture(tmp_path: Path) -> tuple[SFTMixConfig, int]:
    public_train = tmp_path / "public-train.jsonl"
    public_heldout = tmp_path / "public-heldout.jsonl"
    teacher_train = tmp_path / "teacher-train.jsonl"
    teacher_heldout = tmp_path / "teacher-heldout.jsonl"
    public = "Apache-2.0"
    internal = "LicenseRef-LLMEX-Internal-Distillation"
    _write(
        public_train,
        [
            _row("pt-1", "train", "고유 공개 질문", "공개 답변", public, "source-a"),
            _row("pt-2", "train", "공유 질문", "누출 후보", public, "source-b"),
            _row("pt-3", "train", "다른 질문", "source 누출 후보", public, "source-c"),
            _row("pt-4", "train", "중복 질문", "첫 답변", public, "source-d"),
            _row("pt-5", "train", "중복 질문", "둘째 답변", public, "source-d"),
            _row("pt-6", "train", "매우 긴 질문 " * 100, "긴 답변", public, "source-e"),
            _row(
                "pt-7",
                "train",
                "fallback train 질문",
                "fallback train 답변",
                public,
                "source-fallback",
                source_sha256=False,
            ),
            _row(
                "pt-8",
                "train",
                "길이 탈락 heldout와 같은 source의 train 질문",
                "source 예약으로 제외할 답변",
                public,
                "source-long-heldout",
            ),
        ],
    )
    _write(
        public_heldout,
        [
            _row("ph-1", "heldout", "공유   질문", "검증 답변", public, "source-c"),
            _row(
                "ph-2",
                "heldout",
                "fallback heldout 질문",
                "fallback heldout 답변",
                public,
                "source-fallback",
                source_sha256=False,
            ),
            _row(
                "ph-3",
                "heldout",
                "매우 긴 heldout 질문 " * 100,
                "길이 탈락 답변",
                public,
                "source-long-heldout",
            ),
        ],
    )
    _write(
        teacher_train,
        [
            _row("tt-1", "train", "teacher 고유 질문", "teacher 답변", internal, "source-f"),
            _row("tt-2", "train", "공유 질문", "teacher 누출 후보", internal, "source-g"),
        ],
    )
    _write(
        teacher_heldout,
        [_row("th-1", "heldout", "공유\n질문", "teacher 검증", internal, "source-c")],
    )
    tokenizer_dir = tmp_path / "tokenizer"
    vocab = _tokenizer(tokenizer_dir)
    teacher_manifest = tmp_path / "teacher-manifest.json"
    teacher_manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "config_fingerprint": "1" * 64,
                "inventory_fingerprint": "2" * 64,
                "accepted_spool_set_fingerprint": "3" * 64,
                "teacher_output_license": internal,
                "redistribution_allowed": False,
                "release_gate": "blocked",
                "incomplete": 0,
                "counts": {"train": 2, "heldout": 1},
                "sha256": {
                    "train": sha256_file(teacher_train),
                    "heldout": sha256_file(teacher_heldout),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return (
        SFTMixConfig(
            name="synthetic-mix",
            tokenizer_dir=tokenizer_dir,
            public_train_data=public_train,
            public_heldout_data=public_heldout,
            teacher_train_data=teacher_train,
            teacher_heldout_data=teacher_heldout,
            teacher_manifest=teacher_manifest,
            expected_teacher_manifest_sha256=sha256_file(teacher_manifest),
            output_dir=tmp_path / "mixed",
            allowed_licenses=[public, internal],
            max_seq_len=128,
            generation_reserve_tokens=16,
        ),
        vocab,
    )


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _refresh_teacher_binding(config: SFTMixConfig) -> SFTMixConfig:
    teacher = json.loads(config.teacher_manifest.read_text(encoding="utf-8"))
    teacher["counts"] = {
        "train": len(_rows(config.teacher_train_data)),
        "heldout": len(_rows(config.teacher_heldout_data)),
    }
    teacher["sha256"] = {
        "train": sha256_file(config.teacher_train_data),
        "heldout": sha256_file(config.teacher_heldout_data),
    }
    config.teacher_manifest.write_text(json.dumps(teacher, sort_keys=True), encoding="utf-8")
    return config.model_copy(
        update={"expected_teacher_manifest_sha256": sha256_file(config.teacher_manifest)}
    )


def _upstream_manifest(
    path: Path,
    *,
    kind: str,
    train_data: Path,
    heldout_data: Path,
    tokenizer_dir: Path,
) -> None:
    value = {
        "schema_version": 1,
        "kind": kind,
        "outputs": {
            "train": {
                "rows": len(_rows(train_data)),
                "sha256": sha256_file(train_data),
            },
            "heldout": {
                "rows": len(_rows(heldout_data)),
                "sha256": sha256_file(heldout_data),
            },
        },
        "tokenizer_manifest_sha256": sha256_file(tokenizer_dir / "tokenizer-manifest.json"),
        "length_gate": {"max_seq_len": 128, "generation_reserve_tokens": 16},
        "redistribution_allowed": True,
        "release_gate": "not_blocked",
    }
    value["fingerprint"] = fingerprint(value)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def test_mix는_부분_teacher_export를_거부한다(tmp_path: Path) -> None:
    config, _ = _fixture(tmp_path)
    teacher = json.loads(config.teacher_manifest.read_text(encoding="utf-8"))
    teacher["incomplete"] = 1
    config.teacher_manifest.write_text(json.dumps(teacher, sort_keys=True), encoding="utf-8")
    partial = config.model_copy(
        update={"expected_teacher_manifest_sha256": sha256_file(config.teacher_manifest)}
    )

    with pytest.raises(IntegrityError, match="teacher export manifest"):
        preflight_mix(partial)


def test_mix는_legacy_fingerprint를_보존하고_세_원천_manifest를_결속한다(
    tmp_path: Path,
) -> None:
    legacy, _ = _fixture(tmp_path)
    legacy_manifest = preflight_mix(legacy)
    assert legacy_manifest["status"] == "ok"
    legacy_dump = legacy.model_dump(mode="json")
    legacy_dump.pop("public_manifest")
    legacy_dump.pop("expected_public_manifest_sha256")
    legacy_dump.pop("additional_teacher_sources")
    prepare_mix(legacy)
    materialized_legacy = json.loads((legacy.output_dir / "manifest.json").read_text())
    assert materialized_legacy["config_fingerprint"] == fingerprint(legacy_dump)
    assert "public_manifest" not in materialized_legacy
    assert "additional_teacher_manifests" not in materialized_legacy

    public_manifest = tmp_path / "public-manifest.json"
    _upstream_manifest(
        public_manifest,
        kind="sft-capability-remediation-curriculum",
        train_data=legacy.public_train_data,
        heldout_data=legacy.public_heldout_data,
        tokenizer_dir=legacy.tokenizer_dir,
    )
    internal = "LicenseRef-LLMEX-Internal-Distillation"
    gemma_train = tmp_path / "gemma-train.jsonl"
    gemma_heldout = tmp_path / "gemma-heldout.jsonl"
    _write(
        gemma_train,
        [_row("gt-1", "train", "Gemma 고유 질문", "Gemma 답변", internal, "gemma-a")],
    )
    _write(
        gemma_heldout,
        [_row("gh-1", "heldout", "Gemma 검증 질문", "Gemma 검증", internal, "gemma-b")],
    )
    gemma_manifest = tmp_path / "gemma-manifest.json"
    gemma_manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "config_fingerprint": "4" * 64,
                "inventory_fingerprint": "5" * 64,
                "accepted_spool_set_fingerprint": "6" * 64,
                "teacher_output_license": internal,
                "redistribution_allowed": False,
                "release_gate": "blocked",
                "incomplete": 0,
                "counts": {"train": 1, "heldout": 1},
                "sha256": {
                    "train": sha256_file(gemma_train),
                    "heldout": sha256_file(gemma_heldout),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    config = legacy.model_copy(
        update={
            "name": "three-source-mix",
            "output_dir": tmp_path / "three-source-mixed",
            "public_manifest": public_manifest,
            "expected_public_manifest_sha256": sha256_file(public_manifest),
            "additional_teacher_sources": [
                SFTTeacherSourceConfig(
                    name="gemma",
                    train_data=gemma_train,
                    heldout_data=gemma_heldout,
                    manifest=gemma_manifest,
                    expected_manifest_sha256=sha256_file(gemma_manifest),
                )
            ],
        }
    )
    prepare_mix(config)
    manifest = json.loads((config.output_dir / "manifest.json").read_text())
    assert manifest["public_manifest"]["sha256"] == sha256_file(public_manifest)
    assert manifest["additional_teacher_manifests"]["gemma"]["sha256"] == sha256_file(
        gemma_manifest
    )
    assert manifest["inputs"]["teacher-gemma-train"]["rows"] == 1
    assert manifest["inputs"]["teacher-gemma-heldout"]["rows"] == 1
    assert manifest["prompt_overlap"] == 0
    assert manifest["source_sha256_overlap"] == 0

    gemma_value = json.loads(gemma_manifest.read_text())
    gemma_value["counts"]["train"] = 2
    gemma_manifest.write_text(json.dumps(gemma_value, sort_keys=True), encoding="utf-8")
    tampered = config.model_copy(
        update={
            "expected_public_manifest_sha256": sha256_file(public_manifest),
            "additional_teacher_sources": [
                config.additional_teacher_sources[0].model_copy(
                    update={"expected_manifest_sha256": sha256_file(gemma_manifest)}
                )
            ],
        }
    )
    with pytest.raises(IntegrityError, match="teacher export manifest"):
        preflight_mix(tampered)


def test_mix는_assistant_민감_출력만_선필터하고_집계만_공개한다(tmp_path: Path) -> None:
    config, _ = _fixture(tmp_path)
    public = "Apache-2.0"
    internal = "LicenseRef-LLMEX-Internal-Distillation"
    prompt_only_value = "문의 본문 user@example.com, 010-1234-5678, 900101-1234567"
    leaked_email = "private.person@example.com입니다"
    leaked_phone = "010-9876-5432입니다"
    leaked_id = "900101-1234567입니다"
    leaked_credential = "api_key=TopSecretValue123입니다"
    leaked_extra = "계좌 123-456-123456"

    public_train = _rows(config.public_train_data)
    prompt_only = _row(
        "pt-safe-prompt",
        "train",
        prompt_only_value,
        "민감 문자열을 반복하지 않는 안전한 답변",
        public,
        "source-prompt-only",
    )
    multi_turn = _row(
        "pt-email",
        "train",
        "첫 질문",
        "최종 안전 답변",
        public,
        "source-email",
    )
    multi_turn["messages"] = [
        {"role": "system", "content": "system@example.com을 반복하지 마세요"},
        {"role": "user", "content": "첫 질문"},
        {"role": "assistant", "content": f"이전 답변 {leaked_email}"},
        {"role": "user", "content": "두 번째 질문"},
        {"role": "assistant", "content": "최종 안전 답변"},
    ]
    multi_basis = {key: multi_turn[key] for key in ("id", "messages", "provenance", "split")}
    multi_turn["sha256"] = fingerprint(multi_basis)
    public_train.extend(
        [
            prompt_only,
            multi_turn,
            _row(
                "pt-extra",
                "train",
                "추가 규칙 질문",
                leaked_extra,
                public,
                "source-extra",
            ),
            _row(
                "pt-filter-order",
                "train",
                "아주 긴 민감 질문 " * 100,
                leaked_credential,
                public,
                "source-filter-order",
            ),
            _row(
                "pt-safe-reserved",
                "train",
                "민감 heldout와 source만 같은 안전한 질문",
                "안전한 train 답변",
                public,
                "source-sensitive-heldout",
            ),
            _row(
                "pt-safe-length-reserved",
                "train",
                "길이 제한 heldout와 source만 같은 안전한 질문",
                "안전한 길이 제한 train 답변",
                public,
                "source-length-heldout",
            ),
            _row(
                "pt-secret-boundary",
                "train",
                "secret 경계 오탐 질문",
                "notsecret=abcdefgh 및 xapi_key=abcdefgh는 일반 문자열입니다",
                public,
                "source-secret-boundary",
            ),
        ]
    )
    _write(config.public_train_data, public_train)
    public_heldout = _rows(config.public_heldout_data)
    public_heldout.append(
        _row(
            "ph-phone",
            "heldout",
            "전화 출력 질문",
            leaked_phone,
            public,
            "source-sensitive-heldout",
        )
    )
    public_heldout.append(
        _row(
            "ph-scan-limit",
            "heldout",
            "assistant 검색 길이 제한 질문",
            "가" * 65_537,
            public,
            "source-length-heldout",
        )
    )
    _write(config.public_heldout_data, public_heldout)

    teacher_train = _rows(config.teacher_train_data)
    teacher_train.append(
        _row(
            "tt-id",
            "train",
            "식별자 출력 질문",
            leaked_id,
            internal,
            "source-id",
        )
    )
    _write(config.teacher_train_data, teacher_train)
    teacher_heldout = _rows(config.teacher_heldout_data)
    teacher_heldout.append(
        _row(
            "th-secret",
            "heldout",
            "비밀 출력 질문",
            leaked_credential,
            internal,
            "source-secret",
        )
    )
    _write(config.teacher_heldout_data, teacher_heldout)
    raw_config = _refresh_teacher_binding(config).model_dump(mode="json")
    raw_config["extra_sensitive_output_patterns"] = [
        {"name": "bank-account", "pattern": r"\b\d\d\d-\d\d\d-\d\d\d\d\d\d\b"}
    ]
    config = SFTMixConfig.model_validate(raw_config)

    preflight = preflight_mix(config)
    counts = preflight["sensitive_output_filter"]
    assert counts == {
        "total": 7,
        "by_source": {"public": 5, "teacher": 2},
        "by_split": {"heldout": 3, "train": 4},
        "by_rule": {
            "api-key-secret-assignment": 2,
            "assistant-content-length-limit": 1,
            "bank-account": 1,
            "email-address": 1,
            "korean-mobile-phone": 1,
            "korean-resident-registration-number": 1,
        },
    }
    selection = cast(dict[str, object], preflight["selection"])
    excluded = cast(dict[str, int], selection["excluded"])
    assert excluded["sensitive_assistant_output"] == 7
    assert excluded["prompt_too_long"] == 2

    result = prepare_mix(config)
    assert result["reused"] is False
    manifest_text = (config.output_dir / "manifest.json").read_text(encoding="utf-8")
    public_result = (config.output_dir / "train.jsonl").read_text(encoding="utf-8")
    assert prompt_only_value in public_result
    assert "민감 heldout와 source만 같은 안전한 질문" in public_result
    assert "길이 제한 heldout와 source만 같은 안전한 질문" in public_result
    assert "notsecret=abcdefgh 및 xapi_key=abcdefgh" in public_result
    for leaked in (leaked_email, leaked_phone, leaked_id, leaked_credential, leaked_extra):
        assert leaked not in manifest_text
        assert leaked not in json.dumps(preflight, ensure_ascii=False)

    yaml_path = tmp_path / "sensitive-mix.yaml"
    yaml_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    cli = CliRunner().invoke(app, ["sft", "preflight-mix", "--config", str(yaml_path)])
    assert cli.exit_code == 0
    assert '"total": 7' in cli.stdout
    for leaked in (leaked_email, leaked_phone, leaked_id, leaked_credential, leaked_extra):
        assert leaked not in cli.stdout


@pytest.mark.parametrize(
    "rules",
    [
        [{"name": "invalid-regex", "pattern": "["}],
        [{"name": "catastrophic-backtracking", "pattern": "(a+)+$"}],
        [{"name": "too-long", "pattern": "a" * 257}],
        [
            {"name": "same-name", "pattern": "foo"},
            {"name": "same-name", "pattern": "bar"},
        ],
        [
            {"name": "first-rule", "pattern": "foo"},
            {"name": "second-rule", "pattern": "foo"},
        ],
        [{"name": "email-address", "pattern": "foo"}],
        [{"name": "assistant-content-length-limit", "pattern": "foo"}],
        [
            {
                "name": "builtin-copy",
                "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            }
        ],
        [{"name": "valid-name", "pattern": "foo", "unknown": True}],
    ],
)
def test_mix_추가_민감_정규식은_strict하고_중복될_수_없다(
    tmp_path: Path, rules: list[dict[str, object]]
) -> None:
    config, _ = _fixture(tmp_path)
    raw = config.model_dump(mode="json")
    raw["extra_sensitive_output_patterns"] = rules
    with pytest.raises(ValueError):
        SFTMixConfig.model_validate(raw)


def test_mix는_split_누출_중복_길이를_제외하고_release를_계승한다(tmp_path: Path) -> None:
    config, _ = _fixture(tmp_path)
    preflight = preflight_mix(config)
    assert preflight["release_gate"] == "blocked"
    result = prepare_mix(config)
    assert result["reused"] is False
    assert prepare_mix(config)["reused"] is True
    assert status_mix(config)["status"] == "ready"
    assert validate_mix(config)["status"] == "ok"
    manifest = json.loads((config.output_dir / "manifest.json").read_text())
    excluded = manifest["selection"]["excluded"]
    assert excluded["heldout_prompt_from_train"] == 2
    assert excluded["heldout_source_from_train"] == 3
    assert excluded["duplicate_source_prompt"] == 1
    assert excluded["heldout_prompt_duplicate"] == 1
    assert excluded["prompt_too_long"] + excluded.get("sequence_too_long", 0) == 2
    assert manifest["redistribution_allowed"] is False
    assert manifest["release_gate"] == "blocked"
    assert manifest["distribution"]["licenses"]["LicenseRef-LLMEX-Internal-Distillation"]["count"]

    train = [
        ChatRow.model_validate(json.loads(line))
        for line in (config.output_dir / "train.jsonl").read_text().splitlines()
    ]
    heldout = [
        ChatRow.model_validate(json.loads(line))
        for line in (config.output_dir / "heldout.jsonl").read_text().splitlines()
    ]
    assert not (
        {final_user_prompt_sha256(row.messages) for row in train}
        & {final_user_prompt_sha256(row.messages) for row in heldout}
    )
    assert not (
        {row.provenance.source_sha256 for row in train}
        & {row.provenance.source_sha256 for row in heldout}
    )


def test_mix는_source_id가_없는_public을_행별로_보존하고_teacher_원행만_격리한다(
    tmp_path: Path,
) -> None:
    config, _ = _fixture(tmp_path)
    baseline = preflight_mix(config)
    public = "Apache-2.0"
    internal = "LicenseRef-LLMEX-Internal-Distillation"

    def public_without_identity(identifier: str, split: str, prompt: str) -> dict[str, object]:
        row = _row(
            identifier,
            split,
            prompt,
            f"{prompt} 답변",
            public,
            "ignored-source-id",
            source_sha256=False,
        )
        provenance = cast(dict[str, object], row["provenance"])
        provenance.pop("source_id")
        provenance["dataset"] = "pilot-public"
        provenance["source"] = "shared-jsonl"
        basis = {key: row[key] for key in ("id", "messages", "provenance", "split")}
        row["sha256"] = fingerprint(basis)
        return row

    public_rows = [
        public_without_identity("pilot-a", "train", "pilot 공개 질문 A"),
        public_without_identity("pilot-b", "train", "pilot 공개 질문 B"),
        public_without_identity("pilot-c", "train", "pilot 공개 질문 C"),
    ]
    linked_public_sha = cast(str, public_rows[1]["sha256"])
    _write(config.public_train_data, [*_rows(config.public_train_data), *public_rows])
    public_heldout = public_without_identity("pilot-heldout", "heldout", "pilot 공개 heldout 질문")
    _write(config.public_heldout_data, [*_rows(config.public_heldout_data), public_heldout])

    teacher_link = _row(
        "teacher-linked-heldout",
        "heldout",
        "teacher가 결속한 pilot B 질문",
        "teacher heldout 답변",
        internal,
        "teacher-linked",
    )
    teacher_provenance = cast(dict[str, object], teacher_link["provenance"])
    teacher_provenance["source_sha256"] = linked_public_sha
    teacher_basis = {key: teacher_link[key] for key in ("id", "messages", "provenance", "split")}
    teacher_link["sha256"] = fingerprint(teacher_basis)
    _write(
        config.teacher_heldout_data,
        [*_rows(config.teacher_heldout_data), teacher_link],
    )
    config = _refresh_teacher_binding(config)

    preflight = preflight_mix(config)
    baseline_selection = cast(dict[str, object], baseline["selection"])
    selection = cast(dict[str, object], preflight["selection"])
    assert selection["selected_train"] == cast(int, baseline_selection["selected_train"]) + 2
    assert selection["selected_heldout"] == cast(int, baseline_selection["selected_heldout"]) + 2

    assert prepare_mix(config)["reused"] is False
    assert prepare_mix(config)["reused"] is True
    train = [
        ChatRow.model_validate(json.loads(line))
        for line in (config.output_dir / "train.jsonl").read_text().splitlines()
    ]
    heldout = [
        ChatRow.model_validate(json.loads(line))
        for line in (config.output_dir / "heldout.jsonl").read_text().splitlines()
    ]
    train_text = "\n".join(message.content for row in train for message in row.messages)
    assert "pilot 공개 질문 A" in train_text
    assert "pilot 공개 질문 B" not in train_text
    assert "pilot 공개 질문 C" in train_text

    expected_identity = {
        cast(str, public_rows[0]["sha256"]),
        cast(str, public_rows[2]["sha256"]),
    }
    selected_public = [
        row
        for row in train
        if any(
            message.content in {"pilot 공개 질문 A", "pilot 공개 질문 C"}
            for message in row.messages
        )
    ]
    assert {row.provenance.source_sha256 for row in selected_public} == expected_identity
    assert {row.provenance.source_id for row in selected_public} == {"pilot-a", "pilot-c"}
    assert not (
        {provenance_source_key(row.provenance) for row in train}
        & {provenance_source_key(row.provenance) for row in heldout}
    )
    manifest = json.loads((config.output_dir / "manifest.json").read_text())
    assert manifest["source_sha256_overlap"] == 0
    assert manifest["prompt_overlap"] == 0
    assert validate_mix(config)["status"] == "ok"


def test_mix_manifest_tamper와_cli를_실패_폐쇄한다(tmp_path: Path) -> None:
    config, _ = _fixture(tmp_path)
    yaml_path = tmp_path / "mix.yaml"
    yaml_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    runner = CliRunner()
    for command in ("preflight-mix", "prepare-mix", "status-mix", "validate-mix"):
        assert runner.invoke(app, ["sft", command, "--config", str(yaml_path)]).exit_code == 0
    output_manifest = config.output_dir / "manifest.json"
    original_output = output_manifest.read_text()
    damaged_output = json.loads(original_output)
    damaged_output["fingerprint"] = "0" * 64
    output_manifest.write_text(json.dumps(damaged_output), encoding="utf-8")
    with pytest.raises(IntegrityError, match="현재 입력/config"):
        validate_mix(config)
    output_manifest.write_text(original_output, encoding="utf-8")
    teacher_rows = [json.loads(line) for line in config.teacher_train_data.read_text().splitlines()]
    teacher_rows[0]["messages"][-1]["content"] = "공모된 변조 답변"
    basis = {key: teacher_rows[0][key] for key in ("id", "messages", "provenance", "split")}
    teacher_rows[0]["sha256"] = fingerprint(basis)
    _write(config.teacher_train_data, teacher_rows)
    teacher = json.loads(config.teacher_manifest.read_text())
    teacher["sha256"]["train"] = sha256_file(config.teacher_train_data)
    config.teacher_manifest.write_text(json.dumps(teacher), encoding="utf-8")
    with pytest.raises(IntegrityError, match="teacher export manifest"):
        preflight_mix(config)

    teacher["inventory_fingerprint"] = "Z" * 64
    config.teacher_manifest.write_text(json.dumps(teacher), encoding="utf-8")
    nonhex = config.model_copy(
        update={"expected_teacher_manifest_sha256": sha256_file(config.teacher_manifest)}
    )
    with pytest.raises(IntegrityError, match="teacher export manifest"):
        preflight_mix(nonhex)


def test_prepare_mix는_동시_실행과_부분_publish를_실패_폐쇄한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _ = _fixture(tmp_path)
    import llmex.chat.mixer as mixer

    entered = threading.Event()
    release = threading.Event()
    original = mixer._material

    def blocked_material(
        value: SFTMixConfig,
    ) -> tuple[bytes, bytes, dict[str, object]]:
        entered.set()
        assert release.wait(timeout=5)
        return original(value)

    monkeypatch.setattr(mixer, "_material", blocked_material)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(prepare_mix, config)
        assert entered.wait(timeout=5)
        lock_name, staging_prefix = mixer._publish_names(config)
        assert (config.output_dir.parent / lock_name).is_file()
        assert not config.output_dir.exists()
        second = pool.submit(prepare_mix, config)
        try:
            second_result: dict[str, object] | None = second.result(timeout=5)
            second_error: BaseException | None = None
        except BaseException as exc:
            second_result = None
            second_error = exc
        release.set()
        first_result = first.result(timeout=5)

    assert first_result["reused"] is False
    assert second_result is None
    assert isinstance(second_error, ConflictError)
    assert isinstance(second_error, LlmexError)
    assert validate_mix(config)["status"] == "ok"
    assert not list(config.output_dir.parent.glob(f"{staging_prefix}*"))
    assert not (config.output_dir / ".sft-mix.lock").exists()

    for name in ("train.jsonl", "heldout.jsonl", "manifest.json"):
        (config.output_dir / name).unlink()
    config.output_dir.rmdir()
    original_replace = mixer.os.replace

    def fail_directory_publish(source: str | Path, destination: str | Path) -> None:
        if Path(destination) == config.output_dir:
            raise FileNotFoundError("의도한 directory publish 중단")
        original_replace(source, destination)

    monkeypatch.setattr(mixer.os, "replace", fail_directory_publish)
    with pytest.raises(IntegrityError, match="publish"):
        prepare_mix(config)
    assert not config.output_dir.exists()
    assert not list(config.output_dir.parent.glob(f"{staging_prefix}*"))

    monkeypatch.setattr(mixer.os, "replace", original_replace)
    stale = config.output_dir.parent / f"{staging_prefix}stale"
    stale.mkdir()
    with pytest.raises(ConflictError, match="staging"):
        prepare_mix(config)
    stale.rmdir()
    assert prepare_mix(config)["reused"] is False
    assert prepare_mix(config)["reused"] is True


def test_runtime은_prompt와_source_cross_split을_차단한다(tmp_path: Path) -> None:
    config, vocab = _fixture(tmp_path)
    prepare_mix(config)
    sft = SFTConfig(
        name="mix-runtime",
        model=ModelConfig(
            name="tiny",
            vocab_size=vocab,
            max_seq_len=128,
            n_layers=1,
            d_model=16,
            n_heads=2,
            n_kv_heads=1,
            ffn_hidden_size=32,
            dropout=0.0,
        ),
        tokenizer_dir=config.tokenizer_dir,
        train_data=config.output_dir / "train.jsonl",
        heldout_data=config.output_dir / "heldout.jsonl",
        source_manifest=config.output_dir / "manifest.json",
        expected_source_manifest_sha256=sha256_file(config.output_dir / "manifest.json"),
        run_dir=tmp_path / "run",
        allowed_licenses=config.allowed_licenses,
        device="cpu",
        sequence_length=128,
        micro_batch_size=1,
        max_steps=1,
        validation_interval=1,
        validation_batches=1,
        checkpoint_interval=1,
        optimizer=OptimizerConfig(learning_rate=0.01, min_learning_rate=0.001),
        max_new_tokens=2,
    )
    missing_pin = sft.model_dump(mode="json")
    missing_pin.pop("expected_source_manifest_sha256")
    with pytest.raises(ValueError, match="expected_source_manifest_sha256"):
        SFTConfig.model_validate(missing_pin)
    trainer = SFTTrainer(sft)
    assert preflight_sft(sft)["release_gate"] == "blocked"
    with pytest.raises(IntegrityError, match="sequence 길이"):
        SFTTrainer(sft.model_copy(update={"sequence_length": 4}))
    tampered_manifest = tmp_path / "tokenizer-tampered-manifest.json"
    tampered = json.loads((config.output_dir / "manifest.json").read_text())
    tampered["tokenizer_manifest_sha256"] = "0" * 64
    tampered_manifest.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(IntegrityError, match="source manifest"):
        preflight_sft(sft.model_copy(update={"source_manifest": tampered_manifest}))

    forged_manifest = tmp_path / "forged-lower-length-manifest.json"
    forged = json.loads((config.output_dir / "manifest.json").read_text())
    forged["length_gate"]["max_seq_len"] = 4
    forged["fingerprint"] = fingerprint(
        {key: value for key, value in forged.items() if key != "fingerprint"}
    )
    forged_manifest.write_text(
        json.dumps(forged, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(IntegrityError, match="source manifest"):
        SFTTrainer(sft.model_copy(update={"source_manifest": forged_manifest}))
    stale_fingerprint = dict(forged)
    stale_fingerprint["length_gate"] = dict(forged["length_gate"])
    stale_fingerprint["length_gate"]["max_seq_len"] = 5
    forged_manifest.write_text(
        json.dumps(stale_fingerprint, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(IntegrityError, match="source manifest"):
        SFTTrainer(
            sft.model_copy(
                update={
                    "source_manifest": forged_manifest,
                    "expected_source_manifest_sha256": sha256_file(forged_manifest),
                }
            )
        )
    forged_manifest.write_text(
        json.dumps(forged, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    forged_config = sft.model_copy(
        update={
            "source_manifest": forged_manifest,
            "expected_source_manifest_sha256": sha256_file(forged_manifest),
            "sequence_length": 4,
        }
    )
    with pytest.raises(IntegrityError, match="sequence 길이"):
        SFTTrainer(forged_config)
    result = trainer.run()
    checkpoint = Path(str(result["checkpoint"]))
    payload = load_checkpoint(checkpoint, trainer.fingerprints, supported_schema_versions={2})
    assert payload["redistribution_allowed"] is False
    assert payload["release_gate"] == "blocked"
    data_manifest = json.loads((sft.run_dir / "data-manifest.json").read_text())
    assert data_manifest["release_gate"] == "blocked"
    evaluation = evaluate_chat(sft, checkpoint)
    assert evaluation["redistribution_allowed"] is False
    assert evaluation["release_gate"] == "blocked"

    heldout_rows = (config.output_dir / "heldout.jsonl").read_text().splitlines()
    leaked = next(
        json.loads(line)
        for line in heldout_rows
        if "source_sha256" in json.loads(line)["provenance"]
    )
    leaked["split"] = "train"
    basis = {key: leaked[key] for key in ("id", "messages", "provenance", "split")}
    leaked["sha256"] = fingerprint(basis)
    _write(tmp_path / "leaked-train.jsonl", [leaked])
    with pytest.raises(IntegrityError, match="prompt 누출"):
        _datasets(
            sft.model_copy(
                update={"train_data": tmp_path / "leaked-train.jsonl", "source_manifest": None}
            )
        )

    safe_train = json.loads((config.output_dir / "train.jsonl").read_text().splitlines()[0])
    safe_train["provenance"]["source_sha256"] = leaked["provenance"]["source_sha256"]
    basis = {key: safe_train[key] for key in ("id", "messages", "provenance", "split")}
    safe_train["sha256"] = fingerprint(basis)
    _write(tmp_path / "source-leaked-train.jsonl", [safe_train])
    with pytest.raises(IntegrityError, match="source identity 누출"):
        _datasets(
            sft.model_copy(
                update={
                    "train_data": tmp_path / "source-leaked-train.jsonl",
                    "source_manifest": None,
                }
            )
        )

    fallback_train = json.loads((config.output_dir / "train.jsonl").read_text().splitlines()[0])
    fallback_heldout = json.loads(heldout_rows[0])
    for row in (fallback_train, fallback_heldout):
        row["provenance"].pop("source_sha256", None)
        row["provenance"].update(
            {"dataset": "same-dataset", "source": "same-source", "source_id": "same-id"}
        )
        basis = {key: row[key] for key in ("id", "messages", "provenance", "split")}
        row["sha256"] = fingerprint(basis)
    _write(tmp_path / "fallback-train.jsonl", [fallback_train])
    _write(tmp_path / "fallback-heldout.jsonl", [fallback_heldout])
    with pytest.raises(IntegrityError, match="source identity 누출"):
        _datasets(
            sft.model_copy(
                update={
                    "train_data": tmp_path / "fallback-train.jsonl",
                    "heldout_data": tmp_path / "fallback-heldout.jsonl",
                    "source_manifest": None,
                }
            )
        )
