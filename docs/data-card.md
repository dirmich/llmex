# LLMEX 데이터 카드 1.0

데이터는 날짜 고정 한국어 Wikipedia `pages-articles-multistream` dump의 namespace 0 본문이다.
이미지, 토론, 사용자 페이지, redirect는 대상이 아니며 원 dump와 처리 corpus는 패키지에 포함하지 않는다.

최신 revision을 streaming 추출하고 title, page/revision ID, source/dump URL, dump date, 라이선스
고지와 본문 SHA-256을 보존한다. 정책 기반 정제, NFC 정규화, 품질 필터, exact dedup 뒤 문서 hash
기반 98/1/1 split을 적용하며 각 단계 checksum을 manifest에 연결한다.

Wikipedia에는 부정확함, 편향, 개인정보, 명예훼손, 저작권 문제가 있는 문장이 포함될 수 있다.
교육·연구용 실험에 한정하고 사람 판단, 사실 확인, 자동 의사결정에 사용하지 않는다.

전체 dump 처리, 100건 사람 감사, page별 추가 고지 검토는 미완료다. 따라서 데이터 공개 gate는
실패 상태이며 외부 승인을 모두 충족해야 변경할 수 있다.
