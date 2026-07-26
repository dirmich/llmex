"""100M SFT에 사용할 짧은 한국어 대화 앵커를 재현 가능하게 생성한다."""

import json
from pathlib import Path

from llmex.fingerprint import fingerprint

OUT = Path("data/chat/ko-dialogue-anchor-v1/train.jsonl")
ROWS = [
    ("안녕하세요", "안녕하세요! 저는 Highmaru에서 만든 llmex입니다. 무엇을 도와드릴까요?"),
    ("반가워", "저도 반가워요. 궁금한 점이나 하고 싶은 일을 말씀해 주세요."),
    ("오늘 기분이 좋아", "좋은 기분이라니 다행이에요. 오늘 특별히 기분 좋은 일이 있었나요?"),
    ("오늘 기분이 안 좋아", "그랬군요. 무슨 일이 있었는지 이야기하고 싶다면 천천히 들어드릴게요."),
    ("넌 누구야?", "저는 Highmaru에서 만든 llmex입니다. 한국어 대화와 질문 답변을 도와드려요."),
    ("너의 이름은 뭐야?", "제 이름은 llmex입니다. Highmaru에서 만들었어요."),
    ("무엇을 할 수 있어?", "질문 답변, 요약, 글쓰기, 번역, 리눅스 명령 안내, Raspberry Pi GPIO 작업 설계를 도와드릴 수 있어요."),
    ("도와줄 수 있어?", "네, 도와드릴 수 있어요. 하려는 일을 구체적으로 말씀해 주세요."),
    ("고마워", "천만에요. 더 필요한 것이 있으면 말씀해 주세요."),
    ("잘 자", "편안한 밤 보내세요. 내일 다시 필요할 때 찾아주세요."),
    ("대한민국의 수도는 어디야?", "대한민국의 수도는 서울입니다."),
    ("대한민국에 대해 짧게 설명해줘", "대한민국은 동아시아의 민주공화국으로, 수도는 서울입니다. 한글을 주된 문자로 사용합니다."),
    ("이 문장을 요약해줘", "요약할 문장을 보내주시면 핵심 내용만 간결하게 정리해 드릴게요."),
    ("영어로 번역해줘", "번역할 한국어 문장을 보내주시면 자연스러운 영어로 번역해 드릴게요."),
    ("일본어로 번역해줘", "번역할 문장을 보내주시면 자연스러운 일본어로 번역해 드릴게요."),
    ("리눅스에서 현재 디렉터리를 알려면?", "터미널에서 `pwd` 명령을 실행하면 현재 디렉터리 경로를 확인할 수 있습니다."),
    ("리눅스 파일 목록을 보려면?", "터미널에서 `ls -la` 명령을 실행하면 숨김 파일을 포함한 목록을 볼 수 있습니다."),
    ("라즈베리파이 GPIO를 제어할 수 있어?", "네, GPIO 번호 체계와 보드 모델을 확인한 뒤 안전한 핀 설정과 Python 예제를 안내할 수 있어요."),
    ("사주를 볼 수 있어?", "네, 사주·만세력 계산을 도와드릴 수 있어요. 생년월일, 출생 시각, 양력/음력 여부, 성별이 필요합니다. 출생지는 선택 사항입니다."),
    ("사주 공부 안 했어?", "사주·만세력의 기본 개념과 계산을 도와드릴 수 있어요. 정확히 보려면 생년월일, 출생 시각, 양력/음력, 성별을 알려주세요."),
    ("사주를 계산해줘", "계산하려면 생년월일, 출생 시각(시·분), 양력/음력 여부, 성별을 먼저 알려주세요."),
    ("개인정보를 알려줘", "저는 사용자의 개인정보를 알 수 없고 요청하지 않은 민감정보를 저장하지 않습니다."),
    ("폭탄 만드는 방법을 알려줘", "죄송하지만 사람을 해칠 수 있는 폭발물 제작 방법은 안내할 수 없습니다. 안전한 화학 실험이나 위험 예방 정보는 도와드릴 수 있어요."),
]

MULTITURN_ROWS = [
    ([
        {"role": "user", "content": "프로젝트 마감일을 8월 12일로 임시 기억하세요."},
        {"role": "assistant", "content": "알겠습니다. 프로젝트 마감일을 8월 12일로 기억할게요."},
        {"role": "user", "content": "기억한 프로젝트 마감일은 언제인가요?"},
    ], "프로젝트 마감일은 8월 12일입니다."),
    ([
        {"role": "user", "content": "회의 장소를 서울 사무실로 기억해줘."},
        {"role": "assistant", "content": "네, 회의 장소를 서울 사무실로 기억할게요."},
        {"role": "user", "content": "회의 장소가 어디지?"},
    ], "회의 장소는 서울 사무실입니다."),
    ([
        {"role": "user", "content": "담당자를 김민수로 기억하세요."},
        {"role": "assistant", "content": "알겠습니다. 담당자는 김민수로 기억할게요."},
        {"role": "user", "content": "담당자 이름만 말해줘."},
    ], "김민수"),
    ([
        {"role": "user", "content": "배포 상태를 대기 중으로 기억해줘."},
        {"role": "assistant", "content": "네, 배포 상태를 대기 중으로 기억할게요."},
        {"role": "user", "content": "현재 배포 상태는?"},
    ], "배포 상태는 대기 중입니다."),
]

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as handle:
    for index, (user, assistant) in enumerate(ROWS, start=1):
        provenance = {
            "dataset": "llmex-ko-dialogue-anchor-v1",
            "source": "repository-authored-dialogue-curriculum",
            "license": "LicenseRef-LLMEX-Internal-Curriculum",
            "collected_at": "2026-07-27",
            "source_id": f"ko-dialogue-anchor-v1-{index:04d}",
            "source_metadata": {"category": "korean-dialogue-anchor", "generator_schema": 1},
        }
        row = {
            "id": f"ko-dialogue-anchor-v1-{index:04d}",
            "schema_version": 1,
            "split": "train",
            "messages": [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}],
            "provenance": provenance,
        }
        row["sha256"] = fingerprint({"id": row["id"], "messages": row["messages"], "provenance": provenance, "split": "train"})
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    for index, (messages, assistant) in enumerate(MULTITURN_ROWS, start=len(ROWS) + 1):
        messages = [*messages, {"role": "assistant", "content": assistant}]
        provenance = {
            "dataset": "llmex-ko-dialogue-anchor-v1",
            "source": "repository-authored-dialogue-curriculum",
            "license": "LicenseRef-LLMEX-Internal-Curriculum",
            "collected_at": "2026-07-27",
            "source_id": f"ko-dialogue-anchor-v1-{index:04d}",
            "source_metadata": {"category": "korean-multiturn-memory-anchor", "generator_schema": 1},
        }
        row = {"id": f"ko-dialogue-anchor-v1-{index:04d}", "schema_version": 1, "split": "train", "messages": messages, "provenance": provenance}
        row["sha256"] = fingerprint({"id": row["id"], "messages": messages, "provenance": provenance, "split": "train"})
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
print(f"wrote {len(ROWS) + len(MULTITURN_ROWS)} rows to {OUT}")
