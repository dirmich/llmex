# LLMEX 모델 카드 1.0

LLMEX는 한국어 Wikipedia로 처음부터 학습하도록 설계한 decoder-only base LM이다. baseline 후보는
12층, 폭 768, 12/4 GQA, SwiGLU 2,048, context 1,024의 87,804,672 parameter 구성이다.

1.0.0은 학습 도구의 안정 릴리스이며 공개 가능한 완성 가중치 선언이 아니다. 전체 장기 baseline,
best/final 평가, 사람 안전 검토와 법무 승인이 대기 중이다. 대화형 assistant, 최신 사실 확인,
의료·법률·금융 조언, 사람 평가, production 자동화에 사용하지 않는다.

Wikipedia 단일 도메인, 작은 규모, 비정렬 base LM 특성 때문에 환각, 반복, 유해·편향·개인정보 또는
암기 출력이 가능하다. 법률 검토 없이 가중치 라이선스를 단정하지 않으며 외부 gate 승인 전 공개하지 않는다.
