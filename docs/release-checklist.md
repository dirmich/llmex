# 1.22.22 릴리스 체크리스트

## 자동 통과 항목

- [x] 한국어 data/model/tokenizer card와 NOTICE
- [x] 보안·개인정보·위협 모델, 운영·실패 모드 문서
- [x] checksum·SBOM·provenance 생성기와 테스트
- [x] sdist/wheel 빌드와 새 venv 설치 smoke 계약
- [x] API/CLI, migration/changelog, acceptance matrix
- [x] 비밀·절대 경로·`0.ref` import/패키지 경계 감사
- [x] SHA 고정 자동 대화 품질 gate 구현·독립 리뷰·회귀 검증
- [x] 최소 100개 blind sample과 safety-critical 전수·coverage 수동 gate 구현
- [x] quality 2명·safety 1명·필요 adjudicator의 독립 identity/issuer/key 및 서명 만료 검증
- [x] effective matrix, dimension/category 4.0, 핵심 90%, critical/safety veto
- [x] 수동 artifact 원자 publish·tamper 검증과 release 네 번째 gate strict semantic 결속
- [x] SFT mix의 완화 불가 assistant 민감 출력 선필터와 단일 디렉터리 원자 publish
- [x] 한국어 curriculum·Qwen·Gemma 세 upstream manifest의 직접 SHA 결속과 legacy fingerprint 보존
- [x] 공개 원행·teacher 파생행의 행별 provenance identity와 source overlap 0
- [x] 새 SFT의 미존재 run 디렉터리 원자 선점과 strict resume 전용 기존 run 재사용
- [x] SFT 연속 token cache의 2-pass 값 결속·offset 포함 128 MiB 상한·preflight 통계
- [x] 동일 SFT optimizer step의 best·주기·final checkpoint 요청 단일 저장
- [x] 9개 범주 보정 curriculum의 모든 user turn suite 비누출·target-token 질량·원자 publish
- [x] `src/llmex` 57개 모듈 전수 지도, 환경별 제작 워크북, 학습 평가 rubric과 교재 제작 메타데이터
- [x] focused-v2 300-step SFT와 best 100개 heldout·고정 162응답 자동 품질 재유도
- [x] focused-v3 잔여 7개 범주 train 4,350/heldout 435행과 suite·split·source overlap 0 재검증
- [x] focused-v3 200-step SFT와 step 25·200 고정 162응답 품질 비교·byte 재유도
- [x] focused-v4 보존 replay·네 일반화 범주 train 7,200/heldout 720행 비누출 검증
- [x] focused-v4 50-step SFT와 step 10·50 고정 162응답 비교·step 50 byte 재유도
- [x] focused-v5 비누출 접미 counterexample train 7,200/heldout 720행 생성·재검증
- [x] focused-v5 50-step SFT와 step 30·50 고정 162응답 평가·step 50 byte 재유도
- [x] 57개 모듈 교재의 챕터별 환경표와 offline mix→SFT→추론→품질 실행 실습
- [x] focused-v6 핵심 앞부분 보존 train 9,200/heldout 920행과 모든 overlap 0 재검증
- [x] focused-v6 40-step SFT와 step 20·40 고정 162응답 평가·byte 재유도
- [x] focused-v7 exact 문맥·PII 거절 train 8,400/heldout 840행과 overlap 0
- [x] focused-v7 20-step SFT와 step 5·10·20 고정 162응답 평가·byte 재유도
- [x] focused-v8 값-only 일반화 train 8,400/heldout 840행과 overlap 0
- [x] focused-v8 20-step SFT와 step 5·20 진단 평가·byte 재유도
- [x] 학습·생성 BOS/EOS/줄바꿈 경계 일치와 v7 step 10·20 품질 재유도
- [x] focused-v9 PII·정상 안전 train 10,800/heldout 1,080행과 overlap 0
- [x] focused-v9 10-step SFT와 step 2 고정 162응답 자동 gate·byte 재유도
- [x] focused-v10 일반 대화·불확실성 train 10,800/heldout 1,080행과 overlap 0
- [x] 실제 생성 CLI의 품질 평가 동등 decoding 옵션과 고정 seed 재현
- [x] focused-v11 대화·안전 동시 보정 train 13,200/heldout 1,320행과 overlap 0
- [x] focused-v11 150-step SFT와 step 25·50 고정 162응답 평가·byte 재유도
- [x] 기본 loopback 유지와 명시적 신뢰 내부망 teacher hostname allowlist
- [x] OpenAI 호환 빈 `tool_calls` 수용과 실제 tool call 실패-폐쇄
- [x] 실제 trailing newline 이력의 학습·생성 prefix 토큰 완전 일치
- [x] v11 저학습률·v10→v9 안전 복원 trial 재현 설정과 기각 근거 기록
- [x] 18 scenario·20 turn·120응답 한국어 대화 준비도 suite와 학습·inventory overlap 0
- [x] capability curriculum manifest의 최종 SFT source SHA·출력·tokenizer·길이·release 결속
- [x] v11 step 50 한국어 대화 준비도 120응답 생성·byte 재유도·실패 기준선 기록
- [x] 빈 내부망 allowlist의 기존 loopback 증류 fingerprint 호환과 Qwen 10k 재검증
- [x] 기존 품질·대화 준비도 42 scenario·47 turn을 한 curriculum SHA에 결속
- [x] macmini Gemma 4 2,200건 수집·1,656행 export·byte 재유도 검증
- [x] Qwen/public+Gemma mix와 생성/replay 교차 prompt 제외 curriculum 검증
- [x] 두 teacher용 다국어 2,160 prompt inventory와 108응답 품질 suite
- [x] SHA 고정 private HF Llama export와 artifact·release policy 검증
- [x] 공식 llama.cpp converter 기반 F16 GGUF와 Transformers/llama.cpp 실제 parity
- [x] 100M latest 기반 600-step Qwen·Gemma 다국어 혼합 SFT 완료
- [x] 60 scenario·65 turn·390응답 한국어·다국어 통합 suite와 byte 결속 회귀
- [x] step 300·600 전체 품질 재유도와 실패 checkpoint 배포 차단
- [x] focused-v12 범주별 quota와 다중 replay 원천·license·category 결속
- [x] train 4,000·heldout 400행 byte 재유도와 suite·split·source overlap 0
- [x] step 600 기반 LR 2e-6/4e-6 25-step A/B 설정 preflight
- [x] 두 A/B 25-step 학습·checkpoint SHA 고정·390응답 byte 재유도
- [x] unsafe 0·EOS 100%의 LR 4e-6 선택과 A/B checkpoint 배포 차단
- [x] 원 step 600에서 새로 시작하는 최대 150-step 정식 설정
- [x] focused-v12 150-step 학습과 25-step별 validation·checkpoint
- [x] step 50·150 각 390응답 byte 재유도와 실패 판정
- [x] suite 밖 한국어·영어·일본어 자유대화 smoke와 비문 checkpoint 기각
- [x] 한국어 자연대화 10,000·Qwen/Gemma 다국어 각 6,000 고유 prompt와 endpoint preflight
- [x] 결함 있는 expanded 1차 tranche를 부분 수집 상태에서 중단하고 export·학습 사용 차단
- [x] Reference/serial·부자연스러운 조사·큰 수치와 split·teacher 의미 중복 제거
- [x] `prompt_index` 기반 의미 조합 범위 분리와 natural-v3/v2 SHA·fingerprint 고정
- [x] natural 2,000/2,000/3,000 inventory의 고유 request·Wikipedia 0·overlap 0·endpoint preflight
- [x] Qwen 261건·Gemma 한국어 251건 teacher label 독립 감사 실패와 collector 중단·미export
- [x] typed response contract 보존과 목표 언어·숫자·이름·용어·writing·uncertainty metadata-v1 gate
- [x] task/category 균등 최대 50개 표본 승인 artifact와 inventory·accepted spool 강결속 export gate
- [x] 과거 spool 역감사에서 Qwen 192/261·Gemma 50/251 품질 거절 재현
- [ ] Qwen 다국어 v2·Gemma 한국어 v3 collect·export·validate와 새 teacher mix
- [ ] 100M latest SFT·390응답·suite 밖 smoke 통과 checkpoint 선별
- [ ] step 50 profile/seed 최악 정확도 88.89%를 90% 이상으로 보정
- [ ] suite 밖 자연스러운 인사와 실시간 조회 불가 자유대화 smoke

## 외부 승인 없이는 통과 불가

- [ ] 법무 검토: Wikipedia 귀속, 문서별 고지, 생성 가중치와 배포 조건
- [ ] 장기 baseline: 전체 dump, 사람 감사, pilot, 장기 학습, best/final 안전 평가
- [ ] 수동 대화 품질 실행: 실제 학습 모델 blind sample, 독립 quality·safety 검토와 필요 adjudication
- [ ] 공개 배포 결정: 승인된 대상·채널·버전·철회 책임자

네 항목은 승인자, ISO 8601 시각, 근거 artifact를 가진 JSON과 각 품질·`release gate`가 필요하다. 현재 판정은
**1.22.22 source 결속 teacher 응답 품질 gate·conversation act·번역 동의어/활용형 계약·로컬 HF/GGUF export·통합 자동 품질 suite·자유대화 smoke·독립 수동 검토**다. natural-v5는 과거 계약과 source SHA를 보존하고 새 profile에서만 영어·한국어 동사 활용, 보수적 장소 동의어와 ASCII 단어 경계를 허용한다. 이름 훼손·물체 오역·언어 혼입은 계속 실패-폐쇄하며 Qwen/Gemma v4 inventory는 prepare와 endpoint preflight를 통과했다. Hugging Face에는 공개·비공개 모두 업로드하지 않는다.

release gate의 필수 집합은 법무, 장기 baseline, 수동 품질 평가, 공개 배포 결정 네 개다. 수동 품질 manifest/report는 exact key, canonical fingerprint, report SHA, 최소 표본, 모든 점수와 worst 값, reviewer/submission/adjudication 교차 의미, release version·commit·config target을 검증한다. 네 gate는 한 invocation에서 한 번 snapshot한 Git commit·서명 trust policy·issuer map으로 검증한다. production `.llmex/trust-policy.json`에는 `quality-release`, `quality-reviewer`, `safety-reviewer`, `quality-adjudicator` 역할이 아직 없으며 고정 root private key 없이 policy를 수정하지 않는다.

## 1.4.0 차단 수정 검증

- [x] external stage별 실행 직전 nonce 생성과 환경 계약 전달
- [x] 사후 telemetry subject의 nonce/run-id/stage/예산/commit/config fingerprint 결속
- [x] stage 시작 이후 발급 및 현재 만료 유효성 검증
- [x] 서로 다른 유효 과거 telemetry replay 거부
- [x] 후속 stage 뒤 digest·서명·subject·예산 최종 재검증과 TOCTOU 거부

## 1.3.0 보호 gate 추가 검증

- 승인 bundle은 pinned root가 서명한 HEAD policy와 policy의 issuer Ed25519 공개키로 검증한다.
- 각 gate는 서로 다른 승인자, UTC RFC3339 발급·만료, evidence 파일 SHA-256, 버전·Git commit·config fingerprint를 요구한다.
- wheel/sdist digest는 artifact manifest와 provenance subject가 일치해야 하며 SBOM은 wheel METADATA의 runtime dependency만 기술한다.
- canary provenance가 없거나 에너지/token telemetry를 검증할 수 없는 외부 실행은 통과가 아니라 대기/실패다.
- external stage는 실행 전 final telemetry를 재사용하지 않고 종료 후 새로 생성된 final 진술의 stage/run-id/예산 결속과 최종 사용량을 권위 있게 재검증한다.

## 1.3.0 권위 있는 승인 입력

`release gate`에는 approval 파일 위치와 독립적인 `--repository-root`를 명시한다. Git root/HEAD 확인
실패, 빈 값, abbreviated/noncanonical commit은 거부한다. 네 gate의 role/kind는 각각
`legal/legal-approval`, `baseline/baseline-evidence`, `quality-release/manual-quality-gate-approval`, `release/release-approval`과 정확히 일치해야 한다.
정책은 HEAD에 봉인된 `.llmex/trust-policy.json`만 사용하며 로컬 self-signed 결과는 공개 권한이 없다.
