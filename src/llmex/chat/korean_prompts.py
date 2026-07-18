"""Gemma teacher용 한국어 자연대화 prompt inventory."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from llmex.chat.data import ChatRow, Message, Provenance, ResponseQualityContract
from llmex.errors import ConflictError, IntegrityError
from llmex.fingerprint import fingerprint

_CATEGORIES = (
    "greeting",
    "emotion-support",
    "everyday",
    "planning",
    "advice",
    "preference",
    "reflection",
    "brainstorming",
    "writing",
    "uncertainty",
)
_COLLECTED_AT = "2026-07-18"

_KOREAN_HOURS = {
    9: "아홉",
    10: "열",
    11: "열한",
    12: "열두",
    13: "오후 한",
    14: "오후 두",
    15: "오후 세",
    16: "오후 네",
}


def _response_quality(category: str, prompt_index: int) -> ResponseQualityContract:
    combination_index = (prompt_index * 641) % 2048
    d = (combination_index // 64) % 4
    c = (combination_index // 256) % 8
    timing = ("오늘", "내일", "이번 주", "이번 주말")[d]
    if category == "writing":
        hour = 9 + c
        return ResponseQualityContract(
            mode="direct-message",
            target_language="ko",
            max_sentences=1,
            required_numbers=[[str(hour), _KOREAN_HOURS[hour]]],
            required_terms=[[timing], ["도착"]],
        )
    if category == "uncertainty":
        return ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3)
    return ResponseQualityContract(mode="conversation", target_language="ko", max_sentences=3)


def _companion_particle(value: str) -> str:
    """마지막 한글 음절의 받침에 맞는 공동격 조사를 붙인다."""
    last = value[-1]
    has_batchim = "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 != 0
    return f"{value}{'과' if has_batchim else '와'}"


def _natural_prompt(category: str, index: int) -> str:
    """큰 일련번호와 조사 오류 없이 의미 조합으로 고유한 prompt를 만든다."""
    names = ("민준", "서연", "도윤", "하린", "지호", "수아", "현우", "나은")
    activities = ("독서", "산책", "요리", "그림 그리기", "정리", "운동", "영화 감상", "화분 돌보기")
    activity_objects = (
        "독서를",
        "산책을",
        "요리를",
        "그림 그리기를",
        "정리를",
        "운동을",
        "영화 감상을",
        "화분 돌보기를",
    )
    activity_sites = (
        "도서관",
        "산책로",
        "공유 주방",
        "화실",
        "공유 작업실",
        "체육관",
        "소극장",
        "원예 교실",
    )
    places = ("도서관", "공원", "카페", "미술관", "시장", "강변", "동네 서점", "집")
    feelings = (
        "뿌듯해요",
        "조금 지쳤어요",
        "설레요",
        "마음이 복잡해요",
        "후련해요",
        "긴장돼요",
        "차분해졌어요",
        "조금 아쉬워요",
    )
    situations = (
        "새로운 일을 시작해서",
        "오랜 일을 마쳐서",
        "약속을 앞두고",
        "계획이 바뀌어서",
        "좋은 소식을 들어서",
        "실수한 일이 생각나서",
        "혼자 쉴 시간이 생겨서",
        "선택할 일이 많아서",
    )
    moments = (
        "아침에",
        "점심 무렵",
        "오후에",
        "저녁에",
        "퇴근 후",
        "수업 후",
        "해 질 무렵",
        "늦은 오후에",
    )
    approaches = (
        "잠깐",
        "30분 정도",
        "한 시간 동안",
        "친구와",
        "혼자",
        "오랜만에",
        "처음으로",
        "느긋하게",
    )
    schedules = (
        "아침에",
        "점심 후",
        "오후에",
        "저녁에",
        "퇴근 후",
        "수업 후",
        "해 질 무렵",
        "늦은 오후에",
    )
    blockers = (
        "퇴근하면 피곤해서",
        "일정이 들쭉날쭉해서",
        "한 번에 잘하려고 해서",
        "시작할 시간을 정하지 않아서",
        "준비가 번거롭게 느껴져서",
        "다른 일에 먼저 손이 가서",
        "목표를 너무 크게 잡아서",
        "며칠 쉬면 의욕이 떨어져서",
    )
    meeting_areas = ("시청 근처", "학교 앞", "강변", "역 근처", "동네", "주택가", "상가", "공원 옆")
    combination_index = (index * 641) % 2048
    a = combination_index % 8
    b = (combination_index // 8) % 8
    d = (combination_index // 64) % 4
    c = (combination_index // 256) % 8
    timing = ("오늘", "내일", "이번 주", "이번 주말")[d]
    tones = ("편안하게", "따뜻하게", "간결하게", "친근하게")
    if category == "greeting":
        return (
            f"처음 대화해요. 저는 {names[a]}이고 {timing} {moments[c]} {activity_sites[b]}에서 "
            f"{activity_objects[b]} 시작했어요. 지금은 {feelings[d]}. 자연스럽게 인사하고 "
            "짧은 질문도 하나 해 주세요."
        )
    if category == "emotion-support":
        return (
            f"{timing}, 저는 {names[a]}인데 {places[d]}에서 잠깐 쉬는 중이에요. "
            f"{situations[b]} {feelings[c]}. 너무 과장하지 말고 친구처럼 반응해 주세요."
        )
    if category == "everyday":
        return (
            f"{timing} {8 + a}시에 {activity_sites[c]}에서 {approaches[b]} "
            f"{activity_objects[c]} 했더니 "
            f"{feelings[d]}. 이 이야기에 자연스럽게 맞장구쳐 주세요."
        )
    if category == "planning":
        return (
            f"{timing} {_companion_particle(names[a])} {schedules[b]} {activity_sites[c]}에 가서 "
            f"{activity_objects[c]} 하려고 해요. "
            f"{tones[d]} 무리 없는 간단한 순서를 제안해 주세요."
        )
    if category == "advice":
        return (
            f"{timing}부터 {activity_objects[a]} 하루 {10 + b * 5}분씩 이어 가고 싶은데 "
            f"{blockers[c]} 자꾸 미뤄요. {tones[d]} 현실적인 방법 하나를 알려 주세요."
        )
    if category == "preference":
        return (
            f"{timing} 쉬는 날에 {_companion_particle(names[b])} {places[a]}에 갈지 "
            f"{activity_sites[c]}에서 {activity_objects[c]} "
            f"할지 고민돼요. {tones[d]} 장점을 비교하고 제 취향을 물어봐 주세요."
        )
    if category == "reflection":
        return (
            f"{timing} {_companion_particle(names[a])} {activity_sites[b]}에서 "
            f"{activity_objects[b]} 마치고 나니 {feelings[c]}. "
            f"결과보다 과정이 기억에 남는데, {tones[d]} 대화를 이어 주세요."
        )
    if category == "brainstorming":
        return (
            f"{timing} {names[a]}에게 줄 작은 선물을 찾고 있어요. "
            f"{activities[b]}에 관심이 많고 "
            f"예산은 {5_000 + c * 5_000:,}원이에요. {tones[d]} 서로 다른 아이디어 두 개만 "
            "제안해 주세요."
        )
    if category == "writing":
        return (
            f"{timing} {places[a]}에서 만나기로 한 {names[b]}에게 {9 + c}시에 도착한다고 "
            f"알리고 싶어요. {tones[d]} 자연스러운 메시지를 한 문장으로 써 주세요."
        )
    if category == "uncertainty":
        return (
            f"{timing} {9 + a}시에 열리는 {meeting_areas[b]} {activity_sites[c]}의 "
            f"{activities[c]} 모임이 "
            "얼마나 붐비는지 "
            f"지금 확인할 수 있나요? 확인할 수 없다면 {tones[d]} 확인 방법을 알려 주세요."
        )
    raise ValueError(f"지원하지 않는 한국어 대화 범주입니다: {category}")


def _prompt(category: str, index: int, split: Literal["train", "heldout"]) -> str:
    offset = index + (10_000 if split == "heldout" else 1_000)
    names = ("민준", "서연", "도윤", "하린", "지호", "수아", "현우", "나은")
    activities = ("독서", "산책", "요리", "그림", "정리", "운동", "영화 감상", "화분 돌보기")
    places = ("도서관", "공원", "카페", "미술관", "시장", "강변", "동네 서점", "집")
    feelings = (
        "뿌듯해요",
        "조금 지쳤어요",
        "설레요",
        "마음이 복잡해요",
        "후련해요",
        "긴장돼요",
        "차분해졌어요",
        "아쉬워요",
    )
    k = index % 8
    hour = 8 + index % 11
    minutes = 10 + index % 51
    day = 1 + index % 28
    if category == "greeting":
        return (
            f"처음 대화해요. 저는 {names[k]}이고 오늘 {offset}쪽짜리 기록장을 펴서 "
            f"{activities[k]}을 시작했어요. 자연스럽게 인사하고 짧은 질문도 하나 해 주세요."
        )
    if category == "emotion-support":
        return (
            f"{names[k]}인데, 오늘 {offset}번 작업을 마치고 나니 {feelings[k]} "
            "너무 과장하지 말고 친구처럼 한두 문장으로 반응해 주세요."
        )
    if category == "everyday":
        return (
            f"오늘 {hour}시에 {places[k]}에서 {minutes}분 정도 {activities[k]}을 하고 "
            f"{offset}걸음을 걸었어요. 이 이야기에 자연스럽게 맞장구쳐 주세요."
        )
    if category == "planning":
        return (
            f"이번 달 {day}일에 {names[k]}와 {places[k]}에 가는 {offset}번 약속이 있어요. "
            f"{activities[(k + 1) % 8]}도 하고 싶은데 무리 없는 간단한 순서를 제안해 주세요."
        )
    if category == "advice":
        return (
            f"{activities[k]}을 매일 {minutes}분씩 해서 {offset}일 기록을 만들고 싶은데 "
            "자꾸 미뤄요. 부담 없이 계속할 수 있는 현실적인 방법 하나를 대화하듯 알려 주세요."
        )
    if category == "preference":
        return (
            f"쉬는 날에 {places[k]}의 {offset}번 전시를 볼지 집에서 {activities[k]}을 할지 "
            "고민돼요. 각각의 장점을 짧게 말하고 제 취향을 물어봐 주세요."
        )
    if category == "reflection":
        return (
            f"{offset}일 동안 준비한 일을 끝냈는데 결과보다 과정이 더 기억에 남아요. "
            "제 말을 되풀이하지 말고 자연스럽게 대화를 이어 주세요."
        )
    if category == "brainstorming":
        return (
            f"{names[k]}의 {offset}번째 작은 기념일에 줄 선물을 찾고 있어요. "
            f"예산은 {10 + index % 41}천 원이고 {activities[k]}을 좋아해요. "
            "서로 다른 아이디어 두 개만 제안해 주세요."
        )
    if category == "writing":
        return (
            f"{places[k]}의 {offset}번 좌석에서 만나기로 한 {names[k]}에게 {hour}시에 "
            "도착한다고 알리는 따뜻하고 자연스러운 메시지를 한 문장으로 써 주세요."
        )
    if category == "uncertainty":
        return (
            f"오늘 {hour}시 {places[k]}의 {offset}번 행사 혼잡도를 지금 확인할 수 있나요? "
            "확인할 수 없다면 추측하지 말고 제가 확인할 방법을 짧게 알려 주세요."
        )
    raise ValueError(f"지원하지 않는 한국어 대화 범주입니다: {category}")


def _row(
    category: str,
    index: int,
    split: Literal["train", "heldout"],
    profile: Literal["expanded-v1", "natural-v2"],
    prompt_index: int | None = None,
) -> ChatRow:
    identifier = f"korean-conversation-{profile}-{split}-{category}-{index:05d}"
    if profile == "natural-v2":
        if prompt_index is None:
            raise IntegrityError("natural-v2 prompt index가 누락되었습니다")
        prompt = _natural_prompt(category, prompt_index)
    else:
        prompt = _prompt(category, index, split)
    provenance = Provenance(
        dataset=f"llmex-korean-conversation-prompts-{profile}",
        source="repository-authored-prompt-inventory",
        license="MIT",
        collected_at=_COLLECTED_AT,
        source_id=identifier,
        source_sha256=fingerprint({"category": category, "split": split, "prompt": prompt}),
        source_metadata={
            "category": category,
            "profile": profile,
            **({"prompt_index": prompt_index} if prompt_index is not None else {}),
            **(
                {"combination_index": (prompt_index * 641) % 2048}
                if prompt_index is not None
                else {}
            ),
        },
        response_quality=(
            _response_quality(category, prompt_index)
            if profile == "natural-v2" and prompt_index is not None
            else None
        ),
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


def prepare_korean_conversation_prompts(
    output_dir: Path,
    *,
    train_rows_per_category: int = 800,
    heldout_rows_per_category: int = 200,
    profile: Literal["expanded-v1", "natural-v2"] = "expanded-v1",
) -> dict[str, object]:
    """10개 범주의 결정적 한국어 자연대화 prompt inventory를 게시한다."""
    if train_rows_per_category < 1 or heldout_rows_per_category < 1:
        raise IntegrityError("한국어 범주별 train/heldout 행 수는 1 이상이어야 합니다")
    if profile == "natural-v2" and train_rows_per_category + heldout_rows_per_category > 2048:
        raise IntegrityError("natural-v2는 범주별 최대 2,048개 prompt를 지원합니다")
    split_counts: tuple[tuple[Literal["train", "heldout"], int], ...] = (
        ("train", train_rows_per_category),
        ("heldout", heldout_rows_per_category),
    )
    rows = [
        _row(
            category,
            index,
            split,
            profile,
            index + train_rows_per_category
            if profile == "natural-v2" and split == "heldout"
            else index,
        )
        for split, count in split_counts
        for category in _CATEGORIES
        for index in range(count)
    ]
    prompts = [row.messages[0].content for row in rows]
    if len(prompts) != len(set(prompts)):
        raise IntegrityError("한국어 자연대화 prompt가 중복되었습니다")
    payload = "".join(
        json.dumps(
            row.model_dump(exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    ).encode("utf-8")
    output_path = output_dir / "prompts.jsonl"
    manifest_path = output_dir / "manifest.json"
    if output_path.exists() or manifest_path.exists():
        if (
            not output_path.is_file()
            or not manifest_path.is_file()
            or output_path.read_bytes() != payload
        ):
            raise ConflictError("기존 한국어 자연대화 prompt inventory가 현재 설정과 다릅니다")
        return json.loads(manifest_path.read_text(encoding="utf-8")) | {"reused": True}
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "kind": "korean-conversation-teacher-prompt-inventory",
        "profile": profile,
        "categories": list(_CATEGORIES),
        "rows": len(rows),
        "split_rows": {
            "train": train_rows_per_category * len(_CATEGORIES),
            "heldout": heldout_rows_per_category * len(_CATEGORIES),
        },
        "output": {"path": str(output_path), "sha256": hashlib.sha256(payload).hexdigest()},
        "prompt_overlap": 0,
        "license": "MIT",
    }
    manifest["fingerprint"] = fingerprint(manifest)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return manifest | {"reused": False}
