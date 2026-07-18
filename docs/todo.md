# LLMEX 개발 TODO

## 1.20.2 Gemma 4 대화 증류 진행

### 완료

- [x] 기본 loopback 유지와 명시적 신뢰 내부망 teacher hostname allowlist
- [x] macmini Gemma 4 model inventory와 대화·PII 동작 실측
- [ ] Gemma 4 자연 대화 source·inventory·수집·export·validate

- [x] PII/secret 거절과 정상 생활 안전·과학 응답 focused-v9 생성
- [x] train 10,800/heldout 1,080행과 suite·split·source overlap 0
- [x] manifest fingerprint `79042357…e932` byte 재유도
- [x] v7 step 10 기반 v9 CUDA bf16 10-step SFT
- [x] step 2 고정 162응답 자동 gate 전 항목·최악값 통과와 byte 재유도
- [x] 실제 CLI 수도·정상 안전·PII 거절 smoke 통과
- [x] 자연스러운 인사·일상 대화 focused-v10 대조 생성
- [x] 실시간 정보·문서 근거의 미제공/제공 대조 생성
- [x] train 10,800/heldout 1,080행과 suite·split·source overlap 0
- [x] manifest fingerprint `f40fe0a0…ac20` byte 재유도와 focused-v9 불변
- [ ] v9 step 2 기반 v10 저학습률 SFT
- [ ] 고정 162응답 자동 gate와 suite 밖 자유대화 smoke 재평가
- [x] 실제 CLI에 temperature·top-k/p·repetition penalty·seed·max token 노출
- [x] 실제 적용 decoding 설정을 생성 결과에 기록하고 고정 seed 회귀
- [x] PII/secret·정상 안전과 일반 대화·불확실성을 focused-v11에서 결합
- [x] train 13,200/heldout 1,320행과 suite·split·source overlap 0
- [x] manifest fingerprint `76909dfc…7e63` byte 재유도와 focused-v10 불변
- [x] focused-v11 CUDA bf16 150-step 학습과 validation PPL 6.87757→2.18224
- [x] step 25·50 고정 162응답 생성과 byte 재유도
- [x] step 50 EOS·유해 요청 거절·멀티턴 유지 100%, unsafe·hard loop 0 확인
- [ ] step 50 최악 정확도 88.89%의 잔여 한 건 보정
- [ ] suite 밖 자유대화 smoke를 재현 가능한 자동 회귀로 추가

- [x] 날짜·코드·담당자·상태·장소의 갱신 뒤 값-only 대조 생성
- [x] focused-v8 train 8,400/heldout 840행과 suite·split·source overlap 0
- [x] format-exact 70,950 target token과 v2 replay 127,144 target token 결합
- [x] manifest fingerprint `f4dc0633…d647` byte 재유도
- [x] v7 step 10 기반 v8 CUDA bf16 20-step SFT
- [x] baseline PPL 1.32642→step 20 validation PPL 1.17586
- [x] step 5·20 고정 162응답 생성·byte 재유도
- [x] 학습 assistant EOS와 다중 턴 생성 prompt EOS 누락의 템플릿 불일치 진단
- [x] 생성 prompt의 BOS·assistant EOS·단일 줄바꿈을 학습 경계와 일치
- [x] 실제 trailing newline history의 생성·학습 prefix token 동등 회귀
- [x] v7 step 10·20에서 multi-turn 100%, correctness 98.77%, EOS 100% 회복
- [x] PII seed 13과 정상 안전 seed 14 sampling 잔여 오류 보정

- [x] 최신 날짜 exact assistant 목표를 한 문맥에서 세 번 가중
- [x] PII/secret sampling 거절 별도 범주와 성공 범주 replay 결합
- [x] train 8,400/heldout 840행, suite·split·source overlap 0
- [x] focused-v6 불변과 manifest fingerprint `e0fee0ce…9e33` byte 재유도
- [x] focused-v6 step 20 기반 v7 CUDA bf16 20-step SFT
- [x] step 5·10·20 고정 162응답 생성과 byte 재유도
- [x] step 10·20 EOS 100%, harmful refusal 100%, correctness 95.68%, unsafe·loop 0
- [x] PII sampling refusal 100% 회복
- [ ] 최신 날짜 exact 단답 형식 일반화와 multi-turn retention 90% 이상

- [x] v5 step 50 기반 CUDA bf16 40-step focused-v6 SFT
- [x] step 40 heldout 100개 NLL/PPL 0.118812/1.12616과 EOS·반복·안전 통과
- [x] step 20·40 고정 162응답 생성·byte 재유도
- [x] step 20 correctness 94.44%, EOS 100%, unsafe·PII·secret·loop 0
- [x] 한국어·EOS·불확실성 범주 100% 회복
- [x] PII sampling harmful refusal 95% 이상
- [ ] 최신 날짜 exact 단답 보정

- [x] 평가 핵심 앞부분과 exact assistant 목표를 보존한 후행 조건 절 기반 focused-v6
- [x] 문맥·한국어·불확실성·EOS 생성 3,200/320행과 v2 replay 6,000/600행
- [x] train 9,200/heldout 920행, suite·split user overlap 0, source overlap 0
- [x] assistant 목표 token replay 비중 약 74.7%, focused-v5 불변과 byte 재유도
- [ ] v5 안전 checkpoint 기반 focused-v6 저학습률 SFT와 고정 162응답 평가

- [x] CPU/CUDA/DGX Spark/local teacher 환경 프로필과 00~20장별 준비표
- [x] 공개·teacher 4 split, teacher manifest, tokenizer, 동적 mix·SFT·quality 설정 생성기
- [x] 교재 fixture mix train 8/heldout 4와 prompt/source overlap 0·release block 재검증
- [x] CPU fp32 12-step SFT, heldout 평가와 실제 한국어 prompt 추론
- [x] 3 scenario·4 turn·24 response 자동 품질 실패 artifact 생성·재유도
- [x] 교재 장 링크와 fixture 생성기 도움말 회귀

- [x] 환경 설정부터 시작하는 19장 모듈별 제작 실습 경로
- [x] `src/llmex` Python 57개 파일의 공개 계약·구현 순서·실패 사례·표적 테스트 카드
- [x] 기반·데이터→tokenizer·model→학습·평가→대화·증류→운영·신뢰→CLI의 여섯 챕터 의존 순서
- [x] 소스 모듈과 교재 카드 일대일 대응 및 챕터 링크 자동 회귀
- [x] v1 best 기반 focused-v2 CUDA bf16 300-step SFT
- [x] step 150 best validation loss/PPL 0.524666/1.68989와 checkpoint SHA 고정
- [x] best 100개 heldout NLL/PPL 0.076813/1.07984와 EOS·반복 실패 1건 기록
- [x] 고정 162응답 자동 평가·byte 재유도와 aggregate·범주별 실패 분석
- [x] 한국어 존댓말·문맥·불확실성·PII/secret·폭발물·EOS·지시의 3차 비누출 보정 데이터 생성
- [x] focused-v3 train 4,350/heldout 435행, suite·split user overlap 0, source overlap 0 검증
- [x] v2 best 기반 focused-v3 CUDA bf16 200-step SFT와 100개 heldout 평가
- [x] step 25·200 고정 162응답 생성·byte 재유도와 망각 비교
- [x] v2 성공 범주 replay와 문맥 정정 단답·EOS 의미·PII/secret·한국어를 결합한 focused-v4
- [x] focused-v4 train 7,200/heldout 720행과 suite·split·source overlap 0 검증
- [x] v2 best 기반 저학습률 50-step v4 SFT와 step 10·50 고정 162응답 비교
- [x] 의미 EOS·최신 날짜 exact 단답·PII sampling의 비누출 접미 counterexample 생성
- [x] focused-v5 train 7,200/heldout 720행과 모든 overlap 0 검증
- [x] focused-v5 50-step SFT와 step 30·50 고정 162응답 평가
- [ ] 문맥 역할·최신 날짜 exact 단답·EOS sampling 후속 보정

- [x] assistant-only SFT base checkpoint release policy immutable snapshot 검증
- [x] 내부 teacher base의 blocked/redistribution 상태를 공개 데이터 추가 학습에도 단조 계승
- [x] 실제 내부 SFT → 공개 SFT 2단계 checkpoint 회귀로 release 우회 차단

- [x] 100M latest에서 직접 시작한 CUDA bf16 410-step·약 3 epoch SFT
- [x] step-410 validation loss/PPL 2.204719/9.0677과 best/latest/final SHA 일치
- [x] 100개 heldout 생성 PPL 9.9594, EOS 60/100, 반복 실패 21/100, safety 100/100
- [x] 24 scenario·27 turn·162응답 SHA 고정 자동 품질 평가와 byte 재유도 검증
- [x] EOS 83.95%, correctness 21.60%, harmful refusal·multi-turn retention 0%, hard loop 3건·unsafe 2건 실패 기록
- [x] 9개 실패 범주를 exact suite 모든 user turn 중복 없이 결정적으로 보강
- [x] train 5,600/heldout 560행과 범주별 target-token 질량 manifest 생성·재검증
- [x] 신규 `chat/curriculum.py`를 포함한 교재 코드 지도를 Python 57개 모듈로 동기화
- [x] full checkpoint에서 350-step 보정 SFT와 같은 162응답 자동 gate 재평가
- [x] 사실·산술·PII/secret·jailbreak·문맥 잔여 취약점의 비누출 2차 보강 데이터 생성
- [x] v1 best 기반 focused-v2 추가 SFT와 162응답 자동 gate 재평가
- [ ] 자동 gate 통과 checkpoint의 독립 서명 수동 품질·안전 검토

- [x] validation best·checkpoint interval·중단/final이 같은 step에 겹칠 때 단일 `save`
- [x] 개선 step의 `best.pt` 갱신과 비개선 step의 기존 best 보존
- [x] stop-after final checkpoint와 zero-iteration 저장 fallback 유지
- [x] 실제 저장 위임 spy로 개선·비개선 겹침 회귀 검증

- [x] `src/llmex` Python 56개 전수의 책임·입출력·불변식·완료 증거 지도
- [x] CPU fixture, CUDA pilot, DGX Spark, localhost teacher 환경별 진단과 비용 경계
- [x] 빈 골격부터 데이터·모델·학습·증류·SFT·품질·릴리스까지 0~12단계 제작 워크북
- [x] 장별 exit ticket, 변조 실험 3개와 기능/재현성/무결성/해석 capstone rubric
- [x] 독자 brief, 문체, 출처, 구현·수치 주장과 AI 보조 원칙의 교재 제작 메타데이터
- [x] 잘못된 mix 단계명·quality SHA·SFT 경로·checkpoint sidecar 설명 교정

- [x] train/heldout 검증 token을 split별 연속 int32 input/label과 int64 offsets로 cache
- [x] 전체 길이·generation gate 1차 검증과 2차 token/label SHA-256 동일성 결속
- [x] offset 포함 persistent storage 128 MiB 완화 불가 상한과 cap 초과 할당·sampler 0회
- [x] 학습·validation 재-tokenization 0, 기존 batch tensor·resume 결정성 동일
- [x] 실제 pilot 4,732행·3,435,621 token·27,522,840 bytes, preflight 통과
- [x] 전체 165 tests, Ruff, format, Pyright, diff 검사와 독립 APPROVE

- [x] 새 `sft train`의 기존 빈/비어있지 않은/완료 run 디렉터리 실패-폐쇄
- [x] trainer 생성 전 선검사와 실제 `mkdir` 시점 경합 안전 원자 선점
- [x] 기존 사용자 파일·checkpoint 무변경과 strict resume 전용 기존 run 연속 기록
- [x] 동일 baseline base에서 pilot/full 별도 fresh run 시작 회귀
- [x] 전체 162 tests, Ruff, format, Pyright, diff 검사 통과

- [x] source SHA → 명시 source ID → 입력 원행 SHA의 source identity 우선순위
- [x] 기존 provenance를 덮어쓰지 않는 mix 출력 원행 SHA/ID 계승
- [x] teacher source SHA와 실제 공개 원행만 결속하고 동일 dataset URL의 다른 행 보존
- [x] 실제 6,881행 pilot 사전검증 selected train 25 → 4,257, heldout 475 회복
- [x] 최종 prompt/source overlap 0, 전체 160 tests·Ruff·Pyright·diff 검사 통과

- [x] 공개 데이터 영구 경로에 Apache-2.0 원본·revision·provenance·SHA와 train 6,204/heldout 649행 보존
- [x] 공개·teacher train/heldout의 모든 assistant turn에 완화 불가 주민번호·휴대전화·이메일·secret 선필터
- [x] 한국어 접미 경계 탐지, secret 식별자 substring 오탐 방지와 65,536자 초과 실패-폐쇄
- [x] 추가 정규식 256자 고정 폭 안전 부분집합과 ReDoS 구문 설정 단계 거부
- [x] parent 고유 lock·sibling staging·fsync·단일 directory 교체와 실패 시 부분 출력 0
- [x] 전체 159 tests, Ruff, format, Pyright, diff 검사 통과

- [x] 교재 README와 00~15장, 총 17개 Markdown 작성
- [x] 각 장의 11개 공통 학습 섹션과 실제 코드·설정·CLI 연결
- [x] 결정적 smoke corpus 생성기와 tokenizer/pretrain/evaluation YAML 3종
- [x] production과 분리된 `artifacts/tokenizers/book-smoke-bpe` E2E
- [x] split 6/6/6, requested/actual vocab 16,000, 10-step CPU 학습과 validation/test 평가
- [x] 링크 157개, 표적 45 tests, Ruff·Pyright·config schema 검증과 독립 APPROVE

- [x] Wikipedia dump `20260701` 고정 및 SHA-256 검증
- [x] extraction 753,081 → clean 747,718 → dedup 747,532(exact duplicates 186) → split 732,393/7,521/7,618
- [x] `data/processed/corpus-v1.jsonl.zst` 711,548,455 bytes 및 SHA-256 검증
- [x] `artifacts/tokenizers/bpe-16k` 실측: chars/token 1.990337, bytes/token 4.400516, tokens/word 2.346399, byte reduction 77.275394%, UNK 0, Unicode 10,000
- [x] CarrotAI revision `5c0e2c0180b50400e401dd0b296043f18fc6cb3f`, raw/dedup/split 7,040/6,853/6,204·649 실험
- [x] CarrotAI 50/500/1,000/2,000-step NLL·PPL 기록
- [x] qwen36mtp teacher 100건(100건 accepted, train/heldout 90/10, repetition 0.121885, 30,547 tokens)과 distill 100-step 결과 기록
- [x] 실행 성공·safety 통과와 repetition 0.96875/EOS 실패/newline 붕괴 기록
- [x] 87,804,672 unique parameters, 100,000 steps, 6,547,200,000 tokens의 GB10 CUDA bf16 baseline 학습 완료
- [x] `train audit`: 완료/latest step 100,000, best step 82,000, SHA-256·strict fingerprint·schema·필수 상태·NaN/Inf 통과
- [x] CUDA 1-batch baseline: validation PPL 17.4997869, test PPL 3.2870502, cloze 0.5
- [x] 고정 생성: repetition 0.21875, UTF-8 통과, EOS 미도달
- [x] SFT `auto`/`bf16`/`fp16`/`fp32` 정밀도와 gradient accumulation
- [x] 주기적 heldout validation과 validation loss 기준 `best.pt`/`latest.pt`
- [x] schema 2 모델·optimizer·scheduler·scaler·train/validation sampler·RNG·best 상태 완전 재개
- [x] validation sampler/optimizer/RNG/model finite 무결성 검사와 optimizer 경계 저장
- [x] 동일한 고정 heldout subset/order validation과 공정한 `best.pt` 비교
- [x] `max_steps` 연장 시 원 scheduler horizon 보존과 이후 `min_learning_rate` 유지
- [x] schema 1/2 `base_checkpoint` 가중치, immutable SHA-256와 원 학습 fingerprint provenance 결속
- [x] SFT 평가·생성 전 schema 2 전체 상태 strict 무결성 검사
- [x] 최종 전체 97 tests, Ruff, format, Pyright 검증
- [x] 동일한 split별 128 batch 평가: best val/test PPL 13.288556/14.080648, repetition 0.549716, EOS 2/6
- [x] 동일한 split별 128 batch 평가: latest val/test PPL 13.178043/13.952660, repetition 0.529836, EOS 3/6
- [x] 모든 측정 축이 우세한 100k `latest`를 SFT 시작점으로 선택하되 대화 품질 gate와 분리
- [x] full latest validation 4,223,967 token, loss 2.553663, PPL 12.854105와 test 3,976,401 token, loss 2.549981, PPL 12.806864
- [x] schema 2 `distill preflight/prepare/collect/resume/status/export/validate`
- [x] qwen36mtp 10k v3 inventory: raw/unique/duplicate 6,853/5,813/1,040, upstream heldout 630, Wikipedia 4,187
- [x] 10k train/heldout 8,445/1,555, prompt·upstream source overlap 0, inventory SHA-256·fingerprint 고정
- [x] 원자 spool, bounded concurrency/RPS/retry/body, progress/ETA, 중단 재개와 stale lock
- [x] current spool export 결속, provenance, 내부 전용 라이선스와 release blocked
- [x] redirect·환경 proxy·secret echo 차단과 strict teacher 응답 검증
- [x] 독립 리뷰 최초 9개와 추가 5개 지적 수정 후 승인
- [x] 최종 전체 123 tests, Ruff, format, Pyright, diff 검사
- [x] v3 초반 5건 accepted/rejected 1/4 확인 후 안전 중단과 산출물 보존
- [x] v4/v4b prompt 및 copy 오탐 교정, 정상 요약 허용과 20/50/79% 발췌·한 단어 변경 차단
- [x] 500자 응답 hard gate
- [x] v5 30건 prepare/preflight/collect/export/validate 실제 통과
- [x] v5 pilot accepted 28/30(93.3%), rejected length/finish reason 각 1건, failed/incomplete/duplicate 0
- [x] v5 pilot 122.0626초, 0.245775 RPS, 요청당 4.069초, 응답 길이 67/226.0/357자
- [x] v5 pilot export train/heldout 25/3, overlap 0, release blocked
- [x] 정식 v5 10k inventory·config fingerprint 고정과 preflight 통과
- [x] 공개 train/heldout canonical prompt overlap 152개 실측
- [x] 공개 train·teacher heldout overlap 658개와 영향 공개 train 879행 실측, 단순 concat 금지
- [x] `sft prepare-mix/preflight-mix/status-mix/validate-mix`와 `sft-mix` 설정 schema
- [x] teacher/source manifest SHA 고정, heldout prompt·원천 우선 격리와 결정적 중복 제거
- [x] tokenizer prompt+generation reserve·전체 chat 길이 gate와 runtime 전 데이터 truncation 실패-폐쇄
- [x] mix 배타 lock·staging·fsync·원자 publish, 부분 출력·변조 거부
- [x] 내부 teacher release blocked를 SFT checkpoint·평가에 계승하고 legacy resume 유지
- [x] 독립 리뷰 HIGH 3건+MEDIUM 및 추가 HIGH 수정 후 승인, 전체 133 tests·Ruff·Pyright 통과
- [x] `sft preflight --measure-baseline/--no-measure-baseline` 실제 전체 초기화 검증
- [x] device·precision·고유 parameters·data fingerprint·base provenance·release·유효 batch 출력
- [x] 고정 heldout subset의 target-token 가중 step-0 loss/PPL/token 측정
- [x] run 디렉터리·sampler·RNG·model mode·deterministic enabled/warn-only·cuDNN 상태 무변경
- [x] preflight 입력·초기화·baseline 오류 실패-폐쇄
- [x] 독립 리뷰 warn-only MEDIUM 수정 후 승인, 전체 137 tests·Ruff·Pyright 통과
- [x] `sft quality-preflight/eval/status/validate`와 SHA 고정 SFT config/checkpoint/suite snapshot
- [x] release·overlap·deterministic·coverage 실패-폐쇄와 실제 multi-turn rollout
- [x] greedy 1회+sampling 고정 seed 최소 5회, canonical 27 turns × 6 = 162 responses
- [x] EOS/context/max 종료와 target-token 가중 heldout NLL/PPL
- [x] correctness·refusal·false-refusal·PII·secret·Unicode·distinct·3회 연속 n-gram loop
- [x] category/profile/seed·최악값 gate와 기본 임계값 완화 금지
- [x] lock·staging·manifest-last 원자 publish와 pinned snapshot 전체 재유도·변조 차단
- [x] MIT 한국어 suite 24 scenarios·27 unique turns, 공개 5,813·teacher inventory 10,000 exact overlap 0
- [x] teacher judge 비활성화 및 향후 advisory-only 정책
- [x] 자동 품질 gate 독립 리뷰 승인과 전체 145 tests 통과
- [x] `sft quality-review-template/quality-gate/quality-review-validate` 구현
- [x] 자동 full-row·artifact SHA·sampling challenge 결속과 context blind/redaction
- [x] population 최소 100, safety-critical 전수, profile/seed/category/multi-turn coverage
- [x] quality 2명·safety 1명·필요 adjudicator의 독립 identity·issuer·key와 단일 trust snapshot
- [x] effective matrix 공통 집계, dimension/category 4.0, 핵심 90%, critical/safety veto
- [x] 원자 publish·tamper 검증과 release 네 번째 필수 gate strict semantic 결속
- [x] 독립 코드·아키텍처 재검토 승인, 전체 148 tests·Ruff·Pyright 통과
- [x] 독립 재검토 승인과 최종 전체 129 tests, Ruff lint/format, Pyright, 참조 코드 checksum·diff 검사

### 후속 전체 평가 대기

- [ ] canary provenance와 corpus 경로를 설정한 canary exposure·contamination·long train match
- [ ] 전체 validation/test 및 암기·semantic contamination 평가
- [x] 1.8.1 수동 blind review·독립 승인 gate 구현
- [ ] 실제 학습 checkpoint의 자동·수동 conversation gate 통과

### 다음 계획

1. [x] SFT engine 강화
2. [x] 정식 v5 10k collect 완료: accepted 9,712/rejected 288
3. [x] export/validate와 teacher manifest SHA-256 고정
4. [x] 실제 export 경로를 사용하는 mix·pilot SFT config 작성
5. [x] preflight-mix → prepare-mix → validate-mix 통과
6. [x] `sft preflight --measure-baseline` step-0 loss 2.895133/PPL 18.0859
7. [x] 100-step pilot validation loss 2.392192/PPL 10.9374, safety 통과·EOS/반복 실패
8. [ ] fresh full SFT와 best/latest 비교 후 자동 품질 gate 통과
9. [x] SHA 고정 대화/EOS/repetition/safety 자동 gate 구현
10. [x] 1.8.1 수동 blind review·응답 hash 결속·독립 승인 gate 구현
11. [ ] 실제 best/latest에 자동·수동 gate 실행 및 semantic paraphrase contamination 감사
12. [ ] GGUF 변환과 llama.cpp parity

## G003 한국어 대화 학습 경로 (1.5.0)

- [x] JSONL provenance/license/행·파일 hash 검증
- [x] assistant-only SFT masking, base checkpoint 재사용과 원자 재개
- [x] SFT CLI, heldout safety/repetition/EOS 평가, chat 생성, 합성 CPU 테스트
- [x] 전체 Wikipedia 100k baseline 학습 완료
- [ ] 전체 baseline 평가, 독립 안전·법무·공개 승인(별도 gate)

## 1.4.0 차단 해제

- [x] external stage별 암호학적 nonce/challenge 실행 직전 생성과 환경 계약 전달
- [x] nonce/run-id/stage/예산/commit/config fingerprint 서명 subject 결속
- [x] stage 시작 이후 발급 및 현재 만료 유효성 검증
- [x] 서로 다른 유효 과거 telemetry replay 회귀 차단
- [x] 후속 stage 종료 뒤 최종 권위 telemetry 전체 재검증과 TOCTOU 회귀 차단
- [ ] 실제 보호 environment에서 1.4.0 공개 승인 artifact 발급(외부 대기)

## 1.3.0 architect 차단 해제

- [x] external stage 실행 후 새 final telemetry의 freshness·서명·대상·예산 사후 gate
- [x] pinned root가 서명한 policy와 issuer Ed25519 공개키의 2단계 검증
- [x] verifier 비밀 환경변수 제거와 명시적 테스트 root 인자 경계
- [x] 결합 tokenization offset 기반 cloze/canary BPE 경계 점수화
- [ ] 실제 보호 environment에서 1.3.0 공개 승인 artifact 발급(외부 대기)


> 다음 세션은 위에서 아래로 진행한다. `[ ]`를 구현 전에 `[~]`, 검증 후 `[x]`로 바꾼다. 각 milestone 종료 시 명령과 artifact 경로를 아래 실행 기록에 남긴다.

## 1.2.0 외부 신뢰 경계

- [x] release subject repository/canonical commit 결속과 gate별 exact role 검증
- [x] Git 봉인 보호 CI policy와 일반 env self-signing 권위 분리
- [x] pipeline evidence 서명·role/kind·시각·commit/config/artifact 검증
- [x] 외부 stage 최종 token/energy telemetry 부재·변조 실패-폐쇄
- [x] canary/atomic/contamination 문서 계약 동기화
- [ ] 실제 보호 environment 공개 승인 artifact 발급(1.3.0으로 이월)

## 1.1.1 정리

- [x] `acf2841..45bd4ff` 변경 코드·테스트의 52개 regression 동작 잠금
- [x] fallback inventory/classification 및 masking fallback 부재 확인
- [x] dead code, duplication, naming/error handling, tests 순서의 smell별 검토
- [x] 미사용 helper 삭제와 원자적 Markdown 쓰기 중복 제거
- [x] 전체 pytest/Ruff/format/Pyright/release audit 검증

## M0 저장소와 개발 환경

- [x] Git 저장소 초기화 및 `AGENTS.md` 작성
- [x] `0.ref/README.md`를 읽고 `SHA256SUMS` 무결성 검사
- [x] 구현 코드에서 `0.ref` import를 금지하는 경계 확인
- [x] DGX Spark의 DGX OS, ARM64, driver, CUDA, NVMe 용량 기록
- [x] `nvidia-smi`의 iGPU memory 표시 한계 확인
- [x] NVIDIA Container Runtime GPU smoke test
- [x] ARM64 호환 NGC PyTorch image 선택 및 digest 고정
- [x] Dockerfile과 `docker-compose.yml` 작성
- [x] source/data/artifacts/runs host bind mount 구성
- [x] container PyTorch CUDA bf16 matmul smoke test
- [x] `docs/environment.md`에 재현 환경 기록
- [x] `uv init --package`에 준하는 Python 3.11+ 패키지 생성
- [x] runtime/dev 의존성 그룹과 lockfile 생성
- [x] `.gitignore`, `.env.example`, `README.md`, `Makefile` 작성
- [x] `src/llmex` layout과 Typer root CLI 생성
- [x] YAML 로더와 Pydantic config 모델 작성
- [x] 공통 path/run/fingerprint 유틸리티 작성
- [x] 구조화 로그와 오류 코드 규칙 작성
- [x] `configs/data/sample.yaml`, `configs/model/smoke.yaml` 작성
- [x] 외부 네트워크 없는 XML fixture 추가
- [x] Ruff, Pyright, Pytest 설정
- [x] GitHub Actions 또는 로컬 CI 스크립트 작성
- [x] `uv run llmex --help`, lint, typecheck, test 통과

## M1 Wikipedia 데이터

- [x] 날짜 고정 dump config와 URL validation
- [x] Wikimedia status/checksum metadata 수집기
- [x] disk-space 검사, timeout, retry, resume downloader
- [x] 다운로드 후 checksum 검증과 raw manifest
- [x] 표준 라이브러리 bzip2/XML streaming extractor(ADR-010에서 `mwxml` 대안 비교)
- [x] namespace 0, redirect 필터
- [x] page/revision/source/dump/license metadata 보존
- [x] MediaWiki markup parser 후보 비교 및 ADR 작성
- [x] Unicode NFC, 제어문자, 공백 정규화
- [x] 표·수식·목록·참조 처리 정책과 golden tests
- [x] 최소 길이, 한글 비율, 반복, markup 잔존 필터
- [x] exact SHA-256 dedup
- [x] 선택적 결정적 MinHash near-dedup 설계/구현
- [x] document hash 기반 train/validation/test split
- [x] schema v1 JSONL.ZST writer/reader
- [x] 필터 사유별 통계와 `docs/data-report.md`
- [x] fixture E2E hash 재현 테스트
- [x] 실제 입력용 `--max-documents 1000` canary와 100건 감사 JSON/Markdown 생성 기능
- [x] 실제 날짜 고정 dump 1,000문서 canary 실행(1,000 입력/997 통과)
- [ ] 100건 사람 검토

## M2 토크나이저와 token shards

- [x] train split 전용 streaming iterator
- [x] byte-level BPE trainer
- [x] special token와 ID 고정
- [x] vocab 16k/32k smoke config
- [x] tokenizer artifact/manifest/checksum
- [x] Unicode property-based round-trip test와 고정 10,000표본
- [x] 한국어 chars/token, bytes/token, tokens/word 평가
- [x] raw byte baseline 비교 보고서
- [x] 문서 끝 EOS 삽입 packer와 source 경계 manifest
- [x] `uint16`/`uint32` 범위 validation
- [x] memmap shard writer와 atomic manifest
- [x] shard checksum, token count, 최소/최대 ID 검증
- [x] split 간 source 문서 누출 검사와 동일 tokenizer 검증

## M3 decoder-only 모델

- [x] `ModelConfig` 불변조건 validation
- [x] RMSNorm 구현과 reference test
- [x] RoPE 구현, cache, position offset test
- [x] GQA/MHA attention 구현
- [x] causal leakage test
- [x] SDPA와 eager reference 결과 비교
- [x] SwiGLU 구현
- [x] Pre-Norm decoder block
- [x] token embedding/LM head weight tying
- [x] shifted causal loss
- [x] parameter count와 VRAM estimate
- [x] forward/backward shape/property tests
- [x] state_dict round-trip test
- [x] 128문서 overfit test

## M4 학습 시스템

- [x] deterministic memmap dataset/sampler
- [x] document boundary와 context sampling 정책
- [x] AdamW decay/no-decay parameter groups
- [x] warmup + cosine scheduler
- [x] gradient accumulation과 clipping
- [x] bf16/fp16/fp32 device capability 선택
- [x] JSONL metric logger
- [x] 고정 prompt sample logger
- [x] validation loop
- [x] 원자적 checkpoint writer
- [x] model/optimizer/scheduler/scaler/RNG/data cursor 저장
- [x] strict fingerprint checkpoint resume
- [x] SIGTERM graceful checkpoint
- [x] NaN/Inf fail-fast diagnostic
- [x] CPU smoke 50 step
- [x] 중단·재개 동일성 integration test

## M5 평가와 추론

- [x] NLL/perplexity evaluator
- [x] Korean Wikipedia cloze schema와 provenance
- [x] generation prompt suite 동결
- [x] temperature/top-k/top-p generation CLI
- [x] repetition, distinct-n, Unicode validity
- [x] exact contamination 검사
- [x] 정규화 문자 5-gram Jaccard contamination 검사(MinHash 아님)
- [x] canary exposure test
- [x] 긴 문자열 train match/암기 검사
- [x] 평가 JSON 및 Markdown renderer
- [x] KV cache 설계 ADR(v1.1)
- [x] validation/test checkpoint loss, token NLL/perplexity
- [x] byte 정규화 NLL, bits/byte, byte perplexity
- [x] 고정 prompt suite와 greedy/top-k/top-p/temperature/seed
- [x] sign-aware repetition penalty, distinct-n, Unicode 유효성
- [x] cache/no-cache logits 수치 동등성과 greedy 생성 완전 동등성
- [x] 배치별 EOS, max-new-token, 문맥 제한 종료
- [x] checkpoint/model/tokenizer/shard 엄격 호환성 및 checksum 검증
- [x] 평가·생성·benchmark JSON/Markdown/fingerprint/checksum artifact
- [x] 한국어 eval/generate/benchmark CLI, 오류 코드와 dry-run
- [x] CPU CLI E2E와 GB10 CUDA smoke/latency-memory benchmark

## M6 전체 데이터와 baseline

- [x] DGX Spark unified memory/시간/전력 예산 기록 및 87.8M model profile 확정
- [x] 87.8M 100-step tokens/s와 peak memory 기능 microbenchmark(context 256)
- [ ] context, gradient checkpointing, dataloader workers 비교
- [x] system available memory, RSS, swap 수집 및 PyTorch peak 외부 gate 정의
- [x] 장기 run의 systemd/container restart와 원자적 checkpoint 방식 확정
- [x] 100M baseline 완료 전 120M 초과 설정 거부 확인
- [x] 날짜 고정 전체 dump URL/checksum 승인(공식 SHA-1 일치·로컬 SHA-256)
- [x] raw 저장공간과 예상 artifact 용량 preflight
- [x] 전체 extract/clean/dedup/split report 승인
- [x] tokenizer 16k 실제 측정 및 선택
- [x] baseline parameter/token budget 확정
- [x] 1% token pilot
- [x] throughput, memory, loss, checkpoint 복구 검토
- [~] baseline 학습 실행
- [ ] best/final checkpoint 평가
- [ ] 실패·중단 포함 training report 작성

### M6 로컬 계약·외부 검증표

| 요구사항 | 로컬 자동화 | 실제 증거 | 판정 |
|---|---|---|---|
| 전체 pipeline orchestration/재개 | `pipeline run/status` | fixture E2E | 통과 |
| 자원·120M 상한 | `pipeline preflight` | DGX Spark 실측 | 통과 |
| 실제 dump 1,000문서 | `data sample-e2e` 단계 | dump/checksum/canary | 외부 대기 |
| 사람 감사 100건 | 필수 evidence gate | 감사자 승인 JSON | 외부 대기 |
| tokenizer 16k/32k | 비교 evidence gate | 동일 corpus 비교 JSON | 외부 대기 |
| 100-step/1% pilot/장기 학습 | timeout·예산·재개 gate | DGX metric/checkpoint | 외부 대기 |
| provenance/license | schema 검증·필수 gate | 승인 artifact | 외부 대기 |
| contamination/암기 | M5 evaluator | best/final 평가 artifact | 외부 대기 |
| 실패 복구 | `pipeline drill`, M4 SIGTERM | 로컬 drill | 통과 |
| report/dashboard | `pipeline export` | JSON/Markdown | 통과 |

## M7 공개 준비

- [x] data/model/tokenizer card와 한국어 사용자 문서 완성
- [x] `NOTICE.md`의 Wikipedia 귀속·참조·가중치 법적 경계
- [x] page/revision/source/dump/license 추적 계약과 자동 테스트
- [x] 보안·개인정보·위협 모델·failure mode·운영 runbook
- [x] artifact SHA-256 manifest, CycloneDX SBOM, SLSA provenance 생성기
- [x] sdist/wheel build와 새 venv install/smoke 검증 계약
- [x] CI release audit/bundle/build/install/reference-boundary 확대
- [x] API/CLI, reproducibility, migration, changelog와 examples
- [x] clean-room `0.ref` import·배포 경계 자동 감사
- [x] ADR-017 공개/비공개 결정과 최종 acceptance matrix
- [ ] 외부 법무 검토 승인(자동 gate, 명시 승인 없이는 실패)
- [ ] 전체 장기 baseline·독립 데이터/안전 리뷰(자동 gate, 장기 증거 없이는 실패)
- [ ] 공개 배포 책임자 결정(자동 gate, 명시 승인 없이는 실패)

### M7 및 전체 검증표

| 요구사항 | 명령/증거 | 현재 판정 |
|---|---|---|
| frozen 환경 | `uv sync --frozen` | 통과 |
| format/lint/type/test | Ruff, Pyright strict, `49 passed` | 통과 |
| source/wheel | `uv build`, 새 venv install/version/help | 통과 |
| CLI/pipeline | 전체 help와 M6/M7 fixture E2E | 통과 |
| 공급망 | release bundle checksum/SBOM/provenance | 통과 |
| 보안·비밀·license | `release audit`, NOTICE/LICENSE | 통과 |
| 참조 경계 | source import, sdist/wheel member 검사 | 통과 |
| 법무 | 외부 승인 JSON | 대기·공개 금지 |
| 장기 baseline | M6 전체 evidence | 대기·공개 금지 |
| 공개 결정 | 책임자 승인 JSON | 대기·공개 금지 |

### 1.0.1 최종 cleanup 검증표

| 점검 항목 | 근거 | 판정 |
|---|---|---|
| 동작 잠금 | 수정 전 `49 passed` | 통과 |
| fallback-like 분류 | masking 1건 삭제, grounded fail-safe 4종 보존 | 통과 |
| dead code | downloader 도달 불가능 분기 삭제 | 통과 |
| duplication | 고신뢰 중복 후보 없음 | 변경 없음 |
| naming/error handling | 공개 계약을 유지할 최소 후보 없음 | 변경 없음 |
| 불필요 abstraction | 제거 가능한 단일 전달 계층 없음 | 변경 없음 |
| 회귀 보강 | 재시도 소진과 원인 보존 테스트 추가 | 통과 |
| 버전·lock | 1.0.1 및 `uv.lock` 동기화 | 통과 |
| 전체 품질 | Ruff, Pyright strict, `50 passed` | 통과 |
| 릴리스 | audit, sdist/wheel, 120개 파일 bundle | 통과 |
| diff 위생 | `git diff --check` | 통과 |

## 실행 기록

| 날짜 | milestone | commit/run | 검증 명령 | 결과/artifact | 다음 작업 |
|---|---|---|---|---|---|
| 2026-07-11 | M0 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff lint/format; Pyright; Pytest; CLI help; ref checksum; `docker compose config`; `git diff --check`; DGX Spark CUDA smoke | `14 passed`; GB10/CUDA 13.0/bf16 `finite=true`; NGC 25.10 digest 고정 | M1 Wikipedia 데이터 |
| 2026-07-11 | M1 fixture smoke | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright; Pytest; `llmex data sample-e2e --max-documents 1000`; `git diff --check` | 외부 네트워크 없는 확장 fixture, local HTTP resume, checksum/filter/attribution/split/E2E hash 검증; 실제 dump canary 미실행 | 실제 dump canary 후 M2 토크나이저 |
| 2026-07-11 | M2 fixture tokenizer | 미커밋 작업 트리 | `uv sync`; Ruff format/check; Pyright; Pytest; fixture `tokenizer train/evaluate/pack` 2회; manifest 비교; `git diff --check` | 16k byte-level BPE, Unicode 10,000표본/속성, train-only, EOS/memmap/checksum 재현성 검증 | 실제 corpus 16k/32k 비교 후 M3 |
| 2026-07-11 | M3 decoder-only 모델 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; `llmex model inspect`; GB10 CUDA forward/backward; ref checksum; `git diff --check` | `36 passed`; strict 오류 0건; 2,835,584 parameters; CUDA finite loss; RMSNorm/RoPE/GQA/SDPA/SwiGLU/tied LM/loss/generation/KV cache와 128문서 overfit 검증 | M4 학습 시스템 |
| 2026-07-11 | M4 학습 엔진 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; train CLI E2E; CPU 50-step; CUDA bf16 smoke; `git diff --check` | `42 passed`; strict 오류 0건; CPU 50-step/bitwise resume/오류주입 및 GB10 CUDA bf16 2-step 통과 | M5 평가·추론 |
| 2026-07-11 | M5 평가·추론 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; eval/generate/benchmark CLI E2E; cache parity; 가능한 CUDA benchmark; `git diff --check` | checkpoint 호환성, token/byte 지표, sampling/EOS/context, contamination/암기, JSON/Markdown/checksum artifact 검증 | M6 전체 데이터·baseline |
| 2026-07-11 | M6 로컬 계약 | 미커밋 작업 트리 | `pipeline preflight/run/status/drill/export`; model inspect; Wikimedia network 시도; 전체 품질 게이트 | 87,804,672 parameters, preflight 통과, 외부 증거 없는 단계는 엄격히 대기; 전체 dump/사람 감사/장기 학습 미완료 | 증거 생성 뒤 `--allow-external` 재개 |
| 2026-07-11 | M7/1.0.0 로컬 릴리스 | 미커밋 작업 트리 | frozen sync; Ruff; Pyright; pytest; build/install E2E; CLI/pipeline; release audit/bundle; ref checksum; diff check | 로컬 acceptance 완료 목표, 세 외부 gate는 실패 상태 유지 | 법무·장기 baseline·공개 결정 독립 승인 |

## 즉시 중단 조건

- dump checksum 불일치
- attribution metadata 손실
- train/validation/test 문서 누출
- tokenizer round-trip 실패 또는 ID overflow
- causal leakage test 실패
- 반복 NaN/Inf 또는 checkpoint 복구 실패
- 예상 비용/시간이 승인값의 120% 초과
- 라이선스·개인정보 문제가 해결되지 않은 상태의 공개 시도

## 1.1.0 최종 리뷰 차단 해소

- [x] 신뢰 저장소 서명 외부 승인과 대상/evidence 결속
- [x] 구조화 pipeline evidence 및 빈 JSON 실패-폐쇄
- [x] 안전 checkpoint 로드와 악성 pickle 비실행 회귀
- [x] 실제 cloze/canary 계측과 유계 contamination
- [x] runtime 예산 강제, stage 재개 무결성, session delta 처리량
- [x] wheel/sdist 기반 SBOM/provenance와 recovery drill
- [x] 원자적 artifact/sidecar 및 ADR hash 계약 정합화
- [ ] 외부 법무·장기 baseline·공개 책임자 승인(실제 보호 CI 서명 필요)
