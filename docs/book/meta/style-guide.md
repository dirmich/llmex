# 문체와 용어 가이드

- 설명과 문서는 한국어로 쓰고 코드 symbol·CLI option·artifact field는 원문 표기를 유지한다.
- 한 모듈의 설명은 책임, 입력, 출력, 불변식, 실패, 검증 순서로 쓴다.
- “안전하다”, “재현된다”, “완료됐다”는 실행 증거가 있을 때만 사용한다.
- smoke, pilot, full run, production 승인을 서로 바꿔 쓰지 않는다.
- `checkpoint`, `fingerprint`, `provenance`, `heldout`, `gate`는 처음 등장할 때 뜻을 설명한다.
- 미래 기능은 현재형이 아니라 “계약”, “과제”, “미구현”으로 표시한다.
- 개인 절대 경로, secret, private endpoint credential은 예제에 넣지 않는다.
- 명령은 저장소 루트 기준이며 기본적으로 `uv run`을 사용한다.
