# 4부. 대화 데이터와 teacher 증류 모듈

이 챕터는 base model을 대화 모델로 바꾸는 입력 계약부터 증류 수집, 혼합, assistant-only SFT, 자동·수동 품질 판정까지 구현한다. 실제 teacher 호출은 결정적 inventory와 offline fixture 검증이 끝난 뒤에만 연결한다.

## 대화 모듈

### `src/llmex/chat/__init__.py`

- 책임: 대화 하위 패키지의 import 경계를 선언한다.
- 구현 순서: 빈 파일로 import smoke를 통과시킨 뒤 안정된 데이터·runtime 진입점만 선택적으로 노출한다.
- 실패 사례: package import만으로 학습이나 파일 쓰기 같은 부작용이 발생하면 안 된다.
- 검증: `uv run python -c 'import llmex.chat'`와 `tests/test_g003_chat.py`를 실행한다.
- 완료 산출물: 부작용 없는 대화 패키지 namespace다.

### `src/llmex/chat/data.py`

- 책임: `Message`, `Provenance`, `ChatRow`, `ChatDataset`과 JSONL loader를 소유한다.
- 구현 순서: strict role schema → 대화 순서 → 마지막 user 정규화/hash → provenance source key → snapshot loader 순서로 만든다.
- 실패 사례: assistant로 시작하는 행, 마지막 user가 없는 행, 허가되지 않은 license와 중복 ID를 거부한다.
- 검증: `tests/test_g003_chat.py`의 schema·snapshot·provenance 테스트와 `final_user_prompt_sha256` 결정성을 확인한다.
- 완료 산출물: source SHA와 final-user prompt key를 가진 immutable chat dataset이다.

### `src/llmex/chat/template.py`

- 책임: role marker가 있는 문자열과 `TokenizedChat(input_ids, labels)`를 만든다.
- 구현 순서: `render_chat` 역할 구분자 → generation prompt → tokenizer encode → assistant span만 label 유지 순서로 구현한다.
- 실패 사례: user/system/PAD token이 loss target이 되거나 EOS가 assistant label에서 빠지면 실패한다.
- 검증: `tests/test_g003_chat.py`에서 label mask exact equality와 truncation 경계를 검사한다.
- 완료 산출물: assistant-only SFT에 바로 넣을 input/label 쌍이다.

### `src/llmex/chat/mixer.py`

- 책임: public·한 개 이상의 teacher train/heldout을 누출 없이 선택하고 byte-identical하게 게시한다.
- 구현 순서: 입력 SHA 확인 → 선택적 public upstream과 모든 teacher manifest 결속 → heldout 우선 선택 → prompt/source overlap 제거 → 길이·license gate → 원자 publish 순서다.
- 실패 사례: train/heldout prompt 또는 source overlap, 어느 upstream manifest나 JSONL의 불일치, teacher 이름 중복, 기존 산출물 충돌을 거부한다. 새 source가 없을 때는 legacy fingerprint 입력에서 새 필드를 생략해 과거 산출물을 보존한다.
- 검증: `uv run pytest -q tests/test_sft_mixer.py`와 `sft preflight-mix/prepare-mix/validate-mix`를 연속 실행한다.
- 완료 산출물: 혼합 train/heldout JSONL과 선택·제외 통계 manifest다.

### `src/llmex/chat/curriculum.py`

- 책임: 품질 실패 범주를 보정하는 결정적 합성 데이터와 기존 데이터 replay를 만든다.
- 구현 순서: suite의 모든 user turn hash 수집 → 범주별 quota 후보 생성 → split/source 분리 → 이름 있는 replay 원천별 license·category·quota 선택 → target-token 질량 계산 → 원자 publish 순서다.
- 실패 사례: 고정 suite 문장 복제, split/user/source overlap, assistant EOS 누락, 민감 출력과 기존 profile fingerprint 변화는 실패다.
- 검증: `uv run pytest -q tests/test_sft_curriculum.py`와 `sft curriculum-preflight/prepare/validate`를 실행한다. focused-v3은 잔여 범주, focused-v4는 성공 범주 replay, focused-v5는 비누출 접미 counterexample, focused-v6는 핵심 앞부분 뒤의 조건 절과 exact assistant 목표를 실습한다. focused-v12는 한국어·영어·일본어·번역·안전을 범주별 quota와 여러 replay 원천으로 결합한다. 모두 suite·split 모든 user turn overlap 0, source overlap 0, 이전 profile 불변을 확인한다.
- 완료 산출물: 범주·target-token 비중과 suite overlap 0을 증명하는 curriculum manifest다.

focused-v6 실측에서는 validation best step 40보다 step 20의 harmful refusal이 높았다. focused-v7은 그 step 20 실패에서 exact 문맥과 PII 거절만 골라 목표 token을 가중했다. 실제 step 10·20은 PII refusal 100%를 회복했지만 날짜-only 지시는 여전히 설명 문장을 출력해 multi-turn retention 66.67%였다. focused-v8은 날짜·코드·담당자·상태·장소에 같은 “갱신 뒤 값만 출력” 계약을 적용해 특정 평가 답 암기 없이 형식 일반화를 학습한다. 교재 구현은 `best.pt` 하나만 비교하지 말고 같은 suite와 seed로 중간 checkpoint를 재유도하며, loss가 낮아져도 형식 일반화가 개선되지 않을 수 있음을 실패 artifact로 기록한다.

이 실측의 핵심 원인은 모델만이 아니었다. 학습은 assistant마다 EOS를 넣었지만 과거 생성 prompt는 다중 턴 assistant EOS와 BOS를 빠뜨렸다. `render_chat`과 `tokenize_chat`의 prefix token을 직접 비교하는 테스트를 먼저 두고, 생성 응답의 종단 줄바꿈까지 정규화해야 한다. 수정 뒤 v7 step 10·20은 재학습 없이 multi-turn 100%를 회복했다. 학습 데이터를 추가하기 전에 입력 경계 동등성을 증명하는 이유다.

### `src/llmex/chat/multilingual.py`

- 책임: Qwen·Gemma에 서로 겹치지 않는 영어·일본어 대화와 한↔영·한↔일 teacher prompt inventory를 결정적으로 만든다.
- 구현 순서: 6개 task template → `prompt_index` 전단사 순열 기반 split·teacher 의미 조합 범위 분리 → train/heldout 고유 ID·provenance → canonical JSONL·manifest → 재사용 검증 순서다.
- 실패 사례: exact 문장만 다르고 train/heldout 의미 조합이 같거나 Qwen/Gemma 본문이 중복되는 경우, Reference/serial을 본문에 노출하는 경우, split/source ID 충돌과 기존 출력 불일치를 거부한다.
- 검증: `uv run pytest -q tests/test_multilingual.py`와 `uv run llmex data multilingual-prompts`를 실행하고 natural-v3의 split·teacher 의미 조합 교집합 0을 확인한다.
- 완료 산출물: 기존 v1과 의미 범위가 분리된 natural-v3 prompt JSONL, SHA가 고정된 manifest와 독립 108응답 평가 suite다.

### `src/llmex/chat/korean_prompts.py`

- 책임: Gemma4 teacher가 답할 한국어 자연대화 prompt를 10개 범주로 결정적으로 만든다.
- 구현 순서: 범주별 문형·조합 → `prompt_index` 전단사 순열 기반 split 의미 조합 범위 분리 → train/heldout 고유 ID → MIT provenance → exact·의미 중복 검사 → canonical JSONL·manifest 원자 게시 순서다.
- 실패 사례: 부자연스러운 조사·큰 수치를 생성하거나 exact 문장만 바꾼 같은 의미 조합을 train/heldout에 배치하거나, target 부족분을 Wikipedia 질문으로 자동 보충하면 자연대화 학습량이 부풀려진다.
- 검증: `uv run pytest -q tests/test_korean_prompts.py`와 `uv run llmex data korean-conversation-prompts`를 실행하고 natural-v2의 split 의미 조합 교집합 0, `distill prepare`의 고유 request target 일치와 `wikipedia_rows_examined=0`을 확인한다.
- 완료 산출물: 의미 범위를 분리한 natural-v2 고유 prompt, SHA와 범주·split 통계가 고정된 manifest다.

### `src/llmex/chat/runtime.py`

- 책임: SFT token cache, 학습·재개·평가·생성을 `SFTTrainer`로 조립한다.
- 구현 순서: dataset/base SHA 결속 → 두 번 tokenization digest → 연속 cache → target-token 가중 accumulation → validation/best checkpoint → 재개 상태 감사 순서다.
- 실패 사례: 기존 run에 fresh start, base SHA 불일치, 비유한 optimizer/RNG 상태, sampler 위치 불일치와 128 MiB cache 초과를 거부한다.
- 검증: `uv run llmex sft preflight --config <설정> --measure-baseline`, 표적 chat 테스트, 중단·재개 parity를 실행한다.
- 완료 산출물: metrics JSONL, best/latest checkpoint, 입력 fingerprint와 release 정책이 결속된 manifest다.

### `src/llmex/chat/memory.py`

- 책임: 최신 사용자 발화에서 명시적으로 제공된 사실·identity·안전 요청만 보수적으로 재호출한다.
- 구현 순서: 사용자 메시지 history 추출 → exact 사실·정정 규칙 → 최신 값 우선 regex → 모르는 내용은 `None`으로 위임하는 순서다.
- 실패 사례: assistant가 말하지 않은 내용을 기억한다고 주장하거나, 오래된 값을 최신 정정값보다 우선하거나, 모든 질문을 고정 답변으로 가로채면 안 된다.
- 검증: `uv run pytest -q tests/test_foundation.py -k memory`와 quality suite의 multi-turn retention·identity·안전 시나리오를 함께 실행한다.
- 완료 산출물: 모델 가중치 학습과 구분되는 deterministic fallback 모듈과 회귀 테스트다.

### `src/llmex/chat/quality.py`

- 책임: 실제 멀티턴 rollout에서 EOS·반복·정확성·안전·오염 지표와 gate를 계산한다.
- 구현 순서: suite/SFT/checkpoint SHA 확인 → profile별 rollout → `response_metrics` → 전체·profile·scenario worst case → 재생성 가능한 report 순서다.
- 실패 사례: 평균만으로 worst case를 숨기거나, 이전 assistant 응답 대신 정답 history를 넣거나, 산출물 byte 변조를 허용하면 실패한다.
- 검증: `uv run pytest -q tests/test_sft_quality.py`와 `sft quality-preflight/quality-eval/quality-validate`를 실행한다.
- 완료 산출물: row JSONL, 자동 품질 JSON/Markdown, 입력·출력 SHA와 gate 판정이다.

### `src/llmex/chat/quality_review.py`

- 책임: blind review template과 독립 reviewer·adjudicator 서명 gate를 검증한다.
- 구현 순서: 자동 gate 확인 → blind target 생성 → review schema/역할 검증 → disagreement 판정 → 서명 context/target SHA 확인 → 원자 gate 게시 순서다.
- 실패 사례: unsigned review, 자기 승인, 역할 중복, 자동 gate 이전 review와 다른 checkpoint target을 거부한다.
- 검증: `tests/test_sft_quality.py`의 review·gate 테스트와 `sft quality-review-template/quality-review-validate`를 사용한다.
- 완료 산출물: 독립 검토자가 작성할 blind template과 검증된 경우에만 생성되는 수동 gate artifact다.

## Teacher 증류 모듈

### `src/llmex/distill/__init__.py`

- 책임: 증류 패키지 경계다.
- 구현 순서: 빈 namespace에서 시작하고 collector의 안정된 진입점만 공개한다.
- 실패 사례: import 시 endpoint 접속이나 spool 변경이 일어나면 안 된다.
- 검증: `uv run python -c 'import llmex.distill'`를 실행한다.
- 완료 산출물: 부작용 없는 증류 namespace다.

### `src/llmex/distill/schema.py`

- 책임: `SourceProvenance`, `LogicalRequest`, `SpoolRecord`의 strict schema를 정의한다.
- 구현 순서: source identity → logical request ID → 응답·시도·filter 상태 결속 순서로 필드를 만든다.
- 실패 사례: source SHA, request ID, model identity 또는 raw response digest가 맞지 않는 spool을 거부한다.
- 검증: `uv run pytest -q tests/test_distill.py`의 schema·변조 사례를 실행한다.
- 완료 산출물: 재개 가능한 요청별 증류 상태 계약이다.

### `src/llmex/distill/prompts.py`

- 책임: public chat/wiki source를 정규화해 결정적 prompt inventory를 만든다.
- 구현 순서: 입력 snapshot → source별 prompt 변환 → canonical 중복 제거 → hash split → exact target 수 선택 순서다.
- 실패 사례: 입력 순서에 따라 inventory가 달라지거나 train/heldout request가 겹치면 실패한다.
- 검증: `tests/test_distill.py`에서 순서 변화·중복·split 결정을 검사한다.
- 완료 산출물: request ID, source provenance, split이 고정된 inventory다.

### `src/llmex/distill/client.py`

- 책임: OpenAI-compatible localhost endpoint의 model preflight와 completion 요청을 제한적으로 수행한다.
- 구현 순서: no-redirect opener → model identity → canonical request body → 응답 byte 상한 → secret echo 검사 순서다.
- 실패 사례: 미등록 비-loopback endpoint, redirect, timeout, 과대 응답, 다른 model과 secret 반사를 거부한다.
- 검증: fixture HTTP server 기반 `tests/test_distill.py`; 실제 연결은 `uv run llmex distill preflight --config <설정>`으로 확인한다.
- 완료 산출물: raw request/response bytes와 model identity가 검증된 단일 호출 결과다.

### `src/llmex/distill/filters.py`

- 책임: 일반 응답 형식과 source에 결속된 목표 언어·응답 모드·사실 보존 계약을 판정하고 canonical response를 만든다.
- 구현 순서: Unicode/safety/반복/복사 → target script → 문장/직접성 → 숫자·entity·핵심 용어 → uncertainty 경계 순서다.
- 실패 사례: 일반 휴리스틱만 통과한 일본어 원문, `notebook→노트북`, 메시지 뒤 설명, 조회할 수 없는 실시간 상태 단정을 학습 가능으로 오인하면 안 된다.
- 검증: `tests/test_distill.py`와 `tests/test_distill_quality.py`에서 정상·실패 경계와 metadata 보존을 실행한다.
- 완료 산출물: 안정된 rejection reason 또는 자동 계약을 통과한 canonical assistant text다. 실제 학습 승인은 task/category 균등 표본 감사까지 필요하다.

### `src/llmex/distill/collector.py`

- 책임: `preflight → prepare → collect/resume → status → export → validate` 전체 상태 기계를 소유한다.
- 구현 순서: 입력 snapshot/manifest → 요청별 원자 spool → 제한 병렬 수집·재시도 → 상태 집계 → chat export → byte 재검산 순서다.
- 실패 사례: config/source/model/response-quality 결속이 다른 spool, live 충돌, 부분 write, export 후 변조를 거부한다. 표본 감사 전 export하지 않는다.
- 검증: `uv run pytest -q tests/test_distill.py`와 모든 `llmex distill` 하위 명령을 offline fixture부터 순서대로 실행한다.
- 완료 산출물: inventory, request별 spool, collection state, train/heldout chat export와 manifest다.

## 챕터 종료 체크

- [ ] 모든 chat row가 provenance와 결정적 final-user hash를 가진다.
- [ ] teacher inventory와 mix/curriculum split의 prompt·source overlap이 0이다.
- [ ] source task별 목표 언어·번역 의미·writing 직접성·uncertainty 경계를 자동 gate와 균등 표본 감사가 모두 통과한다.
- [ ] assistant-only label에 EOS가 포함되고 user/system/PAD는 `-100`이다.
- [ ] 자동 품질 artifact는 원 입력에서 byte 단위 재생성된다.
- [ ] 수동 승인을 개발자 자신의 unsigned 파일로 대체하지 않는다.
