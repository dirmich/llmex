"""source metadata에 결속된 증류 응답 품질 gate 회귀 테스트."""

import hashlib
import json
from pathlib import Path
from typing import Literal, cast

import pytest

from llmex.chat.data import ResponseQualityContract
from llmex.chat.multilingual import response_quality_contract
from llmex.config import DistillationConfig
from llmex.distill.filters import filter_logical_response
from llmex.distill.prompts import build_inventory
from llmex.distill.schema import LogicalRequest, SourceProvenance
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint


def _config(tmp_path: Path) -> DistillationConfig:
    return DistillationConfig(
        name="quality-gate-test",
        endpoint="http://localhost:8081/v1",
        model="teacher",
        run_dir=tmp_path / "run",
        source_chat_files=[tmp_path / "source.jsonl"],
        corpus=tmp_path / "unused.jsonl.zst",
        target_requests=1,
        source_collected_at="2026-07-18",
        min_response_chars=1,
        max_response_chars=2_000,
        max_repetition_ratio=1.0,
        max_prompt_copy_ratio=1.0,
        quality_gate_version="metadata-v1",
    )


def _request(
    prompt: str,
    contract: ResponseQualityContract,
    *,
    metadata: dict[str, str | int] | None = None,
) -> LogicalRequest:
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return LogicalRequest(
        schema_version=2,
        id=f"distill-{prompt_sha256[:24]}",
        prompt=prompt,
        prompt_sha256=prompt_sha256,
        split="train",
        source=SourceProvenance(
            dataset="quality-regression",
            source="tests/test_distill_quality.py",
            license="CC-BY-4.0",
            collected_at="2026-07-18",
            source_id="quality-source-1",
            source_sha256="a" * 64,
            source_split="train",
            metadata=metadata or {"teacher": "qwen36"},
            response_quality=contract,
        ),
    )


def _translation(
    language: Literal["ko", "en", "ja"],
    *,
    numbers: list[list[str]] | None = None,
    entities: list[list[str]] | None = None,
    terms: list[list[str]] | None = None,
) -> ResponseQualityContract:
    return ResponseQualityContract(
        mode="translation-only",
        target_language=language,
        max_sentences=2,
        required_numbers=numbers or [],
        required_entities=entities or [],
        required_terms=terms or [],
    )


@pytest.mark.parametrize(
    ("case", "prompt", "contract", "response", "accepted"),
    [
        (
            "일본어 원문 반복",
            "다음을 한국어로 번역하세요: 明日の会議は午後三時です。",
            _translation("ko"),
            "明日の会議は午後三時です。",
            False,
        ),
        (
            "일본어에서 한국어 정상 번역",
            "다음을 한국어로 번역하세요: 明日の会議は午後三時です。",
            _translation("ko"),
            "내일 회의는 오후 세 시입니다.",
            True,
        ),
        (
            "한국어 번역에 일본어 표기 잔류",
            "다음을 한국어로 번역하세요: 蒼い空がきれいです。",
            _translation("ko"),
            "蒼 푸른 하늘이 아름답습니다.",
            False,
        ),
        (
            "일본어 표기 제거",
            "다음을 한국어로 번역하세요: 蒼い空がきれいです。",
            _translation("ko"),
            "푸른 하늘이 아름답습니다.",
            True,
        ),
        (
            "한국어 원문 반복",
            "다음을 일본어로 번역하세요: 오늘은 날씨가 맑습니다.",
            _translation("ja"),
            "오늘은 날씨가 맑습니다.",
            False,
        ),
        (
            "한국어에서 일본어 정상 번역",
            "다음을 일본어로 번역하세요: 오늘은 날씨가 맑습니다.",
            _translation("ja"),
            "今日は天気が晴れています。",
            True,
        ),
        (
            "복수형 용어 누락",
            "Translate into Korean: I bought three notebooks.",
            _translation("ko", numbers=[["3", "세"]], terms=[["공책 세 권", "노트 세 권"]]),
            "노트북을 샀습니다.",
            False,
        ),
        (
            "수량과 용어 보존",
            "Translate into Korean: I bought three notebooks.",
            _translation("ko", numbers=[["3", "세"]], terms=[["공책 세 권", "노트 세 권"]]),
            "공책 세 권을 샀습니다.",
            True,
        ),
        (
            "영문 고유명사 변형",
            "Translate into Korean while preserving the name Avery: Avery arrived early.",
            _translation("ko", entities=[["Avery"]]),
            "아버리가 일찍 도착했습니다.",
            False,
        ),
        (
            "영문 고유명사 보존",
            "Translate into Korean while preserving the name Avery: Avery arrived early.",
            _translation("ko", entities=[["Avery"]]),
            "Avery가 일찍 도착했습니다.",
            True,
        ),
        (
            "한글 고유명사 오역",
            "Translate into English while preserving the name 현우: 현우가 문을 열었다.",
            _translation("en", entities=[["현우", "Hyunwoo"]]),
            "Hyuwoo opened the door.",
            False,
        ),
        (
            "한글 고유명사 허용 표면형",
            "Translate into English while preserving the name 현우: 현우가 문을 열었다.",
            _translation("en", entities=[["현우", "Hyunwoo"]]),
            "Hyunwoo opened the door.",
            True,
        ),
        (
            "지정 일본어 용어 불일치",
            "다음을 일본어로 번역하고 '표'는 テーブル로 쓰세요: 표를 확인하세요.",
            _translation("ja", terms=[["テーブル"]]),
            "表を確認してください。",
            False,
        ),
        (
            "지정 일본어 용어 준수",
            "다음을 일본어로 번역하고 '표'는 テーブル로 쓰세요: 표를 확인하세요.",
            _translation("ja", terms=[["テーブル"]]),
            "テーブルを確認してください。",
            True,
        ),
        (
            "숫자 변형",
            "Translate into English: 배터리는 48시간 지속됩니다.",
            _translation("en", numbers=[["48"]]),
            "The battery lasts for 24 hours.",
            False,
        ),
        (
            "숫자 보존",
            "Translate into English: 배터리는 48시간 지속됩니다.",
            _translation("en", numbers=[["48"]]),
            "The battery lasts for 48 hours.",
            True,
        ),
        (
            "영어 숫자 단어 추가",
            "Translate into English: 9시에 노트 세 권을 받습니다.",
            _translation("en", numbers=[["9", "nine"], ["3", "three"]]),
            "At nine, I receive three notebooks and four extras.",
            False,
        ),
        (
            "한국어 숫자 단어 추가",
            "Translate into Korean: At nine, I receive three notebooks.",
            _translation("ko", numbers=[["9", "아홉"], ["3", "세"]]),
            "아홉 시에 노트 세 권과 우산 네 개를 받습니다.",
            False,
        ),
        (
            "일본어 숫자 단어 추가",
            "Translate into Japanese: At nine, I receive three notebooks.",
            _translation("ja", numbers=[["9", "九"], ["3", "三"]]),
            "九時にノートを三冊と傘を四本受け取ります。",
            False,
        ),
        (
            "일본어 두 자리 숫자 단어 보존",
            "Translate into Japanese: I arrive at eleven.",
            _translation("ja", numbers=[["11", "十一"]]),
            "十一時に到着します。",
            True,
        ),
        (
            "요일과 장소 변경",
            "Translate into English: 월요일 도서관에서 노트를 받습니다.",
            _translation(
                "en",
                terms=[["Monday"], ["library"], ["notebook"], ["receive", "collect"]],
            ),
            "On Tuesday, I receive a notebook at the park.",
            False,
        ),
    ],
)
def test_qwen_번역_합성_품질_회귀(
    tmp_path: Path,
    case: str,
    prompt: str,
    contract: ResponseQualityContract,
    response: str,
    accepted: bool,
) -> None:
    reason = filter_logical_response(_request(prompt, contract), response, _config(tmp_path))

    assert (reason is None) is accepted, f"{case}: reason={reason!r}"


@pytest.mark.parametrize(
    ("case", "language", "act", "response", "expected"),
    [
        (
            "영어 질문 1개",
            "en",
            "question",
            "That sounds encouraging. What will you try next?",
            None,
        ),
        (
            "닫는 인용과 괄호 뒤 질문",
            "en",
            "question",
            "That sounds encouraging. (What will you try next?)",
            None,
        ),
        (
            "영어 질문 누락",
            "en",
            "question",
            "That sounds encouraging and worth celebrating.",
            "quality:conversation_question",
        ),
        (
            "일본어 질문 2개",
            "ja",
            "question",
            "よかったですね。次は何をしますか\uff1fどこで始めますか\uff1f",
            "quality:conversation_question",
        ),
        (
            "영어 질문이 마지막이 아님",
            "en",
            "question",
            "What will you try next? That sounds encouraging.",
            "quality:conversation_question",
        ),
        (
            "영어 실용 제안",
            "en",
            "suggestion",
            "That sounds tiring. Perhaps try a short walk before deciding.",
            None,
        ),
        (
            "영어 제안 대신 질문",
            "en",
            "suggestion",
            "That sounds tiring. What would feel easiest?",
            "quality:conversation_suggestion",
        ),
        (
            "영어 가능성만 언급",
            "en",
            "suggestion",
            "That sounds tiring. Perhaps tomorrow will feel easier.",
            "quality:conversation_suggestion",
        ),
        (
            "영어 try 일반 서술",
            "en",
            "suggestion",
            "You try hard every day.",
            "quality:conversation_suggestion",
        ),
        (
            "영어 부정 추천",
            "en",
            "suggestion",
            "I do not recommend any practical step.",
            "quality:conversation_suggestion",
        ),
        (
            "영어 modal 가능성",
            "en",
            "suggestion",
            "You might feel better tomorrow.",
            "quality:conversation_suggestion",
        ),
        (
            "영어 modal 상태 판단",
            "en",
            "suggestion",
            "You could be right.",
            "quality:conversation_suggestion",
        ),
        (
            "일본어 실용 제안",
            "ja",
            "suggestion",
            "お疲れさまでした。今日は短い散歩をしてみるといいですよ。",
            None,
        ),
        (
            "일본어 제안 표면형 누락",
            "ja",
            "suggestion",
            "お疲れさまでした。ゆっくり休める一日ですね。",
            "quality:conversation_suggestion",
        ),
        (
            "일본어 부정 추천",
            "ja",
            "suggestion",
            "今は散歩をおすすめしません。",
            "quality:conversation_suggestion",
        ),
        (
            "일본어 날씨 소망",
            "ja",
            "suggestion",
            "明日は天気だといいですね。",
            "quality:conversation_suggestion",
        ),
        (
            "일본어 주말 소망",
            "ja",
            "suggestion",
            "楽しい週末になるといいですね。",
            "quality:conversation_suggestion",
        ),
    ],
)
def test_conversation_act가_source_metadata에_결속된다(
    tmp_path: Path,
    case: str,
    language: Literal["en", "ja"],
    act: Literal["question", "suggestion"],
    response: str,
    expected: str | None,
) -> None:
    contract = ResponseQualityContract(
        mode=cast(
            Literal["conversation-question", "conversation-suggestion"],
            f"conversation-{act}",
        ),
        target_language=language,
        max_sentences=3,
    )
    reason = filter_logical_response(
        _request("자연스럽게 답하세요.", contract, metadata={"conversation_act": act}),
        response,
        _config(tmp_path),
    )

    assert reason == expected, case


def test_conversation_act_metadata와_contract_불일치는_거절한다() -> None:
    contract = ResponseQualityContract(
        mode="conversation-question", target_language="en", max_sentences=3
    )

    with pytest.raises(ValueError, match="conversation_act metadata와 response_quality mode"):
        _request("Reply naturally.", contract, metadata={"conversation_act": "suggestion"})


@pytest.mark.parametrize(
    ("case", "contract", "response", "accepted"),
    [
        (
            "직접 보낼 한 문장",
            ResponseQualityContract(mode="direct-message", target_language="ko", max_sentences=1),
            "오늘 저녁 7시에 카페 앞에서 만날 수 있을까?",
            True,
        ),
        (
            "인용과 작성 안내가 붙은 답",
            ResponseQualityContract(mode="direct-message", target_language="ko", max_sentences=1),
            '"오늘 저녁 7시에 만날 수 있을까?"라고 보내보세요.',
            False,
        ),
        (
            "인용 뒤 이렇게 보내 안내",
            ResponseQualityContract(mode="direct-message", target_language="ko", max_sentences=1),
            "“오늘 9시에 도착할게” 이렇게 보내보세요.",
            False,
        ),
        (
            "여러 대안을 제시하는 답",
            ResponseQualityContract(mode="direct-message", target_language="ko", max_sentences=1),
            "오늘 만날 수 있을까? 혹은 내일은 어때?",
            False,
        ),
        (
            "종결부호 뒤 무종결 대안",
            ResponseQualityContract(mode="direct-message", target_language="ko", max_sentences=1),
            "오늘 9시에 도착할게! 내일은 어때",
            False,
        ),
        (
            "일반형 사용 안내가 붙은 답",
            ResponseQualityContract(mode="direct-message", target_language="ko", max_sentences=1),
            "오늘 9시에 도착해요—이 문구를 그대로 사용하면 됩니다.",
            False,
        ),
        (
            "약속 시간 변형",
            ResponseQualityContract(
                mode="direct-message",
                target_language="ko",
                max_sentences=1,
                required_numbers=[["7", "일곱"]],
            ),
            "오늘 저녁 8시에 카페 앞에서 만날 수 있을까?",
            False,
        ),
        (
            "불확실성 경계와 확인 경로",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 영업시간을 확인할 수 없습니다. "
            "정확한 시간은 매장에 직접 문의해 주세요.",
            True,
        ),
        (
            "지원하지 않는 실시간 조회 주장",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "실시간 지도를 확인해 보니 지금 영업 중입니다.",
            False,
        ),
        (
            "일반 지도 앱 실시간 기능 단정",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "직접 확인할 수는 없지만 지도 앱의 실시간 혼잡도 기능을 활용하세요. "
            "공식 페이지에 문의하세요.",
            False,
        ),
        (
            "구글 지도 실시간 제공 단정",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "확인 불가합니다. 공식 구글 지도 서비스가 실시간 혼잡도를 제공합니다. "
            "공식 페이지에 문의하세요.",
            False,
        ),
        (
            "마크다운 링크 주소에 지도 제공자",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "혼잡도 현황은 [여기](https://maps.google.com)에서 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "마크다운 링크 주소에 혼잡도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "[네이버](https://example.com/혼잡도)를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML 태그로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "<b>지</b><i>도</i> 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML 태그로 분리한 혼잡도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱에서 혼<b>잡</b>도를 보세요. 직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML 엔티티로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지&#46020; 앱에서 혼잡도를 보세요. 직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "한글 채움 문자로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지\u3164도 앱에서 혼잡도를 보세요. 직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "키릴 문자로 위장한 구글",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "g\u043e\u043egle 지도에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML 자동 링크 주소에 지도 제공자",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "혼잡도 현황은 <https://maps.google.com>에서 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML 링크 속성에 지도 제공자",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '<a href="https://maps.google.com">혼잡도 현황</a>을 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML 링크 속성에 혼잡도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '<a href="https://example.com/혼잡도">네이버</a>를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "중첩 HTML 엔티티로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지&amp;amp;#46020; 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "인용 부등호 속성 태그로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '지<span data-x="&gt;x">도</span> 앱에서 혼잡도를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "부등호 HTML 주석으로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지<!-- > x -->도 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "분할 Markdown 링크 label의 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "[지](https://x.invalid/a)[도](https://y.invalid/b) 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "음악 기호 Cf로 분리한 한글 자모 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "ᄌ\U0001d173ᅵ도 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "그리스 문자로 위장한 구글",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "g\u03bf\u03bfgle 지도에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "script g로 위장한 구글",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "\u0261oogle 지도에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "분할 Markdown 참조 링크 label의 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "[지][x][도][y] 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.\n"
            "[x]: https://x.invalid/a\n[y]: https://y.invalid/b",
            False,
        ),
        (
            "Latin alpha로 위장한 map",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "m\u0251p에서 혼잡도를 보세요. 직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "그리스 rho로 위장한 map",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "ma\u03c1에서 혼잡도를 보세요. 직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "숫자 영으로 위장한 구글",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "g00gle 지도에서 혼잡도를 보세요. 직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "script 내용으로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지<script>x</script>도 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "style 내용으로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지<style>x</style>도 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "Cf 태그 이름으로 분리한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지<\u200bb></\u200bb>도 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "Cf로 분리한 Markdown 링크",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "[지]\u200b(https://x.invalid)[도](https://y.invalid) 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "구두점으로 분리한 한글 자모 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "ᄌ-ᅵ도 앱에서 혼잡도를 보세요. 직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "이미지 대체 텍스트로 완성한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '지<img src="x" alt="도"> 앱에서 혼잡도를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "이미지 대체 텍스트로 완성한 혼잡도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '지도 앱에서 혼<img src="x" alt="잡도">를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "입력값으로 완성한 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '지<input value="도"> 앱에서 혼잡도를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "escape된 Markdown label의 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            r"[지\]](https://x.invalid)[도](https://y.invalid) 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "escape된 Markdown 참조 label의 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            r"[지\]][x][도][y] 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.\n"
            "[x]: https://x.invalid/a\n[y]: https://y.invalid/b",
            False,
        ),
        (
            "중첩 Markdown label의 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "[[지]](https://x.invalid)[[도]](https://y.invalid) 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "escape된 Markdown label의 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            r"[g\]](https://x.invalid)[oogle](https://y.invalid)에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "escape된 Markdown 참조 label의 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            r"[g\]][x][oogle][y]에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.\n"
            "[x]: https://x.invalid/a\n[y]: https://y.invalid/b",
            False,
        ),
        (
            "중첩 Markdown label의 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "[[goo]](https://x.invalid)[[gle]](https://y.invalid)에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "escape된 Markdown label의 map",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            r"[m\]](https://x.invalid)[ap](https://y.invalid)에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "접근성 이름으로 완성한 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            'g<span aria-label="oo"></span>gle에서 혼잡도를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "오른쪽 방향 재정의 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "\u202eelgoog\u202c에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "오른쪽 방향 재정의 map",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "\u202epam\u202c에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "오른쪽 방향 재정의 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "\u202e도지\u202c 앱에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "16진 HTML 엔티티 방향 재정의 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "&#x202E;elgoog&#x202C;에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "10진 HTML 엔티티 방향 재정의 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "&#8238;elgoog&#8236;에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "중첩 HTML 엔티티 방향 재정의 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "&amp;#x202E;elgoog&amp;#x202C;에서 혼잡도를 보세요. "
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML bdo 방향 재정의 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '<bdo dir="rtl">elgoog</bdo>에서 혼잡도를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML bdo 방향 재정의 지도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '<bdo dir="rtl">도지</bdo> 앱에서 혼잡도를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML dir 속성 방향 재정의",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '<span dir="rtl">elgoog</span>에서 혼잡도를 보세요. '
            "직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "HTML style 방향 재정의",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            '<span style="unicode-bidi: bidi-override; direction: rtl">elgoog</span>에서 '
            "혼잡도를 보세요. 직접 확인할 수는 없으니 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "자연스러운 붐비다 활용형",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. Google에서 얼마나 붐비는지 확인하세요. "
            "정확한 정보는 공식 홈페이지나 주최 측에 문의하세요.",
            False,
        ),
        (
            "자연스러운 사람이 많다 활용형",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. Google에서 사람이 많은지 확인하세요. "
            "정확한 정보는 공식 홈페이지나 주최 측에 문의하세요.",
            False,
        ),
        (
            "내비게이션 혼잡도 안내",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 내비게이션 앱에서 실시간 혼잡도를 "
            "확인하세요. 정확한 정보는 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "대문자 I로 위장한 google",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. googIe에서 실시간 혼잡도를 "
            "확인하세요. 정확한 정보는 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 서비스 혼잡도 참고 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 실시간 혼잡도를 정확히 알 수는 없지만, 모임 장소의 공식 페이지나 "
            "주최 측에 직접 문의하세요. 지도 서비스의 혼잡도 정보를 참고할 수도 있습니다.",
            False,
        ),
        (
            "지도 서비스 제공 혼잡도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "실시간 혼잡도를 직접 확인할 수는 없지만, 모임 주최 측에 문의하거나 해당 장소의 "
            "지도 서비스에서 제공하는 혼잡도 정보를 참고해 보세요.",
            False,
        ),
        (
            "지도 혼잡도 정보 비의존 안내",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 실시간 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보는 참고하지 "
            "말고 공식 페이지나 주최 측에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 긍정 뒤 비의존 혼합 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보를 참고할 수도 있지만 "
            "의존하지 말고 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "지도 실시간 혼잡도 직접 부정",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 서비스에서 실시간 혼잡도를 확인할 수 없습니다. 정확한 정보는 공식 페이지나 "
            "주최 측에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 참고하면 활용형 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보를 참고하면 좋습니다. "
            "공식 페이지에도 문의하세요.",
            False,
        ),
        (
            "지도 실시간 혼잡도 가능 명사형 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "제가 직접 확인할 수는 없습니다. 지도 서비스에서 실시간 혼잡도 확인이 가능합니다. "
            "정확한 정보는 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 비의존 뒤 공식 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보에 의존하지 말고 "
            "공식 홈페이지에서 확인하세요. "
            "필요하면 주최 측에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 참조 활용형 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보를 참조하세요. "
            "공식 페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 살펴보기 활용형 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 앱의 혼잡도 현황을 살펴보세요. "
            "공식 페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 참고하면 안 됨",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보를 참고하면 안 됩니다. "
            "공식 페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 참고해서는 안 됨",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보를 참고해서는 안 됩니다. "
            "공식 페이지에 문의하세요.",
            False,
        ),
        (
            "지도 실시간 혼잡도 확인 어려움",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 서비스의 실시간 혼잡도 확인이 어렵습니다. 공식 페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 비의존 뒤 행사 웹사이트 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보에 의존하지 말고 "
            "행사 웹사이트에서 확인하세요.",
            False,
        ),
        (
            "지도 혼잡도 비참고 뒤 현장 안내판 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스의 혼잡도 정보를 참고하지 말고 "
            "현장 안내판에서 확인하세요.",
            False,
        ),
        (
            "지도 혼잡도 공식적 제공 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 직접 확인할 수 없습니다. 지도에서 혼잡도를 공식적으로 제공합니다. "
            "행사 웹사이트에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 이용 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 앱의 혼잡도 정보를 이용해 보세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 체크 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 앱의 혼잡도를 체크하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 파악 가능 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 직접 확인할 수 없습니다. 지도 앱에서 혼잡도를 파악할 수 있습니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 찾기 가능 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 직접 확인할 수 없습니다. 지도 앱에서 혼잡도를 찾을 수 있습니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 알기 가능 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 직접 확인할 수 없습니다. 지도 앱에서 혼잡도를 알 수 있습니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 참고하지 마세요",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 앱의 혼잡도 정보는 참고하지 마세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 참고하시면 안 됨",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 앱의 혼잡도 정보를 참고하시면 안 됩니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 확인하기가 어려움",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱의 실시간 혼잡도는 확인하기가 어렵습니다. 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 확인하는 것은 어려움",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱의 실시간 혼잡도를 확인하는 것은 어렵습니다. 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 말고 공식 홈페이지 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 혼잡도 말고 공식 홈페이지에서 확인하세요.",
            False,
        ),
        (
            "공식 홈페이지를 통한 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 지도 혼잡도는 확인할 수 없습니다. 공식 홈페이지를 통해 확인하세요.",
            False,
        ),
        (
            "지도 아닌 공식 홈페이지 혼잡도 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 서비스가 아니라 공식 홈페이지에서 혼잡도를 "
            "확인하세요.",
            False,
        ),
        (
            "지도 혼잡도 제공 여부 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱의 혼잡도 기능 제공 여부는 공식 홈페이지에서 확인하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "지도 혼잡도 제공하는지 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱에서 혼잡도 정보를 제공하는지 공식 홈페이지에서 확인하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "공식 대상 선행 제공 여부 확인",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "공식 홈페이지에서 지도 앱의 혼잡도 제공 여부를 확인하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "지도 혼잡도 가능 여부 문의",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱에서 혼잡도를 확인할 수 있는지는 공식 홈페이지에 문의하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "지도 혼잡도 가능 안내 비의존",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱에서 혼잡도를 볼 수 있다는 안내를 믿지 말고 공식 홈페이지에 문의하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "지도 혼잡도 알림 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 앱이 혼잡도를 알려줍니다. "
            "공식 홈페이지에도 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 출력 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 앱에 혼잡도 정보가 나옵니다. "
            "공식 홈페이지에도 문의하세요.",
            False,
        ),
        (
            "공식 대상 미끼 뒤 지도 활용",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 혼잡도는 확인할 수 없습니다. 지도 앱의 혼잡도 정보를 공식 홈페이지 대신 "
            "활용하세요.",
            False,
        ),
        (
            "지도 혼잡도 부정 가능성",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱의 혼잡도 정보는 정확하지 않을 수 있습니다. 공식 홈페이지에 문의하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "지도 혼잡도 가능 보장 없음",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱에서 혼잡도를 확인할 수 있다는 보장은 없습니다. 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 혼잡도 인용 안내 비신뢰",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱의 혼잡도를 “확인하세요”라는 안내는 믿지 마세요. "
            "공식 홈페이지에 문의하세요. 현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "지도 혼잡도 확인 불가 안내",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도 앱에서는 혼잡도를 확인할 수 없다고 안내합니다. 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "별개 문장 지도 위치와 현장 혼잡도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도에서 행사 위치를 찾아보세요. 혼잡도는 현장에서 확인하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "같은 문장 지도 위치와 현장 혼잡도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도에서 행사 위치를 찾고 혼잡도는 현장에서 확인하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "줄바꿈 지도 혼잡도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도 앱에서\n실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "공백 없는 별개 문장 지도 위치와 현장 혼잡도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도에서 행사 위치를 찾아보세요.혼잡도는 현장에서 확인하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "쉼표로 분리한 지도 위치와 현장 혼잡도",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도에서 행사 위치를 찾아보세요, 혼잡도는 현장에서 확인하세요. "
            "현재 정보만으로는 확인할 수 없습니다.",
            False,
        ),
        (
            "공식 대상 말고 지도 확인 미끼",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 공식 홈페이지 말고 지도 앱 혼잡도를 확인하세요.",
            False,
        ),
        (
            "공식 대상 무관 지도 확인 미끼",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 공식 홈페이지와 무관하게 지도 앱 혼잡도를 "
            "확인하세요.",
            False,
        ),
        (
            "지도 없는 공식 확인 경로",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 혼잡도를 확인할 수 없습니다. 공식 홈페이지나 주최 측에 문의하세요.",
            True,
        ),
        (
            "지도자 부분문자열 비provider",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "지도자라는 단어와 혼잡도는 관련이 없습니다. 현재 정보만으로는 확인할 수 없습니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "카카오톡 부분문자열 비provider",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "카카오톡이라는 이름과 혼잡도는 관련이 없습니다. 현재 정보만으로는 확인할 수 없습니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "버전 소수점 지도 혼잡도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도 앱 v1.2에서 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "복합 조사 지도 혼잡도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도에서는 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "붙여 쓴 지도앱 콜론 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도앱: 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "인용 카카오 조사 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. “카카오”의 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "마크다운 네이버 조사 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. **네이버**의 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "구글맵 복합 조사 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 구글맵에서의 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 복합 조사 확장 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도에선 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도 괄호 앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도(앱)에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "GoogleMaps 붙여쓰기 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. GoogleMaps에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "Markdown 링크 지도앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. [지도앱](https://example.com)에서 "
            "실시간 혼잡도를 "
            "확인하세요. 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "인라인 코드 지도앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. `지도앱`에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "축약 조사 지도앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도앱으론 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "제로폭 지도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지\u200b도 앱에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "a.m. 점 보호 지도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도 앱은 9 a.m. 이후 혼잡도를 보여줍니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "일본어 인용 카카오맵 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 「카카오맵」에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "지도라고 해도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도라고 해도 혼잡도를 보여줍니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "구두점 지도앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도앱→실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "HTML 지도앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. <code>지도앱</code>에서 실시간 혼잡도를 "
            "확인하세요. 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "emoji 지도앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도앱🗺️에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "추가 축약 조사 지도앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도앱에겐 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "copula 지도 앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도라는 앱에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "접두 합성 지도앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 모바일지도앱에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "ver 약어 지도 앱 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도 앱 ver. 2에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "Google Maps Inc 약어 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. Google Maps Inc. 앱에서 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "google-able 부분문자열 보수 격리",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "google-able이라는 표현과 혼잡도는 무관합니다. 현재 정보만으로는 확인할 수 없습니다. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "공백 없는 점 지도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 지도.한국에서 실시간 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "로드맵 부분문자열 비provider",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "행사 혼잡도 개선 로드맵은 아직 확정되지 않았습니다. 현재 정보만으로는 확인할 수 "
            "없습니다. 공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "도메인 점 지도 혼잡도 우회",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. maps.google.com에서 혼잡도를 확인하세요. "
            "공식 홈페이지에 문의하세요.",
            False,
        ),
        (
            "확인 불가 경계 누락",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "아마 오늘 오후 9시까지 영업합니다.",
            False,
        ),
        (
            "문장 수 상한 초과",
            ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3),
            "현재 정보만으로는 확인할 수 없습니다. 운영 시간은 바뀔 수 있습니다. "
            "매장 공지를 확인해 주세요. 필요하면 매장에 문의해 주세요.",
            False,
        ),
    ],
)
def test_gemma_writing과_uncertainty_품질_회귀(
    tmp_path: Path,
    case: str,
    contract: ResponseQualityContract,
    response: str,
    accepted: bool,
) -> None:
    prompt = "요청한 형식에 맞게 답해 주세요."
    reason = filter_logical_response(_request(prompt, contract), response, _config(tmp_path))

    assert (reason is None) is accepted, f"{case}: reason={reason!r}"


@pytest.mark.parametrize(
    "response",
    [
        "현재 정보만으로는 확인할 수 없습니다. `지도앱`에서 실시간 혼잡도를 확인하세요. "
        "공식 홈페이지에 문의하세요.",
        "현재 정보만으로는 확인할 수 없습니다. 지\u200b도 앱에서 실시간 혼잡도를 확인하세요. "
        "공식 홈페이지에 문의하세요.",
        "현재 정보만으로는 확인할 수 없습니다. 지도 앱은 9 a.m. 이후 혼잡도를 보여줍니다. "
        "공식 홈페이지에 문의하세요.",
    ],
)
def test_지도_혼잡도_격리는_고정된_사유를_반환한다(tmp_path: Path, response: str) -> None:
    contract = ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3)

    reason = filter_logical_response(
        _request("실시간 혼잡도를 알려 주세요.", contract),
        response,
        _config(tmp_path),
    )

    assert reason == "quality:unsupported_realtime_claim"


@pytest.mark.parametrize(
    "response",
    [
        "`현재 정보만으로는 확인할 수 없습니다.` 정확한 내용은 공식 홈페이지에 문의하세요.",
        "**현재 정보만으로는 확인할 수 없습니다.** 정확한 내용은 공식 홈페이지에 문의하세요.",
        "- 현재 정보만으로는 확인할 수 없습니다. 정확한 내용은 공식 홈페이지에 문의하세요.",
    ],
)
def test_uncertainty_markup은_어휘와_무관하게_고정_사유로_격리한다(
    tmp_path: Path, response: str
) -> None:
    contract = ResponseQualityContract(mode="uncertainty", target_language="ko", max_sentences=3)

    reason = filter_logical_response(
        _request("현재 상태를 알려 주세요.", contract),
        response,
        _config(tmp_path),
    )

    assert reason == "quality:unsupported_realtime_claim"


def test_chat_response_quality_metadata가_inventory까지_보존된다(tmp_path: Path) -> None:
    contract = ResponseQualityContract(
        mode="translation-only",
        target_language="ko",
        max_sentences=2,
        required_numbers=[["48"]],
        required_entities=[["Avery"]],
        required_terms=[["공책", "노트"]],
    )
    provenance = {
        "dataset": "quality-regression",
        "source": "synthetic://qwen36/translation",
        "license": "CC-BY-4.0",
        "collected_at": "2026-07-18",
        "source_metadata": {"generator": "qwen36", "batch": 7},
        "response_quality": contract.model_dump(mode="json"),
    }
    messages = [
        {"role": "user", "content": "Translate into Korean: Avery used 48 notebooks."},
        {"role": "assistant", "content": "Avery는 공책 48권을 사용했습니다."},
    ]
    basis = {
        "id": "quality-row-1",
        "messages": messages,
        "provenance": provenance,
        "split": "train",
    }
    row = {"schema_version": 1, **basis, "sha256": fingerprint(basis)}
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    inventory, _ = build_inventory(_config(tmp_path))

    assert inventory[0].source.response_quality == contract
    assert inventory[0].source.metadata == {
        "upstream_split": "train",
        "generator": "qwen36",
        "batch": 7,
    }
    with pytest.raises(IntegrityError, match="metadata-v1"):
        build_inventory(_config(tmp_path).model_copy(update={"quality_gate_version": "none"}))


def test_일본어_계수사_본은_책_용어로_오인하지_않는다() -> None:
    prompt = (
        "自然な韓国語の訳文だけ答えてください。葵は月曜日9時に公園で傘を3本受け取り、蓮に渡します。"
    )
    contract = response_quality_contract("ja-ko", prompt)

    assert ["책"] not in contract.required_terms
    assert ["우산"] in contract.required_terms


def test_번역문_표현의_역은_station_계약으로_오인하지_않는다() -> None:
    prompt = "자연스러운 영어 번역문만 답하세요. 민준은 월요일 9시에 도서관에서 노트 3권을 받아요."
    contract = response_quality_contract("ko-en", prompt)

    assert ["station"] not in contract.required_terms
    assert ["library"] in contract.required_terms
