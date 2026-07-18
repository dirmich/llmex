"""Qwen·Gemma teacher용 영어·일본어 대화/번역 prompt inventory."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from llmex.chat.data import ChatRow, Message, Provenance
from llmex.errors import ConflictError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file

_TASKS = ("conversation-en", "conversation-ja", "ko-en", "en-ko", "ko-ja", "ja-ko")
_TEACHERS = ("qwen", "gemma")
_COLLECTED_AT = "2026-07-18"


def _prompt(
    teacher: Literal["qwen", "gemma"],
    task: str,
    index: int,
    split: Literal["train", "heldout"],
) -> str:
    serial = index + (10_000 if split == "heldout" else 1_000)
    names_ko = ("민준", "서연", "도윤", "하린", "지호", "수아", "현우", "나은")
    names_en = ("Alex", "Jamie", "Morgan", "Taylor", "Casey", "Riley", "Jordan", "Avery")
    names_ja = ("葵", "蓮", "陽菜", "湊", "結衣", "悠真", "凛", "蒼")
    activities_en = ("reading", "walking", "cooking", "drawing", "gardening", "cycling")
    activities_ja = ("読書", "散歩", "料理", "絵を描くこと", "園芸", "サイクリング")
    places_ko = ("도서관", "공원", "카페", "미술관", "시장", "강변")
    places_en = ("library", "park", "café", "museum", "market", "riverside")
    places_ja = ("図書館", "公園", "カフェ", "美術館", "市場", "川辺")
    k = index % 8
    p = index % 6
    quantity = 2 + index % 17
    hour = 8 + index % 11
    if task == "conversation-en":
        lead = "Answer" if teacher == "qwen" else "Reply"
        return (
            f"{lead} naturally in English in one or two sentences. "
            f"I am {names_en[k]}; after finishing item {serial}, I am relaxing by "
            f"{activities_en[p]}. Continue the conversation warmly."
        )
    if task == "conversation-ja":
        lead = (
            "自然な日本語で一、二文で答えてください"
            if teacher == "qwen"
            else "自然な日本語で短く返事をしてください"
        )
        return (
            f"{lead}。私は{names_ja[k]}です。用事{serial}を終えて、"
            f"今は{activities_ja[p]}を楽しんでいます。会話を優しく続けてください。"
        )
    if task == "ko-en":
        lead = (
            "자연스러운 영어로만 번역하세요"
            if teacher == "qwen"
            else "다음 문장을 자연스러운 영어 한 문장으로 옮기세요"
        )
        return (
            f"{lead}: {names_ko[k]}은 {hour}시에 {places_ko[p]}에서 책 {quantity}권을 "
            f"받기로 했습니다. 확인 번호는 {serial}입니다."
        )
    if task == "en-ko":
        lead = (
            "Translate naturally into Korean only"
            if teacher == "qwen"
            else "Give only a natural Korean translation"
        )
        return (
            f"{lead}: {names_en[k]} will meet us at the {places_en[p]} at {hour}:00 "
            f"with {quantity} notebooks. The reference number is {serial}."
        )
    if task == "ko-ja":
        lead = (
            "자연스러운 일본어로만 번역하세요"
            if teacher == "qwen"
            else "다음 문장을 자연스러운 일본어 한 문장으로 옮기세요"
        )
        return (
            f"{lead}: {names_ko[k]}은 오후 {hour}시에 {places_ko[p]}에서 음료 {quantity}잔을 "
            f"준비합니다. 예약 번호는 {serial}입니다."
        )
    if task == "ja-ko":
        lead = (
            "自然な韓国語に翻訳し、訳文だけ答えてください"
            if teacher == "qwen"
            else "次の文を自然な韓国語一文に訳してください"
        )
        return (
            f"{lead}。{names_ja[k]}は{hour}時に{places_ja[p]}でノートを{quantity}冊受け取ります。"
            f"予約番号は{serial}です。"
        )
    raise ValueError(f"지원하지 않는 다국어 task입니다: {task}")


def _row(
    teacher: Literal["qwen", "gemma"],
    task: str,
    index: int,
    split: Literal["train", "heldout"],
) -> ChatRow:
    identifier = f"multilingual-{teacher}-{split}-{task}-{index:05d}"
    prompt = _prompt(teacher, task, index, split)
    source_sha256 = fingerprint(
        {"teacher_pool": teacher, "task": task, "split": split, "prompt": prompt}
    )
    provenance = Provenance(
        dataset="llmex-multilingual-teacher-prompts-v1",
        source="repository-authored-prompt-inventory",
        license="MIT",
        collected_at=_COLLECTED_AT,
        source_id=identifier,
        source_sha256=source_sha256,
        source_metadata={"teacher_pool": teacher, "task": task},
    )
    messages = [
        Message(role="user", content=prompt),
        Message(role="assistant", content="teacher 응답 수집용 prompt이며 학습 label이 아닙니다."),
    ]
    basis = {
        "id": identifier,
        "messages": [message.model_dump() for message in messages],
        "provenance": provenance.model_dump(exclude_none=True),
        "split": split,
    }
    return ChatRow(
        schema_version=1,
        id=identifier,
        split=split,
        messages=messages,
        provenance=provenance,
        sha256=fingerprint(basis),
    )


def _payload(teacher: Literal["qwen", "gemma"], train_rows: int, heldout_rows: int) -> bytes:
    split_counts: tuple[tuple[Literal["train", "heldout"], int], ...] = (
        ("train", train_rows),
        ("heldout", heldout_rows),
    )
    rows = [
        _row(teacher, task, index, split)
        for split, count in split_counts
        for task in _TASKS
        for index in range(count)
    ]
    return "".join(
        json.dumps(
            row.model_dump(exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    ).encode("utf-8")


def prepare_multilingual_prompts(
    output_dir: Path, *, train_rows_per_task: int = 150, heldout_rows_per_task: int = 30
) -> dict[str, object]:
    """두 teacher에 겹치지 않는 결정적 prompt inventory를 게시한다."""
    if train_rows_per_task < 1 or heldout_rows_per_task < 1:
        raise IntegrityError("다국어 task별 train/heldout 행 수는 1 이상이어야 합니다")
    payloads = {
        teacher: _payload(teacher, train_rows_per_task, heldout_rows_per_task)
        for teacher in _TEACHERS
    }
    paths = {teacher: output_dir / f"{teacher}.jsonl" for teacher in _TEACHERS}
    manifest_path = output_dir / "manifest.json"
    expected = [*paths.values(), manifest_path]
    if any(path.exists() for path in expected):
        if not all(path.is_file() for path in expected):
            raise ConflictError("부분 다국어 prompt inventory가 발견되었습니다")
        if any(path.read_bytes() != payloads[teacher] for teacher, path in paths.items()):
            raise ConflictError("기존 다국어 prompt inventory가 현재 설정과 다릅니다")
        return json.loads(manifest_path.read_text(encoding="utf-8")) | {"reused": True}

    output_dir.mkdir(parents=True, exist_ok=True)
    for teacher, path in paths.items():
        path.write_bytes(payloads[teacher])
    manifest: dict[str, object] = {
        "schema_version": 1,
        "kind": "multilingual-teacher-prompt-inventory",
        "tasks": list(_TASKS),
        "rows_per_teacher": (train_rows_per_task + heldout_rows_per_task) * len(_TASKS),
        "split_rows_per_teacher": {
            "train": train_rows_per_task * len(_TASKS),
            "heldout": heldout_rows_per_task * len(_TASKS),
        },
        "outputs": {
            teacher: {"path": str(path), "sha256": hashlib.sha256(payloads[teacher]).hexdigest()}
            for teacher, path in paths.items()
        },
        "prompt_overlap": 0,
        "license": "MIT",
    }
    manifest["fingerprint"] = fingerprint(manifest)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    if sha256_file(paths["qwen"]) == sha256_file(paths["gemma"]):
        raise IntegrityError("두 teacher prompt inventory가 분리되지 않았습니다")
    return manifest | {"reused": False}
