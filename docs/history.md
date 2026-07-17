# 구현 이력

## 2026-07-18 · 1.9.5 모듈별 단계 학습 교재

### 56개 모듈 전수 지도와 제작 워크북

- `src/llmex`의 Python 파일 56개를 기반, 데이터, tokenizer, model, pretraining, inference/evaluation, chat/SFT, distillation, pipeline/trust/release 순으로 전수 연결했다. 각 모듈에 책임, 주요 입력·출력, 직접 구현할 불변식과 완료 증거를 기록했다.
- 빈 저장소에서 공통 기반→원자 I/O→Wikipedia→BPE→Transformer→완전 재개 학습→평가→chat schema→teacher→mix→SFT→자동 품질→수동·release를 만드는 0~12단계 워크북을 추가했다. CPU fixture, CUDA pilot, DGX Spark 장기 실행과 localhost teacher의 자원·네트워크·중단 경계를 분리했다.
- 장별 진단과 exit ticket, 필수 변조 실험 3개, 기능 40·재현성 25·무결성 20·해석 15점의 capstone rubric을 추가했다. 실행 성공과 개념 이해, 자동 품질과 외부 사람 승인을 구분한다.

### 책 제작 근거와 정합성 교정

- 독자 brief, 한국어 문체·용어, 내부·외부 출처 권위, 구현·수치 주장 원장과 AI 보조 검증 원칙을 `docs/book/meta`에 추가했다. `../knowledge_base`의 프로젝트 계획은 M0부터 1.5.2까지 누적된 운영 snapshot이며 현재 저장소보다 후순위임을 명시했다.
- 독립 감사에서 찾은 존재하지 않는 `materialize` 단계, 자동 품질의 잘못된 SHA 세트, `runs/sft-smoke` 경로, 생성되지 않는 checkpoint SHA sidecar 설명을 현재 CLI와 구현에 맞게 교정했다.
- GGUF/llama.cpp는 현재 구현된 기능이 아니라 후속 acceptance contract임을 본문과 capstone에 분명히 표시했다. 00~08 fixture capstone과 09~14 gated extension을 분리해 도움말 확인을 전체 완주로 오인하지 않게 했다.

### 검증

- 56개 source module이 모듈 지도에 모두 포함되는지 전수 검사하고 percent-encoding을 해석한 교재 내부 링크 누락 0, 예제 설정 3종 strict validation과 워크북 CLI 표면을 확인했다. `data sample-e2e`의 완전한 명령은 실제 dry-run으로 검증했다.
- 전체 `165 passed`, Ruff lint/71파일 format, Pyright strict 오류 0, release audit와 `git diff --check`를 통과했다. 독립 리뷰가 처음 지적한 실행 불가 명령과 구현 경계 과장을 모두 교정한 뒤 HIGH/MEDIUM 없이 최종 `APPROVE`를 받았다.
- 정식 qwen36mtp v5 수집은 중단하지 않고 계속 진행한다.

## 2026-07-18 · 1.9.4 상한 결속 SFT token cache

### 반복 tokenization 제거

- 기존 runtime은 trainer 초기화에서 모든 train/heldout 대화의 길이를 tokenization한 뒤 학습·validation batch마다 같은 대화를 다시 tokenization했다. 이제 1차 pass에서 기존 전체 길이·assistant target·generation prompt gate를 그대로 수행하고 input/label 전체 SHA-256을 임시 결속한다.
- 영속 cache는 train/heldout split마다 연속 int32 input, 연속 int32 label, int64 offsets 하나로 구성한다. 데이터 행 수와 무관하게 tensor 6개와 cache wrapper 2개만 유지하며 sampler index 순서로 필요한 구간만 long batch에 복사·패딩한다.
- 2차 tokenization의 길이와 input/label SHA가 1차와 완전히 같을 때만 정확한 크기의 buffer를 채운다. 동일 길이 token 변조, train/heldout cache 오결속과 외부 dataset batch 요청은 sampler 진행 전에 실패-폐쇄한다.

### 메모리 상한과 실제 실측

- input·label storage와 split별 `(rows+1)` offsets를 모두 합친 persistent bytes를 Python 정수로 계산한다. 완화 불가 128 MiB를 넘으면 연속 buffer 할당을 한 번도 하지 않으며, preflight에 split/total 행·token·세 storage byte, dtype, tensor 수와 cap을 기록한다.
- 실제 public 6,853행 + v5 pilot teacher 28행의 검증된 mix 4,732행에서 train 3,091,998 token, heldout 343,623 token, 합계 3,435,621 token과 27,522,840 bytes를 기록했다. CPU preflight는 28.88초, 최대 RSS 3,062,108 KiB였다.
- 같은 실제 cache의 첫 4행을 100회 조립한 micro benchmark는 cached 0.00696초, 재-tokenization 0.38310초로 batch 준비가 약 55배 빨랐다. 이는 model forward/backward를 포함하지 않는 준비 구간 수치다.

### 검증과 독립 검토

- 기존 `_batch`와 cached tensor의 input/label/PAD/-100 exact equality, 학습 중 tokenization 0회, 2-pass 동일 길이 변조 거부, cap 초과 allocation·sampler 0회, train/heldout 분리와 continuous/resume bitwise 결정성을 회귀로 고정했다.
- 전체 165 tests, Ruff lint/format, Pyright strict와 `git diff --check`를 통과했다. 독립 리뷰의 행별 Python tuple 메모리 증폭과 행별 tensor allocator MEDIUM을 연속 buffer로 폐쇄한 뒤 최종 `APPROVE`를 받았다.
- 정식 qwen36mtp v5 수집은 계속 진행 중이다. 완료된 정식 mix의 token cache 통계와 CUDA pilot step 시간을 다시 측정해 full 예산을 확정한다.

## 2026-07-18 · 1.9.3 fresh SFT 실행 경계

### 새 학습과 재개의 권한 분리

- `sft train`과 public `train_sft(..., resume=None)`은 trainer를 초기화하기 전에 `run_dir`가 존재하는지 검사한다. 빈 디렉터리, 사용자 파일이 있는 디렉터리, pilot·완료 run을 모두 실패-폐쇄해 과거 산출물을 덮어쓰지 않는다.
- 직접 `SFTTrainer.run()`을 호출하는 경로도 쓰기 직전에 같은 검사를 반복하고 `mkdir(parents=True, exist_ok=False)`로 경합 승자를 원자적으로 결정한다. 독립 2-thread probe에서 정확히 한 run만 성공하고 다른 하나는 쓰기 전에 `ConflictError`로 종료했다.
- checkpoint의 전체 fingerprint·optimizer·scheduler·sampler·RNG·precision·release 상태를 strict 복원한 `resume` 또는 `restore_checkpoint`만 기존 run 디렉터리에 계속 기록할 권한을 얻는다. 복원 실패는 이 권한을 만들지 않는다.
- 외부 base checkpoint에서 새 run을 만드는 기존 기능은 유지한다. pilot과 full은 동일한 100k `latest` SHA에 결속하되 서로 다른 미존재 run 디렉터리에서 각각 step 0부터 시작하며, full은 pilot checkpoint를 이어받지 않는다.

### 정식 학습 계획과 교재 동기화

- `docs/chat-sft.md`, `docs/run-guide.md`와 모듈별 교재 11장에 fresh train/resume 명령 경계와 pilot/full 분리를 추가했다.
- 최종 mix train 행 수 `N`, micro batch 4, accumulation 16의 약 3 epoch 시작값을 `ceil(3 × floor(N / 4) / 16)`으로 기록했다. sampler가 epoch tail을 버리므로 정확한 3 epoch로 주장하지 않고 pilot 실측 시간·loss·GPU 사용률로 full 예산을 확정한다.
- 정식 qwen36mtp v5 수집은 계속 진행 중이며 GPU는 teacher에만 사용한다. 완료 후 export/validate와 실제 mix 행 수를 확정해야 production pilot/full YAML을 만들 수 있다.

### 검증

- 기존 빈/비어있지 않은/완료 run 거부와 파일 byte 보존, CLI train 실패/resume 성공, 외부 checkpoint에서 서로 다른 fresh pilot/full 시작, preflight 무출력을 회귀로 고정했다.
- 전체 162 tests, Ruff lint/format, Pyright strict와 `git diff --check`를 통과했다. 독립 code review는 19개 표적 테스트와 별도 2-thread 경합 probe 후 HIGH/MEDIUM 없이 `APPROVE`했다.

## 2026-07-18 · 1.9.2 공개 원행과 teacher provenance 결속 교정

### 실제 혼합 사전검증에서 발견한 원행 붕괴

- 공개 instruction 6,853행과 완료된 v5 pilot teacher 28행을 함께 넣은 실제 사전검증에서 입력 6,881행 중 train이 25행만 남고 `heldout_source_from_train`으로 4,251행이 제외되는 이상을 확인했다.
- 공개 변환 행은 `source_id`와 `source_sha256`이 없고 dataset/source URL을 공유한다. 기존 fallback은 이 두 필드만으로 원천 키를 만들어 공개 데이터 전체를 하나의 가상 upstream source로 취급했고, 공개 heldout 하나가 거의 모든 공개 train을 격리했다.
- teacher 행은 원래 공개 `ChatRow.id`와 `ChatRow.sha256`을 `source_id`와 `source_sha256`으로 보존한다. 따라서 coarse dataset URL이 아니라 실제 입력 원행 identity를 fallback으로 써야 teacher heldout과 대응하는 공개 원행 하나만 정확히 결속할 수 있다.

### 구현한 identity 우선순위와 출력 계약

- provenance 원천 키를 `source_sha256 → 명시 source_id의 canonical fingerprint → 호출자가 검증한 입력 행 SHA-256 → 기존 coarse fingerprint` 순서로 결정한다. 명시 source ID는 fallback 변화와 무관하고, 명시 source SHA는 언제나 최우선이다.
- mixer는 schema와 canonical row SHA를 검증한 `ChatRow.sha256`만 fallback으로 넘긴다. 출력에는 기존 `source_id`/`source_sha256`을 절대 덮어쓰지 않으며, 둘 다 없는 행에만 원행 ID와 원행 SHA를 승격해 이후 SFT runtime도 동일 identity로 split overlap을 재검사하게 한다.
- heldout source를 train 선택 전에 예약하는 기존 실패-폐쇄 계약, prompt/source 최종 교집합 0, teacher export manifest와 입력 파일 SHA 결속, 결정적 정렬·재사용·재유도 검증은 유지했다.

### 실제 재유도 결과와 검증

- 수정 후 같은 pilot 입력 6,881행에서 train 4,257행(public 4,238 + teacher 19), heldout 475행(public 472 + teacher 3)을 선택했다. 선택 4,732행과 제외 2,149행의 합이 입력과 정확히 일치한다.
- 제외는 sequence 초과 1,743, heldout prompt의 train 대응 255, prompt 초과 77, 민감 assistant 출력 39, 동일 source+prompt 중복 19, heldout prompt 중복 16이다. 수정 전 발생한 4,251행의 원천 일괄 격리는 사라졌다.
- 동일 dataset/source를 공유하지만 identity가 없는 공개 행은 서로 다른 원행으로 남고, teacher heldout의 `source_sha256`이 가리키는 공개 train 원행 하나만 제외되는 회귀를 추가했다. 출력 4,732행에 runtime용 identity가 모두 존재하며 source/prompt overlap은 0이다.
- 모듈별 실습 교재의 public+teacher 혼합 장도 같은 identity 우선순위, 행 SHA fallback과 출력 identity 승격 계약으로 갱신해 구현과 학습 자료가 어긋나지 않게 했다.
- 전체 160 tests, Ruff lint/format, Pyright strict와 `git diff --check`를 통과했다. 독립 code review는 실제 pilot 설정을 읽기 전용으로 재유도한 뒤 HIGH/MEDIUM 없이 `APPROVE`했다.
- `../knowledge_base/Codex/LLMEX/프로젝트 계획.md`의 문서 단위 hash split, attribution 보존과 split 누출 즉시 중단 원칙을 실제 원행 단위로 적용했다. provenance의 의미적 진실성은 여전히 입력 파일과 teacher manifest의 무결성에 의존하며 외부 서명을 새로 가정하지 않는다.
- 정식 qwen36mtp v5 10k 수집은 계속 진행 중이다. 완료 후 정식 export/validate와 동일 mix gate를 다시 수행하고 실제 선택 행 수로 pilot·fresh full SFT step을 확정한다.

## 2026-07-18 · 1.9.1 SFT 민감 출력 선필터와 원자 산출물 강화

### 학습 데이터 민감 출력 차단

- 공개·teacher의 train/heldout 전체에서 마지막 응답만이 아니라 모든 assistant turn을 길이 gate보다 먼저 검사한다. 주민등록번호, 한국 휴대전화, 이메일과 API key/secret 할당 built-in 규칙은 설정으로 완화하거나 덮어쓸 수 없다.
- ASCII 숫자·이메일 경계를 명시해 `010-1234-5678은`, `mail@example.com으로`처럼 한국어 조사가 붙은 출력도 탐지한다. 반대로 `notsecret`와 `xapi_key` 같은 더 긴 식별자 내부 substring은 secret으로 오탐하지 않는다.
- assistant content가 65,536자를 넘으면 정규식을 실행하지 않고 전용 길이 규칙으로 실패-폐쇄 제외한다. 외부 artifact에는 원문이나 검출 문자열을 남기지 않고 source·split·규칙별 건수만 기록한다.
- 이름 있는 추가 패턴은 최대 256자의 고정 폭 안전 부분집합으로 제한했다. 그룹, 교대, lookaround, backreference, 중괄호와 반복 quantifier를 설정 검증에서 거부해 `(a+)+$` 같은 ReDoS 입력이 실행 경로에 도달하지 못한다. 예약된 길이 규칙 이름도 사용자 규칙이 재사용할 수 없다.
- 자동 품질 평가도 같은 완화 불가 PII/secret built-in을 재사용하고 사용자 unsafe/PII/secret 패턴에 같은 안전 부분집합 검증을 적용한다. suite assertion은 기존 공백·교대 표현을 보존하되 중첩 반복, 반복된 교대, 인접·모호 다중 반복, backreference, lookaround와 `{,m}` 우회를 거부한다.

### 원자 publish와 실제 데이터 보존

- SFT mix와 자동 quality 세 파일은 출력 parent의 경로별 고유 lock, sibling staging, 파일·staging directory fsync를 거친 뒤 완성된 디렉터리 하나를 단일 `os.replace`로 publish한다. 교체 실패 시 출력 디렉터리나 부분 파일을 남기지 않으며 stale staging·부분 출력·동시 실행은 실패-폐쇄한다.
- 임시 `/tmp`에 있던 공개 instruction을 `data/chat/public/korean-instruction-v1`로 보존했다. 원천은 Apache-2.0 `CarrotAI/ko-instruction-dataset` revision `5c0e2c0180b50400e401dd0b296043f18fc6cb3f`이며 원본·라이선스·URL·provenance·checksums와 변환 manifest를 함께 유지한다.
- 공개 변환 결과는 train 6,204행 SHA-256 `68e9a90e2f58288e135a00f4a86905273341771f7c266b19656e029ca8783c0f`, heldout 649행 SHA-256 `735871877d8cbc518faee3f62b7f90f7940acd5ffd0d96a9ce0e0c71370d503b`로 원래 변환물과 일치했다. 대용량 data는 Git에서 제외하고 문서와 실행 config만 추적한다.
- `../knowledge_base/Codex/LLMEX/프로젝트 계획.md`의 attribution 보존, split 누출·개인정보 실패 즉시 중단, 공개 전 개인정보 검토 원칙을 적용했다. 실제 저장소와 최신 사용자 지시를 권위로 유지했다.

### 검증과 진행 상태

- 한국어 접미 직접 probe, secret 오탐 probe, ReDoS 설정 거부, 전 assistant turn·source/split 집계, publish 실패 주입과 동시 실행·stale·reuse 회귀를 추가했다.
- 전체 159 tests, Ruff lint/format, Pyright strict와 `git diff --check`를 통과했다. 독립 code review는 `APPROVE`, architecture review는 `CLEAR`였으며 한국어 경계, ReDoS, 원자 publish와 예약 이름 계약을 직접 probe했다.
- 정식 qwen36mtp v5 10k 수집은 계속 진행 중이다. 완료 수는 고정하지 않으며 `uv run llmex distill status --config configs/distill/qwen36mtp-10k.yaml`로 확인한다. 완료 후 export/validate·mix·baseline preflight·pilot·fresh full SFT·자동/수동 품질 순서를 유지한다.

## 2026-07-18 · 1.9.0 수학 기반 이론·Python 실습 교재

### 교재 구성과 권위 경계

- [교재 README](book/README.md)와 00~15장까지 총 17개 Markdown을 추가했다. 모든 장은 학습 목표, 선행지식, 관련 실제 파일, 핵심 개념, 단계별 구현, 실제 명령, 예상 산출물, 검증 테스트, 흔한 실패와 해결, 체크리스트, 연습문제의 11개 공통 학습 섹션을 갖는다.
- `docs/book/examples/build-smoke-corpus.py`와 tokenizer·pretrain·evaluation YAML 3종을 추가했다. 생성 data, tokenizer artifact와 training run은 Git 제외 경로에만 만들며 교재에는 재현 가능한 source와 설정만 포함한다.
- 외부 `knowledge_base`의 프로젝트 계획은 작성 날짜와 당시 SHA에 결속된 역사 참고 snapshot으로 한정했다. 현재 동작의 권위는 이 저장소의 `src/llmex`, `configs`, `docs`와 CLI `--help`이며, 과거 절대 경로나 M0 지시를 현재 실행 계약으로 복제하지 않는다.

### 실제 구현 계약 교정

- tokenizer pack은 BOS 없이 문서 text와 EOS를 이어 고정 크기 little-endian `.bin`으로 기록하고 문서가 shard를 넘을 수 있는 실제 전역 boundary 계약으로 설명했다.
- chat template은 role prefix와 content를 분리 encode하고 assistant content와 assistant EOS만 label로 남기며, 왼쪽 truncation 뒤 assistant label이 없으면 실패하는 실제 계약에 맞췄다.
- tokenizer→pretrain→evaluation, teacher→mix→SFT→자동·수동 품질→release의 상대 경로와 SHA 전달을 연결했다. production `artifacts/tokenizers/bpe-16k`와 교재 smoke `artifacts/tokenizers/book-smoke-bpe`를 분리해 기존 실물 artifact와 충돌하지 않는다.
- 수동 review는 population 100 미만 즉시 실패, 최소 100개와 safety 전수, 단일 effective matrix와 invocation당 하나의 `TrustContext`를 사용한다. release는 법무·baseline·quality-release·release 네 외부 gate와 strict manual evidence 의미를 검증한다.

### 결정적 smoke E2E 실행 결과

- 합성 corpus는 완전한 provenance schema 문서를 train/validation/test에 6/6/6개로 고정하고 두 번 생성한 compressed corpus SHA가 동일했다.
- 요청/실제 tokenizer vocab은 16,000/16,000으로 일치했다. shard token은 train 25,445, validation 97,959, test 105,216으로 각 split이 sequence length 256을 충분히 넘었다.
- 격리 CPU 10-step pretrain은 최종 loss 9.7193, best validation loss 9.6789로 완료됐다. evaluation은 validation/test에서 각각 predicted token 255를 실제 계산했다.
- canary provenance는 smoke 예제에 의도적으로 넣지 않아 `미실행/실패`로 유지했다. 이는 안전 증거 부재를 통과로 바꾸지 않는 실패-폐쇄 계약이며 E2E 명령 실패가 아니다.

### 검증과 승인

- 교재 17개 Markdown의 로컬 링크 157개를 검사해 깨진 링크 0개를 확인했다.
- M1/M2/M4/M5 표적 회귀 45 tests, generator Ruff lint/format, Pyright, tokenizer/training/evaluation config schema 검증을 통과했다.
- 독립 아키텍처 재검토의 HIGH/MEDIUM 지적을 모두 폐쇄하고 최종 `APPROVE`를 받았다.

## 2026-07-18 · 1.8.1 서명된 수동 blind review와 release 결속

### 구현 완료: 수동 review 입력과 결정적 표본

- `llmex sft quality-review-template`, `quality-gate`, `quality-review-validate`를 추가했다. template은 통과한 자동 quality 결과의 canonical full-row hash, results/report/manifest SHA-256과 sampling challenge에 결속된다.
- 자동 결과 population이 100개 미만이면 즉시 실패한다. 100개 이상에서는 safety-critical response를 전수 포함하고 profile·seed·category·profile-seed·multi-turn coverage를 유지하면서 최소 100개를 SHA-256 순서로 결정적으로 선택한다.
- reviewer에게는 대화 `context`, 응답, category, rubric과 결속 hash만 제공한다. decoding profile·seed, checkpoint/teacher 정보, 기대 판정·자동 점수는 blind template에서 제거해 검토 누출을 막는다.

### 구현 완료: 독립 서명과 품질 판정

- quality reviewer는 정확히 2명, safety reviewer는 정확히 1명이며 큰 비-safety 점수 불일치가 있을 때만 adjudicator 1명을 허용한다. identity, issuer와 Ed25519 공개키 authority를 모두 서로 다르게 요구한다.
- 한 invocation에서 Git commit, 고정 root가 서명한 trust policy bytes와 issuer map을 한 번 snapshot한다. 모든 review/adjudication 서명은 같은 context에서 role·kind·RFC3339 발급/만료·target·exact item/response/full-row hash 집합을 검증한다.
- safety 점수의 큰 불일치는 adjudication으로 덮을 수 없고 즉시 veto한다. critical flag와 safety reviewer 4점 미만도 즉시 실패한다.
- 각 item/criterion은 adjudication resolved score 또는 두 quality reviewer 평균 중 하나의 canonical effective score를 갖는다. 같은 matrix로 전체 평균, 핵심 4점 이상 item 비율, dimension 평균과 category 핵심 평균을 계산한다. 전체 핵심 평균 4.0, 핵심 4점 이상 item 90%, 모든 dimension/category 4.0 이상을 요구한다.

### artifact·release·신뢰 경계

- template과 gate artifact는 배타 lock, staging, fsync와 원자 교체로 publish하며 처음 snapshot한 bytes로 재검증한다. 부분 출력, symlink, 중복 submission, ABA 교체와 checksum/fingerprint 변조는 실패-폐쇄된다.
- release 외부 gate에 `수동 품질 평가`를 네 번째 필수 gate로 추가했다. manual manifest/report의 exact schema, canonical fingerprint, report SHA, 최소 100 표본, 모든 metric·worst 값, reviewer/submission/adjudication 수, safety/sample·점수 평균·이산 통과 count 관계와 release version·Git commit·config fingerprint를 strict 검증한다.
- release의 법무·baseline·수동 품질·공개 결정 서명은 한 번 snapshot한 동일 `TrustContext`와 commit으로 검증한다.
- production `.llmex/trust-policy.json`에는 신규 `quality-reviewer`, `safety-reviewer`, `quality-adjudicator`, `quality-release` 역할을 등록하지 않았다. 고정 root private key가 없는 상태에서 policy를 자체 서명하거나 훼손하지 않았으며, 보호 환경이 적법한 policy와 evidence를 발급하기 전 실제 운영 gate는 의도적으로 실패-폐쇄된다.

### 검증 결과와 남은 실제 작업

- 독립 code-reviewer와 architect의 반복 재검토에서 모든 HIGH/MEDIUM과 architecture WATCH를 폐쇄하고 최종 `APPROVE`를 받았다.
- `uv run pytest -q` 148 tests, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`를 통과했다.
- 1.8.1은 수동 gate 소프트웨어 구현 완료를 뜻한다. 정식 v5 teacher 수집과 혼합 SFT가 끝난 실제 best/latest 모델에 대해 template을 만들고 사람이 quality·safety review를 수행한 것은 아니다. 따라서 현재 모델의 수동 품질이나 공개 배포는 승인되지 않았다.
- 정식 `qwen36mtp-10k-v5` 수집은 동적 상태다. 변하는 completed/pending 수를 이력에 고정하지 않고 `uv run llmex distill status --config configs/distill/qwen36mtp-10k.yaml`로 확인한다.

## 2026-07-18 · 1.8.0 SHA 고정 자동 대화 품질 gate

### 완료: 실제 멀티턴 자동 평가

- 프로젝트 계획의 attribution·split·tokenizer·checkpoint 실패 즉시 중단과 공개 전 contamination·암기·개인정보·라이선스 검토 원칙을 자동 대화 품질 gate에 적용했다.
- `llmex sft quality-preflight/eval/status/validate`와 `sft-quality` 설정 kind를 구현했다. SFT config, schema 2 checkpoint와 suite의 예상 SHA-256을 필수로 고정하고 처음 읽은 snapshot bytes를 로딩·복원의 단일 원본으로 사용한다. 경로가 검증 중 교체되는 ABA와 SHA 불일치는 실패한다.
- release policy, SFT train/heldout과 suite canonical prompt overlap, `deterministic: true`, harmful·benign·multi-turn 분모와 category coverage를 평가 전에 실패-폐쇄한다.
- 모델의 실제 응답을 다음 turn history에 삽입하는 multi-turn rollout을 구현했다. greedy temperature 0·seed 1개와 sampling 양의 temperature·합계 최소 5개 고정 seed를 강제한다.
- MIT `data/evaluation/ko-chat-quality-v1.jsonl`에 24 scenarios·27 unique turns를 고정했다. canonical greedy 1회+sampling 5회 계획은 162 responses다. 공개 SFT 고유 prompt 5,813개와 teacher inventory 10,000개에 대한 canonical exact overlap은 0이다.
- 응답마다 EOS, max tokens, context limit 종료를 구분하고 고정 heldout의 assistant target-token 가중 NLL·PPL·token 수를 기록한다. correctness, harmful refusal, benign false-refusal, unsafe·PII·secret, Unicode/control character, empty, distinct-1/2, 2/3/4-gram 3회 연속 hard loop와 반복 token run을 측정한다.
- aggregate, category, profile, seed, profile-seed, category-profile-seed를 기록하고 profile-seed 최악값과 범주별 gate를 판정한다. 기본 최소값은 refusal 0.95, false-refusal 최대 0.05, EOS 0.99, correctness·multi-turn retention 0.90이며 완전성·Unicode·context는 100%, critical pattern·hard loop는 0이다.
- 평가 출력은 배타 lock과 전용 staging에서 만든 뒤 `results.jsonl`, `report.json`, `manifest.json` 순서로 manifest를 마지막에 원자 publish한다. 기존 부분 출력·남은 staging을 거부하고 validate에서 현재 pinned snapshot으로 전체 결과를 다시 만들어 byte 단위로 비교한다.
- teacher judge는 비활성화했고 향후에도 advisory-only다. 증류 label을 만든 teacher 점수는 독립적인 최종 품질 판정이 아니다.

### 구현 검증과 후속 경계

- 자동 품질 gate는 독립 리뷰에서 APPROVE 판정을 받았다.
- 전체 145 tests 실행이 통과했다. release/overlap/deterministic/coverage 실패, 실제 rollout, 고정 seed, weighted loss, 종료 원인, 안전·반복 지표, 동시 실행·부분 출력·SHA/ABA·artifact 변조 회귀를 포함한다. Ruff lint·format과 Pyright도 오류 없이 통과했다.
- 정식 `qwen36mtp-10k-v5` 수집은 이 문서 작성 시점에도 진행 중이다. 변하는 완료 건수는 이력에 고정하지 않고 `uv run llmex distill status --config configs/distill/qwen36mtp-10k.yaml`로 확인한다.
- 수동 blind review, 응답 hash 결속, 독립 검토자·안전 검토자, 서명과 승인 gate는 1.8.1 후속 작업이다. 따라서 자동 gate 구현·통과만으로 대화 가능성 또는 외부 공개를 승인하지 않는다.

## 2026-07-17 · 1.7.1 SFT 실제 preflight와 step-0 기준선

- `llmex sft preflight --config <경로> --measure-baseline|--no-measure-baseline`을 추가했다. 기존 `train --dry-run`의 설정 fingerprint 확인보다 강하게 실제 train/heldout schema·license·canonical 누출, tokenizer와 source manifest 결속·release·길이 gate, base checkpoint, device·precision 및 모델/optimizer 초기화를 수행한다.
- 성공 출력은 확정 device·precision, 중복 없이 센 고유 파라미터 수, train/heldout 행 수·fingerprint·파일 SHA-256, 전체 fingerprint, base provenance, redistribution/release 상태와 `micro_batch_size × gradient_accumulation_steps` 유효 batch를 기록한다.
- `--measure-baseline`은 학습과 같은 seed의 고정 validation subset에서 assistant target token 수로 가중한 step-0 loss, perplexity와 target token 수를 측정한다. `--no-measure-baseline`은 전체 초기화 검증만 수행하며 기본값이다.
- 측정은 run 디렉터리와 파일을 만들지 않고 validation sampler·누적 batch 수, Python/NumPy/PyTorch RNG, 모델 train/eval mode, deterministic algorithms의 enabled·warn-only와 cuDNN benchmark 상태를 성공·오류 모두 원래대로 복원한다. 입력·device·precision·base·길이 또는 비유한 loss 오류는 실패-폐쇄한다.
- 독립 리뷰의 deterministic `warn_only` 복원 MEDIUM 지적을 수정한 뒤 최종 승인을 받았다. 전체 137 tests, Ruff와 Pyright를 통과했다.
- `../knowledge_base/Codex/LLMEX/프로젝트 계획.md`의 split 누출·checkpoint 복구 실패 즉시 중단과 smoke 선행 품질 gate를 따른다. 정식 v5 진행 건수는 고정하지 않고 `distill status`로 확인하며, 이후 순서는 `export/validate → mix → baseline 측정 preflight → pilot → 동일 heldout 평가 비교`다.

## 2026-07-17 · 1.7.0 공개·teacher 비누출 SFT mix

### 실측한 concat 차단 근거

- 공개 instruction만 비교해도 train/heldout 사이 canonical final-user prompt 152개가 겹쳤다.
- 정식 v5 inventory와 함께 비교하면 공개 train과 teacher heldout이 658개 고유 prompt에서 겹치며 공개 train 879행이 영향을 받았다. 행 전체 hash만 다른 데이터를 직접 concat하면 heldout 질문이 학습에 들어가므로 단순 병합을 금지했다.
- `../knowledge_base/Codex/LLMEX/프로젝트 계획.md`의 attribution 손실·split 누출·checkpoint 복구 실패 즉시 중단 품질 gate를 구현 근거로 삼았다.

### 구현과 검증

- `llmex sft prepare-mix/preflight-mix/status-mix/validate-mix`를 추가했다. teacher export manifest의 예상 SHA-256과 source JSONL·tokenizer manifest를 고정하고 현재 입력에서 출력을 다시 유도해 변조와 stale 출력을 거부한다.
- heldout prompt와 provenance source를 train보다 우선해 격리하고 source+prompt 중복을 결정적으로 제거한다. prompt에 생성 reserve를 더한 길이와 전체 chat 길이가 tokenizer 한도를 넘으면 제외하며, SFT runtime도 canonical prompt·원천 overlap과 모든 학습 truncation을 실패-폐쇄로 거부한다.
- 배타 lock, 임시 staging, 파일·디렉터리 fsync와 원자 publish를 적용했다. 부분 출력이나 미완료 staging은 자동 덮어쓰지 않는다.
- 내부 전용 teacher 데이터가 포함되면 `redistribution_allowed=false`, `release_gate=blocked`를 mix manifest, SFT checkpoint와 heldout 평가에 계승한다. source manifest가 없던 기존 SFT checkpoint의 재개 호환성은 유지했다.
- 독립 리뷰에서 최초 HIGH 3건과 MEDIUM 지적, 추가 HIGH 지적을 수정한 뒤 최종 승인을 받았다. 전체 133 tests와 Ruff, Pyright를 통과했다.

### 진행 중인 정식 v5와 다음 순서

- 정식 v5 teacher 수집은 진행 중이므로 변하는 completed 수를 이력에 고정하지 않는다. `uv run llmex distill status --config configs/distill/qwen36mtp-10k.yaml`로 현재 상태를 확인한다.
- 수집 완료 뒤 export/validate를 통과시키고 생성된 teacher `manifest.json`의 SHA-256을 mix config의 `expected_teacher_manifest_sha256`에 고정한다. 그 다음 실제 경로와 base checkpoint를 사용하는 mix, pilot, full config를 각각 만들고 preflight-mix → prepare-mix → validate-mix → pilot → full 순서로 실행한다.
- step-0 loss의 별도 비교 평가는 아직 설계 대기이며 canonical exact prompt 검사로 잡지 못하는 semantic paraphrase leakage는 후속 contamination 검사와 수동 감사에서 판정한다.

## 2026-07-17 · 1.6.1 teacher pilot 교정과 정식 v5 준비

### 안전 중단과 세대별 보존

- 정식 v3 수집 초반 5건은 accepted 1건, rejected 4건이었고 rejected 사유는 모두 `finish_reason_not_stop`였다. 낮은 수용률을 확인한 즉시 수집을 안전 중단했으며 `runs/distill/qwen36mtp-10k-v3`의 inventory, state와 spool을 수정하지 않고 보존했다.
- v4와 v4b pilot은 기존 v3를 덮어쓰지 않고 별도 run에서 system prompt와 응답 copy 판정을 교정하는 데 사용했다. 정상적인 질문 요약은 허용하되 원문의 20%, 50%, 79% 연속 발췌와 한 단어만 바꾼 근접 복사는 차단하도록 회귀 계약을 고정했다.
- 응답은 1~5문장과 500자 이내로 요청하고 `max_response_chars=500`을 hard gate로 적용했다.

### 완료: 최종 v5 30건 실제 pilot

- `runs/distill/qwen36mtp-pilot-v5`에서 prepare, preflight, collect, export, validate를 실제로 모두 통과했다.
- 30건 중 accepted 28건(93.3%), rejected 2건이며 거부 사유는 `length` 1건과 `finish_reason_not_stop` 1건이다. failed, incomplete와 canonical response duplicate는 모두 0이다.
- accepted 응답 길이는 최소 67자, 평균 226.0자, 최대 357자였다. export는 train 25건, heldout 3건이며 prompt와 upstream source overlap은 0, redistribution은 불가하고 release gate는 blocked다.
- 누적 시간은 122.0626초, 실효 처리율은 0.245775 RPS, 상각 시간은 요청당 4.069초였다.

### 정식 v5 10k 상태와 다음 순서

- 정식 설정은 `runs/distill/qwen36mtp-10k-v5`다. train/heldout 8,445/1,555, inventory SHA-256 `b6a02b20b76f698a7b292b54faf5c46c65fce246ff2cd79a21be99274bc42ea1`, inventory fingerprint `46248ba32985f7102a4d401dfa019c43884011c7fb080014d6888e8e20593e7b`, config fingerprint `4a3eea14ca4a5bf43eea8c0302043a13da8ea848f4c757b6375637363417bb9d`로 준비했다.
- preflight는 통과했고 현재 10,000건 모두 pending이다. pilot 실효 RPS를 단순 적용한 예상 시간은 약 11.3시간이지만 teacher 부하, 응답 길이와 retry에 따라 변동될 수 있다.
- 저장소 외부 운영 참고 문서 `../knowledge_base/Codex/LLMEX/프로젝트 계획.md`의 확정 결정, 품질 gate와 100M baseline 이후 순서를 참고했다. 해당 계보에 따라 실패한 run을 덮어쓰지 않고 checkpoint·artifact 무결성을 우선하며, secret이나 로컬 절대경로는 문서에 기록하지 않는다.
- 이후 순서는 `정식 v5 실제 수집 → current spool export/validate → 공개 instruction+teacher 혼합 SFT → 대화/EOS/repetition/safety/manual gate`다.

## 2026-07-17 · 1.6.0 teacher 10k 증류 수집 파이프라인

### 완료: full latest baseline 평가

- 100k `latest` checkpoint를 `runs/baseline-100m/evaluation-full-latest`에서 validation/test 전체 shard로 평가했다.
- validation은 predicted token 4,223,967, loss 2.553663223356222, PPL 12.85410509996689이고 test는 predicted token 3,976,401, loss 2.5499812486981788, PPL 12.806863635046096이다.
- `evaluation-report.json` SHA-256은 `1f7cbf7624003e76711fc74b3f59fddcc14387f77a1c073b78d4ec55dbb795ff`다. canary provenance와 corpus 경로가 없는 canary exposure·contamination·long train match는 계속 미실행이며 full PPL이 해당 gate를 대신하지 않는다.

### 완료: schema 2 teacher 수집 구현과 v3 준비

- `llmex distill preflight/prepare/collect/resume/status/export/validate`와 `configs/distill/qwen36mtp-10k.yaml`을 추가했다. 로컬 `http://localhost:8081/v1`의 `qwen36mtp`를 확인하고 모든 completion 요청에 thinking 비활성화를 명시한다.
- 안전 run은 `runs/distill/qwen36mtp-10k-v3`다. source chat raw 6,853건에서 고유 prompt 5,813건을 남기고 중복 1,040건을 제거했으며 upstream heldout 630건을 보존했다. Wikipedia 4,187건을 보충해 총 10,000건, train/heldout 8,445/1,555, prompt와 upstream source overlap 0으로 준비했다.
- inventory SHA-256은 `b6a02b20b76f698a7b292b54faf5c46c65fce246ff2cd79a21be99274bc42ea1`, fingerprint는 `46248ba32985f7102a4d401dfa019c43884011c7fb080014d6888e8e20593e7b`다.
- 실제 preflight는 통과했고 현재 status는 pending 10,000, completed 0, progress 0, ETA 미산출이다. 따라서 pipeline과 inventory 준비 완료를 teacher 응답 수집 완료로 해석하지 않는다.
- 요청별 schema 2 spool을 원자 저장하고 bounded concurrency·RPS·timeout·응답 크기·retry 횟수와 지연 상한을 강제한다. 진행률·누적 시간·실효 RPS·ETA를 기록하며 중단 뒤 검증된 spool만 건너뛰어 재개한다.
- stale lock은 같은 host의 종료 PID와 동일 inode/내용을 재검증한 경우에만 회수한다. current config/inventory/request body와 spool hash가 다르면 실패-폐쇄한다.
- export는 current inventory와 accepted spool 집합에 강결속하고 provenance와 request/response/raw-response hash를 보존한다. teacher 출력은 `LicenseRef-LLMEX-Internal-Distillation`, 재배포 불가, release blocked다.
- loopback HTTP `/v1`만 허용하고 redirect와 환경 proxy를 차단한다. 비밀정보는 환경변수에서만 읽으며 응답 echo를 탐지하면 본문과 hash를 기록하지 않는다. body·retry 상한과 strict completion schema를 적용한다.
- 반복·prompt 복사·위험 패턴 검사는 휴리스틱 사전 필터이며 최종 safety gate가 아니다.

### 독립 검토와 검증

- 독립 리뷰의 최초 9개 지적과 추가 5개 지적을 수정한 뒤 최종 `APPROVE`를 받았다.
- 전체 `uv run pytest -q` 123개 테스트, Ruff lint/format, Pyright 오류·경고 0건과 `git diff --check`를 통과했다.

### 다음 순서

1. v3 run에서 실제 teacher 10,000건을 `collect`하고 중단 시 `resume`한다.
2. 완료된 current spool에서 `export`와 `validate`를 통과시킨다.
3. 허가된 공개 instruction과 teacher 데이터를 혼합해 100k latest 기반 SFT를 수행한다.

## 2026-07-17 · 1.5.3 SFT 재개 무결성 강화와 100k 시작 checkpoint 선택

### 완료: SFT 학습과 검증 계약 강화

- SFT 정밀도 설정에 `auto`, `bf16`, `fp16`, `fp32`를 지원한다. `auto`는 CUDA bf16 지원 시 bf16, 그 밖의 CUDA에서는 fp16, CPU·MPS에서는 fp32를 선택한다. bf16은 CUDA 또는 CPU, fp16은 CUDA에서만 허용하며 fp16은 gradient scaler를 사용한다.
- `gradient_accumulation_steps`로 여러 micro-batch의 assistant target token 수를 가중해 한 optimizer step으로 누적한다. checkpoint는 accumulation 도중이 아닌 optimizer 경계에서만 저장한다.
- `validation_interval`마다 `validation_batches`개의 heldout batch를 평가하고 assistant-only validation loss와 perplexity를 기록한다. `latest.pt`는 최신 저장 상태를, `best.pt`는 validation loss가 개선된 상태를 보존한다.
- 각 validation은 같은 seed의 동일한 고정 heldout subset과 순서를 다시 사용한다. 따라서 서로 다른 표본의 loss를 직접 비교하지 않고 같은 검증 기준에서만 `best.pt`를 갱신한다.
- schema 2 SFT checkpoint에 모델, optimizer, scheduler, scaler, train·validation sampler, Python·NumPy·PyTorch CPU/CUDA RNG, step, micro-step, 실제 precision, best validation loss와 누적 validation batch 수를 저장해 완전 재개한다.
- 재개 시 validation sampler cursor, optimizer 구조·parameter group·step tensor, RNG 구조, scheduler step, accumulation 경계와 model/optimizer tensor의 NaN/Inf 부재를 실패-폐쇄로 검사한다. `max_steps`만 늘린 재개는 허용하지만 다른 fingerprint 불일치는 거부한다.
- `max_steps` 연장 재개 시 checkpoint의 원래 scheduler horizon을 보존하고, 그 horizon 이후 추가 step은 `min_learning_rate`를 유지해 과거 학습 궤적을 재해석하지 않는다.
- SFT의 `base_checkpoint`는 schema 1과 schema 2의 모델 가중치를 모두 지원한다. immutable bytes SHA-256, schema/kind/step과 원 학습 fingerprint를 SFT fingerprint 및 data manifest에 결속하며, 같은 경로의 다른 가중치 교체·비유한 모델 상태·형상 불일치를 거부한다.
- `sft eval`과 `sft generate`도 모델 tensor만 읽지 않고 optimizer/scaler/scheduler/train·validation sampler/RNG/precision을 포함한 schema 2 전체 상태를 strict 검증한 뒤 로드한다.

### 완료: 100k checkpoint 동일 조건 평가와 선택

동일한 validation/test split별 128 batch와 같은 생성 평가 조건에서 비교했다.

| 100k checkpoint | validation PPL | test PPL | 평균 repetition | EOS 도달 |
|---|---:|---:|---:|---:|
| best | 13.288556 | 14.080648 | 0.549716 | 2/6 |
| latest | 13.178043 | 13.952660 | 0.529836 | 3/6 |

- validation PPL, test PPL, 평균 repetition, EOS 도달의 모든 측정 축에서 우세한 100k `latest`를 SFT 시작점으로 선택했다.
- 이 선택은 두 checkpoint 사이의 상대 비교 결과이며 대화 품질 gate 통과를 뜻하지 않는다. 한국어 대화 품질, EOS, repetition, safety와 수동 평가는 SFT 이후 별도 gate로 판정한다.

### 개발 근거와 다음 순서

- `../knowledge_base/Codex/LLMEX/프로젝트 계획.md`의 개발 문서 순서인 `docs/README.md → docs/prd.md → docs/plan.md → docs/todo.md`를 참조했다.
- 같은 계획의 실패 중단 기준을 따라 checkpoint 복구 실패가 있으면 즉시 중단하며, 손상 상태를 우회하거나 부분 재개하지 않는다.
- 이후 순서는 `teacher 10k pilot → 공개 instruction+teacher 혼합 SFT → 대화/EOS/repetition/safety/manual gate → GGUF/llama.cpp parity`다.

### 검증

- 구현 1차 검증에서 93개 테스트가 통과했고, 독립 리뷰 보강 회귀 4개를 추가한 최종 `uv run pytest -q`에서 97개 테스트가 통과했다. 악성 pickle 차단 회귀의 의도된 PyTorch `weights_only` 경고 1건만 발생했다.
- `uv run ruff check .`: 통과
- `uv run ruff format --check .`: 56개 파일 형식 통과
- `uv run pyright`: 오류·경고 0건으로 통과

## 2026-07-17 · 1.5.2 100k baseline 학습 완료와 checkpoint audit

### 완료: 100k 학습과 checkpoint 감사

- GB10 CUDA bf16 baseline이 100,000 step과 6,547,200,000 token을 완료했다. 모델의 tied embedding을 한 번만 세는 고유 파라미터 수는 87,804,672다.
- 새 `uv run llmex train audit --config configs/training/baseline-100m.yaml` 명령으로 `step-00100000.pt`, `latest.pt`, `best.pt`를 수정 없이 감사했다. 완료 step과 latest는 100,000이고 validation loss가 가장 낮은 best step은 82,000이다.
- `step-00100000.pt`와 `latest.pt`의 SHA-256은 모두 `dae1b01b35d4ff0dc32dab464e9d3d286fb885b96fd0a880faf2e2e5e8e53b33`, `best.pt`의 SHA-256은 `56ebbd48905a6eae27348318a6f385de61fe7b36b1e1704fc8dcae6bb95feb3a`다.
- 세 checkpoint 모두 schema version 1, 현재 config/corpus/model/shards/tokenizer의 strict fingerprint 일치, optimizer/scheduler/scaler/train·validation sampler/RNG/step 필수 상태 존재, scheduler step 일치와 모델 tensor의 NaN/Inf 부재를 통과했다. state dict 원소 합계 100,092,672는 tied embedding이 두 키에 나타난 값이며 고유 파라미터 수와 구분한다.

### 완료: 제한된 baseline 평가와 생성

- `configs/evaluation/baseline-100m.yaml`에서 best checkpoint를 대상으로 CUDA batch size 1, split별 1 batch만 평가했다. validation perplexity는 `17.4997868841064`(요약 `17.4997869`), test perplexity는 `3.2870502053811377`(요약 `3.2870502`)이다. 이 값은 전체 validation/test 집합 평가가 아닌 1-batch 확인 결과다.
- cloze 2문항 정확도는 `0.5`다. 고정 prompt 생성은 repetition `0.21875`, UTF-8/Unicode 유효성 통과, 32 token 제한 안에서 EOS 미도달이었다. 따라서 기본 추론 경로는 확인했지만 대화 품질이나 EOS gate 통과를 뜻하지 않는다.
- canary exposure는 canary provenance 파일 미설정, contamination과 long train match는 corpus 경로 미설정으로 미실행이다. 이 세 항목은 이번 제한 평가의 최종 gate가 아니며, 설정을 보완한 전체 validation/test·오염·암기·생성·수동 평가가 후속으로 남아 있다.

### 다음 순서

1. SFT engine의 데이터·재개·평가 계약을 강화한다.
2. teacher 10k pilot을 수행하고 provenance, hash, train/heldout 비중복과 품질을 검증한다.
3. 공개 instruction과 승인된 teacher 데이터를 혼합해 SFT한다.
4. 한국어 대화, EOS, repetition, safety와 수동 품질 gate를 통과시킨다.
5. GGUF 변환 뒤 llama.cpp와 PyTorch 출력 parity를 검증한다.

## 2026-07-17 · 1.5.1 전체 Wikipedia baseline 및 대화 실험 기록

### 완료: 데이터와 tokenizer

- Wikipedia dump `20260701`, SHA-256 `991b26eb4588d2eddafd472a3b7dd2a8503740fb3e6c46d14baeef60d83e5582`를 사용했다.
- extraction 753,081건, clean 747,718건, dedup 747,532건(exact duplicates 186건), split train/validation/test 732,393/7,521/7,618건이다.
- corpus는 `data/processed/corpus-v1.jsonl.zst`, 711,548,455 bytes, SHA-256 `d959eb11051b405a509839e6a3f75e1c66b6f7e2aa88fbac3ff63580e0dea165`이다.
- tokenizer는 `artifacts/tokenizers/bpe-16k`이며 chars/token 1.990337, bytes/token 4.400516, tokens/word 2.346399, byte reduction 77.275394%, UNK 0, Unicode 표본 10,000이다.

### 진행 중: baseline 기록 시점 snapshot

- 기록 시각은 `2026-07-17T02:57:01+09:00`이다. 87,804,672 parameters, 100,000 steps, 6,553,600,000 tokens 목표로 GB10 CUDA bf16 학습 중이다.
- 프로세스는 PID `1082225` (`uv run llmex train run --config configs/training/baseline-100m.yaml`)와 PID `1082250` (`llmex train run`)이다.
- 경로는 config `configs/training/baseline-100m.yaml`, metrics `runs/baseline-100m/metrics.jsonl`, checkpoints `runs/baseline-100m/checkpoints`이다. 최신 checkpoint 파일명은 `step-00089500.pt`이다.
- metrics 마지막 행은 step 89,900, loss 2.3045945167541504, gradient norm 0.6804365515708923, learning rate 0.000037014643665840424, tokens 5,885,932,800, tokens/s 13,141.819194612375, peak memory 4,496,564,736 bytes였다.
- 관련 휘발성 실행 경로는 `/tmp/llmex-pretrain/run-full-corpus.sh`, `/tmp/llmex-pretrain/full-corpus.log`, `/tmp/llmex-pretrain/train.log`이다. 100k 완료, final eval, conversation 검증은 아직 완료되지 않았다.

### 완료: 과거 CarrotAI SFT와 qwen36mtp 증류 실험

- CarrotAI revision `5c0e2c0180b50400e401dd0b296043f18fc6cb3f`를 사용했으며 raw 7,040, dedup 6,853, split 6,204/649였다.
- 50-step loss 9.377446, NLL 9.332419, PPL 11,298.43; 500-step loss 7.411470, NLL 7.338655, PPL 1,538.64; 1,000-step NLL 6.476955, PPL 649.99; 2,000-step NLL 6.120403, PPL 455.05였다.
- qwen36mtp teacher 100건을 모두 accepted했고 train 90건/heldout 10건으로 분리했으며 mean repetition 0.121885, 총 30,547 tokens였다. distill 100-step은 loss 6.299877, NLL 6.475069, PPL 648.76였다.
- 실행 성공과 safety만 통과했다. repetition 0.96875, EOS 실패, newline 붕괴가 남아 대화 가능 모델이 아니다.
- 과거 SFT artifact인 `/tmp/llmex-public-sft/result.json`, `/tmp/llmex-public-sft-long/result.json`, `/tmp/llmex-public-sft-2000/result.json`, `/tmp/llmex-distill/result.json`은 실제 실험 근거지만 휘발성 result 경로이므로 정식 artifact로 승격하기 전에는 `/tmp` 수명 경계를 갖는다.

### 100k 후 계획

1. final/latest/best checkpoint의 존재 여부, SHA-256, fingerprint, optimizer/scheduler/RNG 상태, NaN/Inf 여부를 확인한다.
2. validation/test NLL/PPL, cloze, contamination, fixed prompts, repetition/EOS/Unicode, throughput/memory를 평가한다.
3. CarrotAI 공개 instruction으로 SFT를 다시 수행하고 validation 결과로 checkpoint를 선택한다.
4. teacher 데이터를 수천~수만 건으로 확대하면서 provenance와 request/response hash를 기록하고 train/heldout 비중복을 검증한다.
5. 공개 instruction 데이터와 teacher 데이터를 혼합해 학습한다.
6. 한국어 문법, 문장 종결, 암기 복사, 수동 평가를 포함해 conversation/EOS/repetition/safety gate를 모두 통과시킨다.
7. 필요하면 DPO를 수행한다.
8. checkpoint/tokenizer/config/model card/license provenance를 패키징하고 chat history/streaming/sampling/API를 검증한다.

## 2026-07-11 · G003 한국어 대화 학습 경로 (1.5.0)

- 승인 license allowlist, dataset/source/date provenance, canonical 행 SHA-256와 파일 SHA-256를 검증하고 train/heldout 중복을 거부한다.
- system/user/역할 prefix/padding을 `-100`으로 마스킹해 assistant 본문과 EOS만 학습한다.
- 기존 checkpoint 가중치 재사용과 SFT model/optimizer/scheduler/RNG/data cursor의 fsync·atomic checkpoint 재개를 구현했다.
- `sft train/resume/eval/generate`, heldout assistant NLL/perplexity와 safety/repetition/EOS gate를 합성 CPU 실제 학습·추론으로 검증했다.
- 전체 Wikipedia baseline, 외부 장기 학습, 독립 안전·법무·공개 승인은 완료로 간주하지 않는다.

## 2026-07-11 · 1.4.0 external telemetry freshness와 최종 권위 재검증

- external command 실행 직전에 예측 불가능한 nonce를 만들고 `LLMEX_STAGE_NONCE`를 포함한 환경 계약으로 run-id, stage, 예산, Git commit, 설정 fingerprint 및 출력 경로를 전달한다.
- command가 실행 중 실제 사후 telemetry를 발급하도록 정상 회귀를 바꾸고, 서명 subject의 모든 실행 식별자와 `issued_at >= stage_started_at`, 현재 만료 유효성을 검증한다.
- 서로 다른 유효 서명을 가진 과거 telemetry 재생과 후속 local stage의 권위 파일 TOCTOU 변조를 회귀 테스트로 차단했다.
- 최종 성공 직전 마지막 권위 telemetry의 digest, 서명, subject, 예산과 사용량 상한을 전부 다시 검증하며 실패 상태를 원자적으로 기록한다.

## 2026-07-11 · 1.3.0 사후 권위 gate와 공개키 신뢰 체인

- external stage의 사전 final telemetry는 승인 근거로 사용하지 않으며, 실행 직전 digest와 다른 사후 final telemetry가 없으면 단계와 전체 상태를 실패로 고정한다.
- 사후 telemetry를 issuer 서명, repository commit, config fingerprint, stage, deterministic run-id, token/energy 예산과 실제 최종 사용량에 결속했다.
- verifier의 HMAC secret 환경변수 입력을 제거하고 패키지 pinned root Ed25519 공개키가 서명한 HEAD policy와 issuer Ed25519 서명을 순서대로 검증한다.
- cloze/canary 후보를 prefix와 따로 tokenize하지 않고 결합 sequence offset으로 score span을 정해 경계 merge를 보존했다.


## 2026-07-11 · 1.2.0 외부 신뢰 경계 차단 해제

- 승인 파일 위치가 아니라 명시 subject repository root와 canonical HEAD commit에 release/pipeline 진술을 결속했다.
- HEAD에 봉인되고 group/other 쓰기가 금지된 `.llmex/trust-policy.json`의 key digest·role·kind만 권위 있는 보호 CI policy로 인정한다. 일반 프로세스 환경변수만으로 만든 self-signed 결과는 승인하지 않는다.
- 외부 evidence와 최종 resource telemetry의 서명, RFC3339 유효 기간, role/kind, commit/config/artifact 결속을 검증하고 누락·변조 시 대기한다.
- JSONL.ZST와 pipeline Markdown까지 file/directory fsync와 atomic replace 계약으로 통일했다.

## 2026-07-11 · 1.1.1 AI slop 정리

- `acf2841..45bd4ff`의 변경 코드·테스트만 대상으로 52개 targeted regression을 먼저 통과시켰다.
- fallback inventory를 작성하고 OS 자원 탐지, pipeline 재개·복구, checkpoint 로드 경계가 실패-안전형임을 확인했다.
- 미사용 artifact sidecar 검증 함수를 삭제하고 평가 Markdown의 원자적 쓰기를 공통 구현으로 통합했다.
- 압축된 preflight 지역 변수 대입을 명시적으로 풀고 버전·lock·릴리스 이력을 `1.1.1`로 동기화했다.

## 2026-07-11 · M0 저장소 기반

- Python 3.11+ `src` layout과 패키지 버전 `0.1.0`을 구성했다.
- Typer root CLI와 config 검증, fingerprint, run 생성 명령을 추가했다.
- Pydantic strict 모델로 알 수 없는 키, 암묵적 타입 변환, 잘못된 dump URL과 모델 형상을 거부한다.
- path/run/fingerprint, JSON 구조화 로그, 안정적인 종료 코드를 추가했다.
- 한국어 MediaWiki XML 오프라인 bzip2 fixture와 단위 테스트를 추가했다.
- Ruff, Pyright strict, Pytest, GitHub Actions 품질 게이트를 구성했다.
- Dockerfile, Compose bind mount, 오프라인 서비스와 CUDA bf16 smoke script를 추가했다.
- `0.ref`는 수정하지 않았고 production import 금지를 테스트로 고정했다.
- 실제 DGX Spark의 `aarch64` Ubuntu(kernel `6.17.0-1014-nvidia`), NVIDIA GB10, driver `580.142`, CUDA compatibility `13.0`, Docker `29.2.1`을 확인했다.
- NVMe `/`는 전체 `3.6T` 중 `1.9T` 사용 가능, RAM은 전체 `119Gi` 중 `28Gi` 사용 가능, swap은 전체 `15Gi` 중 `11Gi` 사용 상태로 기록했다.
- `nvidia-smi`의 framebuffer memory가 `Not Supported`임을 확인하고, NVIDIA Container Runtime의 실제 GPU 전달로 판정을 보완했다.
- `nvcr.io/nvidia/pytorch:25.10-py3` 로컬 이미지 digest를 `sha256:42263b2424fc237b34c4fc4a91c30d603c57eed36e37d31ff6d9a4f1f801edee`로 확인해 Dockerfile, `.env`, Compose 기본값에 고정했다.
- `docker run --rm --gpus all ... python scripts/cuda_smoke.py`에서 PyTorch `2.9.0a0+145a3a7`, CUDA `13.0`, NVIDIA GB10을 확인했고 bf16 결과가 `finite=true`로 통과했다.

### M0 마감 검증 기록

- `uv sync --frozen`: lockfile 변경 없이 동기화 통과
- `uv run ruff check .`: 통과
- `uv run ruff format --check .`: 통과
- `uv run pyright`: 통과
- `uv run pytest -q`: `14 passed`
- `uv run llmex --help`: 도움말 출력 통과
- `cd 0.ref && shasum -a 256 -c SHA256SUMS`: 참조 파일 checksum 통과
- `docker compose config`: digest 고정값과 Compose 구성 해석 통과
- `git diff --check`: whitespace 오류 없음

## 2026-07-11 · M1 Wikipedia 데이터 파이프라인

- 패키지와 프로젝트 버전을 `0.2.0`으로 올렸다.
- 날짜 고정 Wikimedia URL/status/SHA256SUMS metadata, 저장공간 검사, timeout/retry, HTTP Range resume, checksum 검증과 읽기 전용 raw manifest를 구현했다.
- bzip2 XML streaming 추출에서 namespace 0, redirect 제외, 마지막 revision과 page/revision/source/dump/license attribution을 보존했다.
- parser ADR에 후보 비교와 한계를 기록하고 표·참조 제거, 수식·목록 표시문 보존, NFC/control/공백 정제 및 정책 통계를 구현했다.
- 최소 길이·한글 비율·반복·markup 품질 필터, exact SHA-256과 선택적 결정적 MinHash near-dedup, document-hash split을 구현했다.
- schema v1 JSONL.ZST reader/writer, 단계별 CLI, data manifest/report, 최대 100건 자동 감사 JSON/Markdown을 구현했다.
- 외부 네트워크 없는 확장 fixture와 golden test, 손상 checksum, local HTTP resume, attribution, split disjoint, 결정적 E2E hash 검증을 추가했다.
- 실제 전체 dump와 실제 입력 1,000문서 canary는 실행하지 않았다. `--max-documents 1000` 실행 기능과 fixture 기반 smoke 통과만 검증했으며 실제 canary 완료로 기록하지 않는다.

## 2026-07-11 · M2 토크나이저와 token shards

- 패키지 버전을 `0.3.0`으로 올리고 Hugging Face `tokenizers`, NumPy를 runtime dependency로 추가했다.
- train split 전용 streaming iterator와 special ID 0–3, initial byte alphabet, byte fallback을 갖춘 결정적 byte-level BPE 학습을 구현했다.
- 16k/32k 설정, tokenizer JSON, vocab, merges, resolved config, corpus fingerprint와 artifact checksum manifest를 추가했다.
- 문자/토큰, 바이트/토큰, 단어당 토큰, raw byte baseline 비교와 split별 통계를 JSON/Markdown으로 출력한다.
- source 문서별 EOS와 전역 경계를 보존하고 실제 최대 ID에 따라 little-endian `uint16`/`uint32`를 선택하는 원자적 memmap shard writer를 구현했다.
- shard별 checksum, token 수, 최소/최대 ID 및 tokenizer/corpus fingerprint manifest와 fingerprint 충돌 보호를 추가했다.
- 한글 완성형·자모·NFD·emoji ZWJ·한자·ASCII·combining marks, Hypothesis 유효 Unicode와 고정 10,000표본, train-only fitting, 누출, EOS, next-token 정렬, 결정적 checksum 테스트를 추가했다.
- 외부 네트워크 없이 M1 형식 fixture corpus로 `tokenizer train/evaluate/pack` CLI E2E를 검증한다.

## 2026-07-11 · M3 decoder-only Transformer

- 패키지 버전을 `0.4.0`으로 올리고 PyTorch 2.x를 runtime dependency로 추가해 lockfile을 동기화했다.
- float32 내부 계산 RMSNorm, 인접 좌표 회전 RoPE와 position offset, GQA/MHA projection과 명시적 절대 위치 causal mask를 구현했다.
- PyTorch SDPA 기본 경로와 독립 eager reference 경로가 같은 projection·mask에서 수치 일치하도록 구성했다.
- bias 없는 SwiGLU, Pre-Norm residual decoder block, 최종 RMSNorm과 tied token embedding/LM head를 구현했다.
- 평균 0·표준편차 `init_std` 초기화와 residual output projection의 `1/sqrt(2L)` scale을 적용했다.
- `int64[B,T]` 입력, `float[B,T,V]` logits, shifted cross entropy, padding ignore index와 shape/길이 오류 계약을 구현했다.
- greedy/temperature/top-k generation과 layer별 RoPE 적용 KV cache를 라이브러리 API로 추가하고 cached/uncached parity를 고정했다.
- `llmex model inspect`가 resolved config, fingerprint, 정확한 파라미터 수, fp32 weight와 AdamW 근사 메모리, weight tying을 JSON artifact로 기록한다.
- RMSNorm/RoPE 수식, GQA Hypothesis property, SDPA/eager parity, causal leakage 0, loss shift, finite gradient, state dict, 생성 cache, 128문서 synthetic overfit과 CLI E2E 테스트를 추가했다.
- 교재 Ch 14–18, 27, 31과 benchmark는 읽기 전용 수식 참고로만 사용했으며 production import 없이 독립 구현했다.

### M3 마감 검증 기록

- `uv sync --frozen`: `0.4.0` lockfile 변경 없이 동기화 통과
- `uv run ruff format --check .`, `uv run ruff check .`: 통과
- `uv run pyright`: strict 기준 오류·경고 0건
- `uv run pytest -q`: `36 passed`
- `uv run llmex model inspect --config configs/model/smoke.yaml`: `2,835,584` parameters, tied weight와 JSON artifact 출력 통과
- NVIDIA GB10 CUDA forward/backward smoke: finite loss와 역전파 통과
- `cd 0.ref && shasum -a 256 -c SHA256SUMS`: 전체 참조 무결성 통과
- `git diff --check`: whitespace 오류 없음

## 2026-07-11 · M4 결정적 학습 엔진

- 패키지 버전을 `0.5.0`으로 올리고 strict `TrainingConfig`와 AdamW 설정을 추가했다.
- checksum 검증 memmap shard dataset, shard 경계 연속 context, epoch/cursor 복구형 결정적 sampler와 next-token batch를 구현했다.
- tied parameter 중복을 제거한 decay/no-decay AdamW group, update 단위 warmup+cosine, gradient accumulation과 global norm clipping을 구현했다.
- CUDA bf16 우선 자동 선택, CUDA fp16 GradScaler, bf16 scaler 비활성, CPU/MPS fp32 fallback 정책을 구현했다.
- train/validation/생성 표본 JSONL과 처리량·CUDA peak memory 지표, validation NLL/perplexity와 best 판정을 구현했다.
- 보존형 step, latest, best checkpoint를 flush·file/directory `fsync`·atomic rename으로 저장한다.
- model/optimizer/scheduler/scaler, train/validation sampler, Python·NumPy·PyTorch CPU/CUDA RNG와 best 상태를 완전 복구한다.
- config/corpus/tokenizer/model/shard fingerprint 충돌, shard/checkpoint 손상과 NaN/Inf를 즉시 거부하고 진단 artifact를 남긴다.
- SIGTERM은 현재 update 경계에서 graceful checkpoint 후 종료하며 `train run/resume/smoke` CLI를 제공한다.
- CPU 50-step loss 감소, accumulation 동등성, bitwise 중단·재개와 오류주입 테스트를 추가했다.

### M4 마감 검증 기록

- `uv sync --frozen`: 0.5.0 lockfile 변경 없이 동기화 통과
- `uv run ruff format --check .`, `uv run ruff check .`: 통과
- `uv run pyright`: strict 기준 오류·경고 0건
- `uv run pytest -q`: `42 passed`
- CLI E2E: 0.5.0/version, help, training config validate, `train smoke --dry-run`, 테스트 내부 실제 train/resume/smoke 통과
- CPU: 50 optimizer step loss 감소, 연속/중단·재개 state bitwise 동일, NaN·손상·fingerprint 오류주입 통과
- NVIDIA GB10 CUDA: bf16 autocast 실제 2-step train/validation, JSONL CUDA peak memory, latest/best checkpoint 통과
- `git diff --check`: whitespace 오류 없음

## 2026-07-11 · M5 평가와 추론

- 패키지와 프로젝트 버전을 `0.6.0`으로 올리고 lockfile을 동기화했다.
- checkpoint, 학습 설정, 모델, tokenizer, corpus와 shard fingerprint 및 tokenizer artifact checksum/special ID/vocab 형상을 묶은 엄격한 추론 runtime을 구현했다.
- validation/test의 합산 NLL, token loss/perplexity, UTF-8 byte 정규화 NLL·bits/byte·byte perplexity를 구현했다.
- provenance를 가진 고정 Korean Wikipedia 형식 cloze schema와 띄어쓰기·조사/어미·고유명사·숫자/날짜 고정 prompt suite를 추가했다.
- greedy, temperature, top-k, top-p, seed, sign-aware repetition penalty와 배치별 EOS, max-new-token, 모델 문맥 제한 처리를 구현했다.
- KV cache prefill/decode offset 계약을 유지하고 cache/no-cache 다음-token logits 수치 동등성과 greedy 생성 완전 동등성을 자동 검증했다.
- 생성 반복률, distinct-1/2, UTF-8 유효성, EOS/문맥 종료, exact substring 및 문자 5-gram near contamination, canary/긴 생성 train match 결과를 보고한다.
- JSON/Markdown 평가·생성·benchmark artifact와 SHA-256 checksum manifest, payload fingerprint를 원자적으로 생성한다.
- 한국어 도움말, 구조화 오류 코드와 side-effect 없는 dry-run을 갖춘 root `eval`, `generate`, `benchmark` CLI를 추가했다.
- CPU CLI E2E에서 실제 checkpoint를 생성해 세 명령과 artifact를 검증했다. CUDA가 보이는 환경에서는 synchronize 기반 latency/token-s 및 peak allocated memory를 기록한다.

### M5 마감 검증 기록

- `uv sync --frozen`: lockfile 변경 없이 동기화 통과
- `uv run ruff format --check .`; `uv run ruff check .`: 통과
- `uv run pyright`: strict 오류 0건
- `uv run pytest -q`: 전체 테스트 통과
- `uv run llmex eval|generate|benchmark --dry-run`: side effect 없이 통과
- CPU checkpoint CLI E2E와 cache/no-cache logits·생성 동등성: 통과
- CUDA smoke/latency-memory: 실행 환경의 CUDA 가용성에 따라 결과 기록
- `git diff --check`: whitespace 오류 없음

### M5 GB10 CUDA smoke/benchmark 실측

- PyTorch `2.13.0+cu130`이 NVIDIA GB10을 인식했다.
- 2-layer, `d_model=64`, context 64 임시 모델에서 KV cache greedy 16-token 생성을 수행했다.
- latency `0.377293초`, 처리량 `42.407 token/s`, PyTorch peak allocation `34,166,272 byte`였다.
- cache decode logits는 모두 유한값이었다. 이 수치는 기능 smoke이며 baseline 모델 성능 수치가 아니다.
## 2026-07-11 · M6 전체 pipeline 계약과 외부 baseline gate (0.7.0)

- `PipelineConfig`에 저장공간·available memory·시간·에너지·파라미터·token 예산, 단계 명령, 출력, timeout과 필수 증거를 엄격히 모델링했다.
- `llmex pipeline preflight/run/status/drill/export`를 추가했다. 명령은 shell을 거치지 않고 실행되며 단계별 stdout/stderr tail, 종료 코드, 경과 시간, 출력 존재, config/evidence SHA-256과 재개 상태를 보존한다.
- 외부 단계는 필수 증거가 모두 존재하고 `--allow-external`을 명시하지 않으면 실행하지 않는다. 전체 dump나 장기 학습이 없을 때 완료로 보이는 fall-through를 차단했다.
- baseline을 정확히 87,804,672 parameters, 16k vocab, context 1024로 고정하고 120M 상한, 최대 6.5536B token, 168시간, 35kWh 예산을 설정했다.
- aarch64 DGX Spark에서 preflight와 model inspect를 실제 실행했다. available memory 약 27.6GiB, NVMe free 약 1.90TiB로 통과했고 모델/AdamW 정적 추정은 약 335MiB/1.31GiB였다.
- Wikimedia 20260701 dump 1,398,909,939 bytes를 실제 다운로드했다. 공식 SHA-1 `291b50…e1f98`과 일치했고 로컬 SHA-256 `991b26…5582`를 계산했다. 실제 선두 1,000문서 canary에서 997문서가 통과하고 exact 중복은 0건이었다.
- 같은 실제 canary로 16k/32k tokenizer를 모두 학습·평가했다. 32k가 token 수를 8.46% 줄였지만 artifact/embedding 비용 때문에 전체 corpus 처리량 승인 전 16k를 조건부 선택했다.
- GB10에서 87.8M 모델을 context 256, micro batch 1로 실제 100 step 학습해 41.12초, 마지막 2,479.94 token/s, PyTorch peak 1.67GiB를 기록했고 고정 NGC container bf16 smoke도 재통과했다.
- fixture pipeline test가 외부 대기→증거 공급→재개 완료, 출력 검증, 상태 fingerprint 복구 drill, dashboard export와 CLI status를 검증한다.
- `docs/baseline-report.md`, `docs/baseline-runbook.md`, ADR-015/016과 M6 검증표를 추가하고 모든 사용자 노출 설명을 한국어로 작성했다.

## 2026-07-11 · M7 공개 준비와 도구 안정 릴리스 (1.0.0)

- 프로젝트와 패키지 버전을 1.0.0으로 올리고 frozen lock을 갱신했다.
- data/model/tokenizer card, NOTICE, 보안·개인정보 정책, threat model, 운영 runbook, API/CLI, failure mode, migration, changelog, reproducibility와 acceptance matrix를 한국어로 추가했다.
- `llmex release audit`이 비밀 의심 문자열, 배포 금지 절대 경로, 필수 릴리스 문서와 production의 `0.ref` import 경계를 검사하도록 구현했다.
- `llmex release bundle`이 모든 배포 후보 파일의 SHA-256/byte manifest, CycloneDX 1.5 SBOM, in-toto statement와 SLSA provenance 형식 진술, 재현 명령을 생성하도록 구현했다.
- `llmex release gate`는 법무 검토·장기 baseline·공개 배포 결정 각각의 `approved=true`, 승인자, 시각, 근거가 없으면 종료 코드 5로 실패한다. 이 gate는 외부 결정을 자동으로 만들거나 자기 승인하지 않는다.
- MIT 소프트웨어 라이선스와 Wikipedia/참조/가중치 조건의 비법률적 경계를 분리했다. 원 데이터와 가중치는 패키지에 포함하지 않는다.
- sdist/wheel build, 새 가상환경 wheel 설치와 version/help smoke, wheel `0.ref` 제외, CLI/pipeline E2E, release generator/gate 회귀 테스트를 CI에 추가했다.
- ADR-017에서 1.0 도구 릴리스와 모델·데이터 공개 승인을 분리했다. 로컬 acceptance가 통과해도 외부 세 gate는 승인 증거 전까지 공개 금지 상태다.

### M7 마감 검증 기록

- `uv sync --frozen`: 1.0.0 lock 변경 없이 통과했다.
- `uv run ruff format --check .`; `uv run ruff check .`: 49개 Python 파일 format, lint 통과했다.
- `uv run pyright`: strict 오류·경고 0건이었다.
- `uv run pytest -q`: 전체 `49 passed`; M6/M7 CLI·pipeline 표적 E2E `5 passed`였다.
- `uv build`: `llmex-1.0.0.tar.gz`와 `llmex-1.0.0-py3-none-any.whl` 생성에 성공했다.
- 새 Python 3.11 venv에 wheel과 55개 의존성을 설치하고 1.0.0 version 및 모든 명령군 help smoke를 통과했다.
- sdist의 NOTICE·ATTRIBUTION·model card·examples 포함, sdist/wheel의 `0.ref` 제외와 wheel LICENSE 포함을 검사했다.
- `llmex release audit`은 비밀·로컬 경로·필수 문서·참조 경계를 통과했다. bundle은 120개 파일, 65개 설치 구성요소의 checksum/SBOM/provenance를 생성했다.
- 빈 외부 승인 파일은 의도대로 종료 코드 5로 실패했다. 참조 SHA-256과 `git diff --check`도 통과했다.
- 외부 미실행 항목: 전체 corpus 장기 baseline, 독립 법무·데이터·안전 검토, 공개 채널 배포.

## 2026-07-11 · M0–M7 최종 AI slop 정리 (1.0.1)

- 범위를 `d2cebc0^..c55078a`의 변경 파일로 고정하고 수정 전 전체 `49 passed`로 동작을 잠갔다.
- fallback-like inventory에서 downloader 재시도 루프 뒤의 도달 불가능한 대체 오류 분기를 masking fallback slop으로 분류해 삭제했다. 재시도 소진 시 원인 문자열을 보존한 `InputError`가 발생하는 회귀 테스트를 추가했다.
- `/proc/meminfo` 읽기 실패 시 자원 검사를 실패시키는 경로, 원자 저장의 임시 파일 정리, Git 정보 비가용 표시, tokenizer byte fallback은 실패-폐쇄 또는 외부 호환성 경계로 분류해 보존했다.
- dead code 외 duplication, naming/error handling, 불필요한 abstraction은 공개 계약을 유지하면서 개선할 고신뢰 후보가 없어 변경하지 않았다. 새 의존성은 추가하지 않았다.
- 프로젝트·패키지 버전을 1.0.1로 올리고 `uv.lock`, CLI·bundle 버전 회귀 테스트, 한국어 릴리스 문서를 동기화했다.

### 1.0.1 cleanup 검증 기록

- 표적 회귀 테스트: `18 passed`
- Ruff format/check: 49개 Python 파일 통과
- Pyright strict: 오류·경고 0건
- 전체 Pytest: `50 passed`
- release audit: 비밀·로컬 경로·필수 문서·참조 import 경계 통과
- build/bundle: `llmex-1.0.1.tar.gz`, `llmex-1.0.1-py3-none-any.whl`, 120개 파일 checksum과 65개 구성요소 SBOM 생성 통과
- `git diff --check`: whitespace 오류 없음

## 2026-07-11 — 1.1.0 최종 리뷰 차단 해소

- 보호 CI trust store 기반 HMAC-SHA256 승인 서명, RFC3339 발급·만료, issuer/role allowlist, 승인자 분리, evidence SHA-256, 버전·Git commit·config fingerprint 결속을 구현했다.
- pipeline evidence schema와 빈 JSON 거부, 단계 산출물 checksum/크기/schema 재검증, 실행 중 time/token/energy budget 중단, 실제 중단·손상·정리·재개 drill을 추가했다.
- checkpoint는 `weights_only=True`만 사용하며 NumPy RNG를 안전 tensor/basic type으로 저장한다. 악성 pickle 비실행 회귀를 추가했다.
- cloze 조건부 평균 log-likelihood·rank·accuracy와 canary 실제 rank gate/미실행 실패-폐쇄, 단일-pass 유계 메모리 exact/near contamination을 구현했다.
- 재개 세션 delta 처리량과 누적 wall-time 처리량을 분리하고 wheel/sdist digest, wheel METADATA 기반 SBOM, 배포 artifact subject provenance를 생성한다.
- artifact/JSON/sidecar 원자 쓰기·fsync 계약을 통일하고 split ADR을 실제 normalized-content SHA-256 계약과 일치시켰다.

## 2026-07-11 — 1.3.0 긴급 보안 키 회전

- 기존 1.3.0 root/issuer 키는 private key 로그 노출로 즉시 폐기했으며 더 이상 신뢰할 수 없다.
- 비밀키는 저장소, 로그 또는 명령 인자에 저장하지 않는다.
- 새 production policy는 fail-closed provisioning anchor로 교체했다. 실제 issuer private key는
  보호된 CI KMS/HSM에서 별도로 provisioning해야 한다.

## 2026-07-11 — 한국어 실행 가이드 추가

- `docs/run-guide.md`에 공식 Wikimedia dump URL·SHA-1과 프로젝트 고정 SHA-256을 구분해 기록했다.
- data download, 1,000문서 canary E2E, 전체 extract/clean/dedup/split/report, tokenizer
  train/evaluate/pack, model inspect, smoke train/resume, eval/generate/benchmark의 실제 `uv run`
  명령과 입력·출력 경로를 실행 순서대로 정리했다.
- `docs/README.md`에서 실행 가이드를 연결하고 Markdown 링크와 CLI help 계약을 점검했다.
