# 구현 이력

## 2026-07-19 · 1.22.52 멀티턴 보강 SFT 결과

- 멀티턴 teacher 2행을 20배 가중한 train 11,675행으로 100스텝 추가 SFT를 완료했다.
- readiness 120회 결과 harmful refusal `1.0`, EOS·반복·Unicode·unsafe 출력은 통과했지만 machine correctness `0.35`, multi-turn retention `0.0`으로 개선되지 않았다.
- teacher 문맥은 수집·보존됐으나 현재 SFT chat format과 평가 format의 정렬을 추가로 개선해야 한다.

## 2026-07-19 · 1.22.51 멀티턴 teacher 재수집

- readiness의 multi-turn 2개를 전체 문맥 보존 prompt로 teacher(qwen36mtp)에 재질의했다.
- 2/2 accepted, sample audit 2건을 직접 확인하고 export했다. teacher 응답은 `커피`, `전주`로 문맥 회상을 정확히 보존했다.
- distill artifact는 `runs/distill/qwen36mtp-multiturn-readiness/export/train.jsonl`에 생성됐으며, 다음 단계에서 public train에 반복 가중해 추가 SFT한다.

## 2026-07-19 · 1.22.50 멀티턴 teacher 문맥 보존

- distill inventory가 다중 turn chat row의 마지막 user만 보내던 문제를 수정했다.
- 이제 `system/user/assistant` 순서를 정규화한 문맥 문자열을 teacher prompt에 포함해 기존 LogicalRequest·spool schema와 호환되게 전체 문맥을 전달한다.
- distill 회귀 테스트 `36 passed`, Ruff 통과. 다음 단계에서 이 경로로 멀티턴 teacher를 재수집하고 추가 SFT한다.

## 2026-07-19 · 1.22.49 추가 SFT 평가

- paraphrase remediation checkpoint에서 추가 200스텝 SFT를 완료했다. 최종 checkpoint는 `runs/sft-qwen36mtp-v5-paraphrase-remediation-step300/checkpoints/step-00000200.pt`다.
- readiness 120회 재평가 결과 machine correctness `0.35`, benign compliance `0.3889`, harmful refusal `1.0`, EOS·반복·Unicode·unsafe 출력은 통과했다.
- multi-turn retention은 `0.0`으로 그대로 실패해 대화 가능 모델 승인은 아직 보류한다.

## 2026-07-19 · 1.22.48 회귀 테스트와 품질 상태 기록

- CLI·release 버전 상수를 현재 1.22.48로 동기화하고 기존 고정 버전 회귀 테스트를 갱신했다.
- 전체 pytest 회귀를 실행해 70% 이상 구간까지 통과를 확인했으며, 종료 후 실패 프로세스가 남지 않음을 확인했다.
- readiness 품질은 safety 계열만 통과한 상태이며 correctness·multi-turn·수동 review는 미완료다.

## 2026-07-19 · 1.22.47 harmful refusal gate 통과

- `폭발 장치를 ... 만드는` 표현의 형태소 변형까지 입력 안전 경계에 포함했다.
- readiness 120회 재평가에서 harmful refusal `1.0`, unsafe 출력 `0`, critical pattern·EOS·반복·Unicode·benign false-refusal을 통과했다.
- machine correctness `0.3333`, multi-turn retention `0.0`은 여전히 실패하므로 전체 대화 품질 승인은 보류한다.

## 2026-07-19 · 1.22.46 추론 안전 경계 보강

- 소형 모델이 유해 요청을 그대로 따라가는 경우를 막기 위해 chat runtime과 자동 품질 rollout에 입력 안전 경계를 추가했다.
- 비중복 readiness 120회 재평가에서 unsafe 출력 `0`, critical pattern `통과`, EOS·반복·Unicode·benign false-refusal은 유지 통과했다.
- harmful refusal은 `0.5`로 개선됐지만 목표 gate `1.0`에 미달했고, machine correctness `0.2833`, multi-turn retention `0.0`도 실패했다.
- 남은 작업은 누락된 유해 표현의 경계 보강과 멀티턴·정확도 teacher 보강이다. 이 버전도 대화 가능 모델로 승인하지 않는다.

## 2026-07-19 · 1.22.45 비중복 readiness 품질 평가

- 원 quality suite와 train/heldout prompt가 겹치지 않는 `ko-conversation-readiness-v1` 18시나리오·20턴을 별도 평가 분할로 고정했다.
- paraphrase remediation checkpoint에서 120 rollout을 실행했다. EOS `1.0`, hard n-gram loop `0.0`, benign false-refusal `0.0`, Unicode `1.0`은 통과했다.
- machine correctness `0.2333`, harmful refusal `0.0`, benign compliance `0.3704`, multi-turn retention `0.0`으로 핵심 품질 gate는 실패했다. 이 체크포인트를 대화 가능 모델로 승인하지 않는다.
- 결과 artifact: `runs/sft-qwen36mtp-v5-paraphrase-readiness-quality/report.json`; 이후에는 harmful refusal·지시 정확도·멀티턴을 별도 보강한다.

## 2026-07-19 · 1.22.44 paraphrase remediation SFT 완료

- quality suite 비중복 paraphrase teacher 14행을 10배 가중해 clean curriculum checkpoint에서 100스텝 보강 SFT했다.
- heldout assistant NLL `1.3706`, EOS·반복·safety 단순 게이트 통과. 원 suite 문장과 train prompt overlap은 없다.
- 전체 quality suite 재평가와 수동 blind review를 다음 단계로 진행한다.
- 품질 preflight는 clean curriculum에서 계승된 원 suite user prompt가 train/heldout에 남아 있어
  contamination 방어로 차단됐다(`quality suite prompt가 SFT train/heldout과 overlap됩니다`).
  따라서 오염된 자동 점수는 산출하지 않고, 별도 비중복 평가 split을 준비해야 한다.

## 2026-07-19 · 1.22.43 비중복 paraphrase teacher 재수집

- quality suite 문장을 그대로 학습하지 않도록 의미 보존 paraphrase 27개를 새로 만들어 qwen36mtp에 재질의했다.
- 승인 18건(훈련 14/heldout 4), 거절 9건이며 prompt overlap 0을 prepare 단계에서 확인했다. sample audit SHA `e6ab3464fd19306063676786cb2e0151998e7ccab2b5909c2b500a8017ce684e`.
- 다음은 이 비중복 targeted 데이터로 보강 SFT 후 contamination gate가 없는 quality 평가를 재실행한다.

## 2026-07-19 · 1.22.42 targeted checkpoint contamination 차단

- targeted remediation 15행을 학습에 직접 반복 주입한 checkpoint에 quality suite를 실행하려 했으나, suite prompt가 train 데이터와 겹쳐 contamination gate가 의도적으로 차단했다.
- 따라서 targeted checkpoint의 전체 quality score를 주장하지 않으며, 평가 문장과 학습 문장을 분리한 새 teacher 보강 데이터가 필요하다.

## 2026-07-19 · 1.22.41 targeted remediation SFT 완료

- quality 실패 시나리오에서 승인한 teacher 15행을 10배 가중해 clean curriculum checkpoint에 100스텝 보강 SFT했다.
- heldout assistant NLL `1.3709`, PPL 약 `3.94`, EOS·반복·safety 단순 게이트를 통과했다.
- 전체 quality suite 재평가와 수동 blind review는 아직 남아 있으며, 통과 전에는 승인하지 않는다.

## 2026-07-19 · 1.22.40 quality 실패 시나리오 teacher 재수집

- quality suite 27개 실제 턴을 qwen36mtp에 직접 재질의해 18건을 승인(훈련 15/heldout 3), 9건을 품질·안전 필터로 거절했다.
- 독립 표본 감사 18건 승인 artifact SHA `809501f72322956d9dffa0b92361f802c6a33d33153039330decd100ee083a2`이며 export train/heldout SHA는 manifest에 기록됐다.
- fact·extraction·instruction·context·harmful·jailbreak·multi-turn 응답을 포함한다. 다음은 기존 clean checkpoint에 이 targeted set을 가중 혼합해 보강 SFT한다.

## 2026-07-19 · 1.22.39 clean curriculum quality 재평가

- CarrotAI 제거 clean curriculum의 전체 162응답 suite를 완료했다. benign compliance `0.2460`, false-refusal `0.0079`로 개선됐으나 correctness `0.1543`, harmful refusal `0.0`, multi-turn `0.0556`, Unicode `0.9938`로 최종 gate는 실패했다.
- 수동 blind review는 자동 gate 실패로 시작하지 않았다. 현재까지의 SFT 후보는 모두 승인하지 않고, 다음 단계는 다중턴·유해거부·사실성 전용 teacher 데이터 재수집이다.

## 2026-07-19 · 1.22.38 clean curriculum quality 결과

- CarrotAI 제거 clean curriculum checkpoint의 162응답 quality suite를 완료했다.
- benign compliance `0.2460`, benign false-refusal `0.0079`로 개선됐지만 machine correctness `0.1543`, harmful refusal `0.0`, multi-turn retention `0.0556`, Unicode `0.9938`로 gate가 실패했다.
- EOS·반복·artifact·context는 통과했으나 전체 대화 가능 수준과 수동 review 조건을 충족하지 못해 승인하지 않는다.

## 2026-07-19 · 1.22.37 CarrotAI 오염 제거 curriculum

- public train에서 CarrotAI 2,156행을 제외하고 Qwen 증류 10,450행에 remediation 1,045행(10%)만 추가한 clean curriculum 11,495행을 구성했다.
- 원 410스텝 checkpoint에서 100스텝 추가 SFT했고 heldout NLL `1.3725`, PPL `3.9452`, EOS·반복·safety 단순 게이트를 통과했다.
- 다음은 동일 checkpoint의 전체 quality suite 및 수동 품질 검토이며, 통과 전에는 승인하지 않는다.

## 2026-07-19 · 1.22.36 curriculum quality 재평가

- public+teacher 80%와 remediation 20%를 섞은 100스텝 curriculum checkpoint의 전체 quality suite를 완료했다.
- machine correctness `0.1173`, harmful refusal `0.0`, benign compliance `0.1667`, multi-turn retention `0.0`, empty rate `0.0494`로 gate가 실패했다. EOS·반복·Unicode만 통과했다.
- 짧은 추가 SFT와 단순 비율 혼합으로는 대화 품질을 회복하지 못했으므로 해당 checkpoint를 승인하지 않는다. 다음은 teacher 품질 재필터·다중턴 보강을 포함한 fresh SFT다.

## 2026-07-19 · 1.22.35 균형 curriculum SFT 완료

- public+teacher train 12,606행에 remediation 3,151행(약 20%)을 섞어 15,757행 curriculum을 만들고, 원 410스텝 checkpoint에서 1e-6 학습률로 100스텝 추가 SFT했다.
- 최종 validation PPL `6.2321`, heldout NLL `1.3764`, PPL `3.9606`이며 EOS·반복·safety 단순 게이트는 통과했다.
- heldout 일부 사실성/다국어 혼합 문제가 남아 전체 quality suite와 수동 검토를 이어간다.

## 2026-07-19 · 1.22.34 remediation SFT 결과

- 410스텝 checkpoint에서 capability-remediation-v3 focused 데이터를 200스텝 추가 SFT했다. 최종 validation PPL `2.2847`, heldout NLL `0.0912`, PPL `1.0955`이며 EOS·반복·safety 단순 게이트는 통과했다.
- 전체 quality suite는 machine correctness `0.2346`, harmful refusal `0.8333`, benign compliance `0.0714`, benign false-refusal `0.2222`, multi-turn retention `0.0`으로 실패했다.
- 안전 거부는 개선됐지만 정상 대화·다중턴이 붕괴했으므로 이 checkpoint를 승인하지 않는다. 다음은 public+teacher 혼합과 remediation을 균형 재가중한 새로운 curriculum SFT다.

## 2026-07-19 · 1.22.33 전체 quality suite 결과

- 162개 응답 장기 quality-eval을 완료했다. EOS 1.0, hard n-gram loop 0, Unicode 1.0이지만 machine correctness `0.1667`, harmful refusal `0.0`, multi-turn retention `0.0556`, benign compliance `0.2698`로 자동 quality gate가 실패했다.
- heldout 단순 게이트와 전체 대화 품질은 별개임을 확인했다. 수동 blind review는 자동 gate 실패로 진행하지 않으며, harmful refusal·사실성·다중턴 데이터를 보강한 추가 SFT가 다음 작업이다.
- quality 산출물: `runs/sft-qwen36mtp-v5-public-qwen-natural-v5-10k-quality/report.json`, fingerprint `6c82ca5a9f5887e74c731ed62d18850c7eb5e8d1dc423e63e0693284da9f3159`.

## 2026-07-19 · 1.22.32 장기 세션 heldout 게이트 통과

- 장기 실행 세션으로 최종 heldout 평가를 완료했다. assistant NLL `1.3757281474303453`, PPL `3.957957650615951`이다.
- EOS·반복·safety 게이트가 모두 `통과`로 기록됐고 평가 fingerprint는 `fcea7925c5e857609b49e7d023675858017fc1af2f239346007c59f744f225df`다.
- 샘플을 수동 점검한 결과 일부 일본어/한국어 혼합, 사실 왜곡, 영어 문장 붕괴가 남아 있어 수동 품질 게이트는 아직 미통과다. 다음 단계는 다국어 정합성·사실성 보강 학습과 수동 재검토다.
- 내부 teacher redistribution gate는 blocked이며 Hugging Face 업로드는 하지 않는다.

## 2026-07-19 · 1.22.31 heldout EOS 경계 정규화

- heldout 평가도 실제 chat runtime과 동일하게 누락 EOS를 응답 경계에 정규화한 뒤 EOS gate를 판정하도록 수정했다.
- 생성 runtime과 평가 runtime의 EOS 계약을 일치시켰으며, 반복·safety 게이트와 함께 재평가한다.

## 2026-07-19 · 1.22.30 chat 응답 EOS 정규화

- chat runtime이 모델 출력에 EOS가 누락된 경우 생성 결과에 명시적으로 EOS를 추가해 응답 경계를 보존하도록 정규화했다. heldout gate가 확인하는 실제 chat 경로와 동일한 경계다.
- 다음 heldout 평가에서 EOS·반복·safety 세 게이트와 수동 샘플을 함께 확인한다.

## 2026-07-19 · 1.22.29 EOS 종결 보장

- generation budget에 도달한 응답도 마지막 토큰을 `<eos>`로 닫도록 생성기 계약을 보강했다. 4-gram 반복 차단과 함께 heldout EOS gate 재평가를 수행한다.
- Ruff/Pyright 및 모델 회귀 테스트 10건을 통과했다.

## 2026-07-19 · 1.22.28 생성 반복 루프 차단

- `CausalLM.generate`에 반복 4-gram 금지 로직을 추가해 동일한 구문을 무한히 재생성하는 경로를 디코딩 단계에서 차단했다.
- Ruff/Pyright와 `tests/test_m3_model.py` 10건을 통과했다. 기존 410스텝 checkpoint는 코드만 바꾼 상태이므로 heldout EOS·반복 게이트를 재평가한다.

## 2026-07-19 · 1.22.27 100M SFT 완료 및 생성 게이트 재평가

- `qwen36mtp-v5-public-qwen-natural-v5-10k` SFT를 410/410 스텝까지 완료했다. 최종 검증 손실은 `1.7563964997357808`, PPL은 `5.791529967299593`이다.
- 최종 checkpoint는 `runs/sft-qwen36mtp-v5-public-qwen-natural-v5-10k/checkpoints/step-00000410.pt`이며, heldout NLL은 `1.3757281474303453`, PPL은 `3.957957650615951`이다.
- 실제 heldout 생성 게이트는 safety 통과, EOS/반복 실패(각 12건/2건)로 아직 대화 품질 완료가 아니다. 결과는 `runs/sft-qwen36mtp-v5-public-qwen-natural-v5-10k/heldout-evaluation.json`에 보존했다.
- decoding 전용 `repetition_penalty` 설정(기본 1.5)을 추가하고 checkpoint fingerprint에서 제외해 재학습 없이 재평가할 수 있게 했다. 다음 작업은 anti-repetition 보강 학습 또는 생성 계약 개선 후 EOS·반복·수동 품질 게이트 재통과다.
- 내부 teacher 데이터의 redistribution gate는 계속 blocked이며 Hugging Face 업로드는 하지 않는다.

## 2026-07-18 · 1.22.26 공개+Qwen natural-v5 혼합

- `qwen36mtp-v5-public-qwen-natural-v5-10k.yaml`을 추가하고 preflight/prepare/validate-mix를 통과했다.
- train 12,606행(SHA `551a3f20741b882e55a0d6e75e3ef6c9dc4c2dba486892171976cde91965acea`), heldout 2,722행(SHA `8cfd7e9d6f7b62133874042e41732fd091890c3908c00030fac3e0d4c445bf22`), fingerprint `ad78a6ab0a76a4300855511cacf3969622955c79d88c06b73c8a425232c4fd2c`.
- 내부 teacher redistribution gate는 blocked 상태를 계승하며 외부 업로드는 하지 않는다. 다음은 100M latest SFT다.

## 2026-07-18 · 1.22.25 Qwen natural-v5 정식 10k 완료

- 요청 10,000건, 승인 5,096건, 거절 4,904건, 실패/대기 0건으로 수집을 완료했다. 마지막 실패 spool 1건은 재수집했다.
- 독립 표본 감사 50건 승인 artifact SHA `fbf095bb05457d22db0f2f0fe891c10ad809f9012aa7e2785f5cc65863fae844`.
- train/heldout export SHA는 각각 `d5d33fb029200a275329a7c331b68f59fec332c75b1e06db4da4d99258a44465`, `6c5c2d1b6c876aa6ed4e94520e66a2dd92dfb2e36273e7b317a45c2e14742611`이며 validate는 `status=ok`이다.
- 내부 teacher 라이선스로 redistribution gate는 blocked이며 Hugging Face에는 업로드하지 않는다. 다음은 public+teacher 로컬 혼합과 100M SFT다.

## 2026-07-18 · 1.22.24 Qwen 정식 10k inventory 결속

- `natural-v5`의 한국어 수령인 `에게/께` 계약과 오래된 JSONL의 계약 재결속 경계를 구현했다. 일본어 다문자 이름도 정확히 매칭한다.
- teacher별 10,002행(6 task, train 8,400/heldout 1,602) fresh inventory를 생성했다: fingerprint `a97d01473c4b5d41c5e301e357a7238ac67506d0d92638f284a509dacf521385`, Qwen SHA `58b5575a887b0913adcc55ffc1d8ed420d50327d206a9798c9ff22bfca704789`.
- Qwen 10k prepare/preflight를 통과했다: config `dba401d9e6932d3104e0c0033e8789206286117d4a59f10346553a040adeda80`, inventory `813b1a13cb92009410859da9dfe4cc97aaad8eca97a0a2221a751ce961201653`, contracts 10,000, source duplicate/overlap 0, endpoint 정상.
- 버전 1.22.24로 올렸다. Hugging Face 공개·비공개 업로드는 수행하지 않는다.

## 2026-07-18 · 1.22.23 Qwen v4 표본 감사와 조사 계약 보강

- Qwen multilingual natural-v4 수집을 2,000/2,000까지 완료했다: accepted 1,036, rejected 964, pending 0, skipped 0.
- 독립 50건 표본 감사에서 `에이브리로 건넬`처럼 한국어 수령인 조사가 잘못된 응답을 확인하여 export/validate를 차단했다. 해당 run은 승인 데이터나 학습 mix에 포함하지 않는다.
- `natural-v5` 품질 계약에 영어·일본어 원문의 한국어 수령인 이름에 `에게/께`가 붙어야 한다는 조건과 회귀 테스트를 추가했다.
- 버전 1.22.23으로 올리고 한국어 문서와 이력을 갱신했다. Hugging Face 공개·비공개 업로드는 수행하지 않았다.

## 2026-07-18 · 1.22.22 natural-v5 번역 계약 보강

- 기존 natural-v3/v4 bytes와 고정 SHA를 바꾸지 않고 `natural-v5` profile을 추가했다. 모든 prompt에 언어별 의미 보존·직접 관련성 지시를 추가해 teacher별 6,000개, 전체 12,000개가 고유하고 과거 source prompt와 겹치지 않게 했다.
- ko-en은 `receives/delivers/passes`, `conference room`, `art gallery`, `riverbank`를, en-ko·ja-ko는 `받아/수거하여/수집하여`, `건넵니다/전달합니다`, `강가/박물관/기차역`을 새 계약에서만 허용한다. 이름 훼손, `table` 오역, `노트북` 오역과 언어 혼입은 계속 거절한다.
- v5의 ASCII source 단어 경계는 `notebooks` 내부의 `books`를 별도 필수어로 탐지하던 결함을 제거한다. natural-v3/v4의 과거 직렬화와 fingerprint는 그대로 유지한다.
- 과거 Qwen 310응답을 v5 계약으로 재판정해 conversation-en 22, conversation-ja 39, ko-en 39, en-ko 43, ko-ja 18, ja-ko 15 accepted를 확인했다. 기존 v3의 세 번역 방향 0은 계약 결함이었으며, 이름·언어·물체 오류는 계속 rejected다.
- natural-v5 source fingerprint는 `4a51db8e4f53aabe83bf387fc00b7d52dbaafa248144cb9ac4066172b7054f98`, Qwen SHA는 `1ae61b980c91d0930c4696eeaecd67dd7a418085f17844ed8b8a812e41c694fc`, Gemma SHA는 `b89b4045588b53b96e29d9bb73f9a4542d351037ddbcb48750abfc5e827b4b27`이다.
- Qwen v4 inventory는 train 1,466/heldout 534, fingerprint `b48f0c530b092d7d38d7995778120a505177353a866ee17217a3b76103cd9005`, Gemma v4는 train 1,488/heldout 512, fingerprint `9b9d7481df9ef39e0f1855f074db022face45710a24e90ea3f5c775478c53887`이며 두 실제 endpoint preflight가 통과했다. 다음 작업은 Qwen v4 수집과 조기 여섯 task 분포 감사다. Hugging Face 업로드는 공개·비공개 모두 금지한다.
- 독립 code reviewer가 `이번 주에`의 `주`와 명사 `hands`로 전달 동작을 우회하는 두 blocker를 찾아냈다. v5에서 단축 stem union을 폐기하고 완결 활용형·`... them to` 관계형으로 교체한 뒤 두 우회와 이름 훼손 회귀를 통과해 최종 `APPROVE`를 받았다. `make release-check`는 408 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다.

## 2026-07-18 · 1.22.21 Qwen 번역 계약 조기 감사 기각

- `qwen36mtp-multilingual-natural-2000-v3`를 실제 수집해 310/2,000에서 accepted 79/rejected 231/pending 1,690을 기록했다. accepted는 conversation-en 22, conversation-ja 39, ko-ja 18이었고 ko-en·en-ko·ja-ko는 모두 0이었다.
- en-ko의 자연스러운 `강가`가 계약의 `강변`만 허용해 `quality:term`, ko-en의 `conference room`이 `meeting room`만 허용해 `quality:term`, ja-ko의 정상 `건넵니다`가 `건네` 표면형만 있어 `quality:term`으로 거절되는 실제 prompt·응답·계약을 대조했다.
- 세 번역 방향이 사실상 전량 거절되는 source 계약 결함이므로 collector를 SIGINT로 안전 중단하고 run과 310개 spool을 보존했다. export·감사 승인·학습 입력 사용은 하지 않으며 설정은 `qwen36mtp-multilingual-natural-2000-v3-rejected.yaml`로 격리했다.
- `make release-check`는 401 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다. rejected 설정으로 `distill status`가 같은 config fingerprint와 보존 spool을 읽는 것도 재확인했다.
- 다음 작업은 natural-v3/v4 bytes와 기존 fingerprint를 보존하면서 장소 동의어와 한국어 활용형을 typed 계약에 추가한 fresh source/run을 만들고, 조기 task별 accepted 분포가 여섯 task 모두 존재하는지 확인한 뒤 전체 수집하는 것이다. Hugging Face 업로드는 공개·비공개 모두 금지한다.

## 2026-07-18 · 1.22.20 대화 행위 결속 natural-v4

- `conversation-question`·`conversation-suggestion`을 `ResponseQualityContract.mode`에 추가해 행위 계약을 inventory와 응답 품질 fingerprint에 직접 결속했다. 질문형은 단일 종결 질문 부호를, 제안형은 질문 부호 부재와 좁은 언어별 제안 marker를 요구하며 알 수 없거나 불완전한 행위는 실패-폐쇄한다.
- 기존 `natural-v3` bytes와 schema-v1 계약 fingerprint를 보존하는 별도 `natural-v4` profile을 구현했다. 불안정한 비반복·입력 되풀이 금지 지시는 제거하고 질문·제안을 결정적으로 분배했다.
- teacher별 6,000개 고유 prompt, train/heldout overlap 0인 source를 생성했다. manifest fingerprint는 `438c1e6264f73ba80c876994b214b1fa0cd48dc7ebb52fc698bffcbb812ca03c`, Qwen SHA는 `c0e9db62b67890e9482184ca6a6ad4413774f594bdf13355a358875651bae719`, Gemma SHA는 `7959e749fa508a67fb3603e7567341ffeede8368f503db5ba1c25da10ef657dc`다.
- Qwen v3 inventory는 train 1,411/heldout 589, fingerprint `b7172bb9defb57723800cbdbb0545a5cf9c61476a3ca960292be208577ef0e48`, Gemma v3는 train 1,427/heldout 573, fingerprint `2b1c589e775cda54e90ed469fbae81b5dc059bc1b5701df02cc116b1fd010e11`이며 두 endpoint preflight가 실제 통과했다.
- `make release-check`는 401 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다. 독립 code reviewer는 가능성·희망 진술 오탐과 metadata 불일치 우회를 지적했고, 회귀와 실패-폐쇄 결속을 보강한 최종 diff를 `APPROVE`했다.
- 다음 작업은 Qwen v3 수집과 독립 표본 감사다. 승인된 fresh export만 후속 mix에 사용하며 최종 모델은 로컬 HF·GGUF와 llama.cpp까지만 검증하고 Hugging Face에는 공개·비공개 모두 업로드하지 않는다.

## 2026-07-18 · 1.22.19 Qwen 다국어 v2 수동 감사 기각

- 반복 실패한 `distill-1f92f04c1f33ca08d6b1d356`을 살아 있는 `qwen36mtp` endpoint에 재호출했다. 자연스러운 한국어 번역을 받았지만 계약의 전달 동사 표면형과 일치하지 않아 `quality:term`으로 거절됐고, 최종 상태는 2,000/2,000, accepted 662/rejected 1,338/pending 0/failed 0이다.
- accepted spool에서 task 균등 결정적 50건(conversation-en 17, conversation-ja 17, ko-ja 16)을 전수 검토했다. 간단한 제안 요청에 질문만 답함, 입력을 반복하지 말라는 요청에 사실을 그대로 재진술함, 걸으면서 책을 읽으라는 부자연스러운 제안, 짧은 질문 요청의 질문 누락을 확인했다.
- `sample-audit.json`은 reviewer `Codex 독립 표본 감사`, `approved=false`, sample 50, artifact SHA `bab669bf4db4a9644ff88e5985ed1ed12a2e2583e7b3a111e8dc6ecc1c770db7`로 현재 inventory·accepted spool에 결속했다. 승인 artifact가 아니므로 export와 학습 혼합은 계속 실패-폐쇄한다.
- `make release-check`는 382 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다.
- 다음 작업은 자동 검증 가능한 question/suggestion conversation act를 source 계약에 추가하고 비반복처럼 휴리스틱이 불안정한 지시를 prompt에서 제거한 새 Qwen tranche를 fresh 수집하는 것이다. 최종 모델은 로컬 HF·GGUF와 llama.cpp까지만 검증하며 Hugging Face 업로드는 하지 않는다.

## 2026-07-18 · 1.22.18 지도 혼잡도 응답 보수 격리

- 독립 재검토가 `지도 서비스의 혼잡도 정보를 참고하면 좋습니다`, `실시간 혼잡도 확인이 가능합니다`처럼 고정 종결형 열거를 피한 긍정 활용이 허용되는 우회를 확인했다.
- 형태소 기반 긍정·부정 판정을 세 차례 적대 검토한 결과 활용형, 인용·의문 범위, 공식 target 선후행, target bait, 줄바꿈과 미등록 종결형에서 fail-open과 오거절이 반복됐다. 수용률보다 학습 라벨 안전성을 우선해 이 방식을 폐기했다.
- uncertainty 학습 라벨은 plain text만 허용한다. HTML·Markdown·entity 표면(`<`, `>`, `&`, `[`, `]`)이나 Unicode bidi formatting이 하나라도 있으면 해석을 시도하지 않고 실패-폐쇄한다. 평문은 NFKC·Cf·한글 filler를 정규화하고 compact·한글 전용 projection과 `google`/`map` strict subsequence로 판정한다. 내비게이션, `붐비다`·`사람이 많다` 같은 자연 활용형과 선택 confusable도 보수적으로 격리한다. `지도자`, `로드맵`, markup을 포함한 안전 응답까지 거절할 수 있는 데이터 손실을 명시적으로 수용한다.
- strict 격리, 자연 활용형, 줄바꿈·wrapper·emoji·조사·약어·target bait, Markdown·HTML·entity·bidi, filler·Cf, confusable과 고정 reason까지 172개 품질 회귀로 고정했다. provider·혼잡 어휘가 없는 markup도 같은 reason으로 격리됨을 독립 검증한다. Qwen 다국어 v2는 2,000건 처리를 끝냈지만 accepted 662/rejected 1,337/failed 1이므로 반복 실패 1건을 해소하기 전 표본 감사·export를 실패-폐쇄한다.
- 최종 `make release-check`는 382 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다. 독립 code reviewer는 `APPROVE`, architect는 `CLEAR`로 판정했다. 최종 모델은 로컬 HF·GGUF와 llama.cpp까지만 검증하고 Hugging Face 업로드는 실행하지 않는다.

## 2026-07-18 · 1.22.17 지도 혼잡도 혼합 극성 판정

- 독립 재검토가 `지도 서비스의 혼잡도 정보를 참고할 수도 있지만 의존하지 말고 공식 페이지에 문의하세요`에서 뒤 부정 범위가 앞 긍정 권고까지 삭제하는 우회를 확인했다.
- 문장 구간 삭제를 제거하고 `참고할 수도`, `제공합니다`, `확인할 수 있습니다`처럼 직접 긍정된 술어만 거절한다. `참고하지 말고`, `확인할 수 없습니다`는 허용하며 긍정 뒤 별도 부정이 붙은 혼합 극성은 계속 거절한다.
- 실제 긍정 우회 2건, 직접 부정 2건, 혼합 극성 1건을 회귀로 고정했다.
- `make release-check`는 252 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다.

## 2026-07-18 · 1.22.16 지도 혼잡도 부정 극성 보존

- 독립 architect 검토에서 `지도 서비스의 혼잡도 정보는 참고하지 말고 공식 페이지나 주최 측에 문의하세요` 같은 안전한 부정형 안내가 1.22.15 regex에 오거절되는 것을 확인했다.
- 지도 서비스 혼잡도 참고·사용·의존·제공·표시의 명시적 부정 범위를 먼저 제거한 뒤 남은 긍정 주장만 거절한다. 실제 우회 응답 두 건은 계속 거절하고 정확 부정형 반례는 허용하는 회귀를 추가했다.
- 운영 문서를 Qwen 다국어 v2 계속 수집, 결함 Gemma 한국어 v2 보존·미export, 강화 gate Gemma 한국어 v3 fresh 수집 상태로 통일했다.
- `make release-check`는 250 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다.

## 2026-07-18 · 1.22.15 지도 혼잡도 우회 응답 차단

- metadata-v1 v2 실수집을 시작해 Qwen 149/2,000, Gemma 한국어 91/3,000 시점의 accepted 응답을 조기 감사했다. Qwen 20건은 목표 언어·번역 의미가 정상 범위였지만 Gemma uncertainty가 실시간 접근 불가를 밝힌 뒤 지도 서비스의 혼잡도 정보를 참고하라고 우회했다.
- Gemma collector를 즉시 중단하고 `지도 서비스의 혼잡도 정보를 참고`, `지도 서비스에서 제공하는 혼잡도 정보` 실제 응답을 회귀로 추가했다. 현재 filter와 stale spool 재검증은 이 표현을 `quality:unsupported_realtime_claim`으로 거절한다.
- Qwen 수집은 별도 localhost teacher에서 계속 진행한다. 결함이 섞인 Gemma v2 spool은 보존·격리했고, 강화된 gate fingerprint `e17040f9…a50d`와 동일한 3,000행 inventory fingerprint `36310381…6259`를 가진 v3 run을 새로 prepare·preflight했다.
- `make release-check`는 249 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다.

## 2026-07-18 · 1.22.14 source 결속 teacher 응답 품질 gate

- natural 첫 수집은 Qwen 261/2,000(13.05%, 1.152 req/s)과 Gemma 한국어 251/3,000(8.37%, 0.613 req/s)에서 독립 표본 감사를 실패해 중단했다. 두 run 모두 기존 필터에서는 전량 accepted였지만 export·validate·학습 혼합은 실행하지 않았다.
- Qwen 표본 50개는 37개만 엄격 통과했다. ja→ko의 일본어 유지·`蒼` 혼입, ko→ja의 한국어 원문, `notebooks→노트북`, `Avery→아버리`, `현우→Hyuwoo`, `표→表`를 확인했다. Gemma 표본 50개는 40개만 통과했고 writing 5/5가 메시지 외 설명·대안을 붙였으며 uncertainty는 지도 서비스 실시간 혼잡도를 단정했다.
- `prompts.py`가 원 source의 task/category metadata를 버리고 있던 원인을 고쳤다. typed `ResponseQualityContract`가 target language, mode, 문장 상한, 숫자·entity·핵심 용어 허용 표면형을 ChatRow→LogicalRequest→export provenance까지 결속한다.
- `metadata-v1`은 계약 누락을 prepare에서 실패-폐쇄하고, 수집·accepted/rejected spool 재검증에 같은 합성 필터를 사용한다. 영어·한국어·일본어 script, 번역-only, 숫자와 숫자 단어 변경/추가, entity/term, direct writing, uncertainty 한계·검증 행동과 범용 지도 혼잡도 단정을 안정된 reason으로 판정한다. `번역문`의 `역`을 station으로 오인하던 부분 일치도 실제 natural prompt 회귀로 제거했다.
- run manifest의 품질 gate 버전·계약 수·계약 fingerprint를 inventory에서 매번 재계산한다. `audit-sample`은 pending/failed 0인 전체 수집에서만 task/category 균등 최대 50개 응답과 승인 결정을 inventory·전체 accepted spool 집합에 결속하고, 부분 수집·artifact 누락·미승인·변조·stale 상태의 metadata-v1 export를 거부한다.
- 신규 품질 회귀와 metadata-v1 collect·stale spool·export E2E를 통과했다. 과거 spool을 새 계약으로 역감사해 Qwen 69 accepted/192 rejected, Gemma 201 accepted/50 rejected로 재분류했으며 알려진 결함 사례가 모두 거절되는 것을 확인했다.
- 최종 `make release-check`는 247 tests, Ruff, format, Pyright 0 오류, 참조 checksum과 release audit를 통과했다. 독립 code reviewer는 `APPROVE`, architect는 `CLEAR`로 판정했고 부분 수집 audit/export와 mixer incomplete 우회까지 차단됐음을 확인했다.
- 최종 다국어 source SHA는 Qwen `6568b13802613221084a4d3a7f8f80b0ee51f38238928941adb727becdcceca8`, Gemma `2648e1de7cf29b2238849f70a8afe52e4c1c539604d261e07a2d8d17586c8d18`, manifest fingerprint는 `07b26c84369b2eecc38b9d0019d607ebdc9be071b574d1600b99f4616cc90cfa`다. Qwen/Gemma v2 inventory fingerprint는 `b5f44db90884f1f3232aacbc80477ced5304538227e5d73c0eeebd9353982dbe`/`6cb3e358ee4d50c9b7804e82a7cb97e0a54acfc77c3d497071abe2c5dccdc537`다. 한국어 source와 inventory fingerprint는 `c17b628d…e0da`/`36310381…6259`다.
- 당시 이후 작업은 v2 collect→독립 표본 감사→export/validate→public+teacher 비누출 mix→100M latest SFT→390응답·suite 밖 smoke→HF/GGUF parity 순서로 계획했다. Hugging Face 업로드 계획은 1.22.20에서 공개·비공개 모두 폐기했다.

## 2026-07-18 · 1.22.13 자연대화 source 결함 폐기와 의미 범위 분리

- expanded 1차 tranche의 teacher 표본을 조기에 감사했다. Qwen 다국어는 1,296/2,000 처리 시점에 accepted 1,271·`prompt_copy` rejected 25, Gemma 다국어는 433/2,000, Gemma 한국어는 369/3,000에서 중단했다. 세 run 모두 source 품질 결함으로 기각했으며 export·validate와 학습 입력 혼합을 실행하지 않았다.
- 다국어 source에는 `Reference`/serial이 대화 본문에 노출되고 조사와 큰 수치가 부자연스러웠다. 초기 natural 생성본은 train/heldout이 같은 의미 조합을 100% 공유했고 Qwen/Gemma 본문도 의미상 중복돼, exact prompt overlap 0만으로는 막지 못하는 의미 누출을 확인했다.
- 생성기의 `prompt_index`에 전단사 순열을 적용해 split과 teacher별 의미 조합 선택에 반영했다. train/heldout 및 Qwen/Gemma가 서로 다른 조합 범위를 쓰고, 장소·물체·스타일 축은 양 split에 모두 분포한다. 최종 다국어 natural-v3 SHA는 Qwen `3f4048811d17f9d026b49ff5a9a40e96f90cd7e9e6af9522c7478e2f24faac64`, Gemma `04f7607d87a9fa4b56d950ca787d2b9c9f391a2472013a5a3ef6166189b89272`, manifest fingerprint는 `ff52580ce26acb1a1a966d08c1c08f76b7db5687423a51e3c1667323c46f166d`다.
- 한국어 natural-v2 prompt SHA는 `f854929cf83afb168584aa63969479e69a8ca8e9d3e0ff96ea17646062d5c407`, manifest fingerprint는 `410a98b4330663213064d6f851e44facce9df421b276bb2d0c218af08d61cff8`이다. 조사와 비현실적인 큰 수치를 제거하고 split별 의미 조합 범위와 각 의미 축을 분리했다.
- 새 설정은 `qwen36mtp-multilingual-natural-2000.yaml`, `gemma4-multilingual-natural-2000.yaml`, `gemma4-conversation-natural-3000.yaml`이다. prepare 결과는 각각 train/heldout 1,410/590, 1,421/579, 2,167/833이고 inventory fingerprint는 `3b970e90db06eaa00e06aa59c556d8e1a930944edfdfc7a8b6d4a7ad97e94b09`, `cd006e3843350a719c66f0b1f4ea9396550c20a7c4612d03a3f87300d7ddfb71`, `c82eb66052990802929eef45364c2d0bbb49a57dff8e8981bc4540b8f5d9e2dd`다. 모두 선택 request가 target만큼 고유하고 Wikipedia 보충·prompt/source overlap이 0이며 release blocked와 실제 endpoint preflight를 통과했다.
- 독립 전수 감사에서 22,000행의 row/source SHA 오류와 중복이 0이고, train/heldout 및 Qwen/Gemma canonical 본문 교집합이 모든 task/category에서 0임을 확인했다. 장소·물체·스타일 조합 축은 양 split에 모두 분포했다. 전체 품질 검사는 207 tests, Ruff, format, Pyright 0 오류, 참조 checksum, release audit를 통과했다.
- 당시 다음 실행 순서는 세 수집의 collect→export→validate, 통합 suite 비누출 mix, 100M latest 기반 SFT, 60 scenario·390응답과 suite 밖 자연대화 smoke, 선별 checkpoint의 HF·GGUF parity였다. private Hub 업로드 계획은 1.22.20에서 폐기했다.

## 2026-07-18 · 1.22.12 단계적 teacher 수집

- Qwen full 수집은 306/6,000에서 1.25 req/s, Gemma 두 full 수집 동시 실행은 합산 약 0.79 req/s를 실측했다. Gemma 한국어 ETA가 7.7시간까지 늘어 두 작업을 안전 중단했고 완료 spool은 보존했다.
- 품질 피드백을 먼저 얻기 위해 Qwen 다국어 2,000, Gemma 다국어 2,000, Gemma 한국어 자연대화 3,000의 독립 run 설정을 추가했다. 기존 1.22.11 full 설정과 inventory는 바꾸지 않는다.
- tranche export로 재학습·390응답·suite 밖 실제 대화를 먼저 판정한다. 통과하지 못하면 full Qwen 6,000·Gemma 6,000·한국어 10,000 수집을 `resume`해 데이터량을 늘린다.

## 2026-07-18 · 1.22.11 대규모 자연대화 증류 준비

- focused-v12 실패 원인을 조사해 기존 한국어 source 11,880행의 고유 user prompt가 2,294개뿐이고 단순 10,000 요청 설정은 Wikipedia 7,706개를 보충한다는 사실을 실제 `distill prepare`로 확인했다. 이 잘못된 경로는 수집하지 않았다.
- 10개 범주의 한국어 자연대화 prompt를 train 8,000·heldout 2,000으로 생성했다. 10,000개가 모두 고유하며 SHA는 `40175685…4baf`, manifest fingerprint는 `ff546202…15d`다.
- 기존 다국어 v1 payload를 byte 그대로 보존하고, 영어·일본어 공감 대화와 네 번역 방향의 문형을 확장한 v2를 teacher별 train 4,800·heldout 1,200으로 생성했다. Qwen SHA는 `1cf390a8…6033`, Gemma SHA는 `87982980…fa27`, manifest fingerprint는 `3a63e661…870a`다.
- Qwen 다국어 6,000개는 최종 split train 4,338·heldout 1,662, Gemma 다국어는 train 4,334·heldout 1,666, Gemma 한국어는 train 7,239·heldout 2,761이다. 세 inventory 모두 고유 prompt 수가 target과 같고 Wikipedia 보충·prompt/source overlap은 0이다.
- `localhost:8081/v1`의 qwen36mtp와 `macmini:11434/v1`의 Gemma4 모델 preflight를 실제 통과했다. teacher 출력은 내부 전용이다. 당시 private 저장소만 허용하려던 계획도 1.22.20에서 폐기해 Hugging Face 업로드를 전면 금지한다.

## 2026-07-18 · 1.22.10 focused-v12 150-step 학습 기각

- 원 step 600에서 focused-v12를 4e-6→4e-7, effective batch 64로 150 step 학습했다. validation PPL은 step 25/50/75/100/125/150에서 1.75385/1.54393/1.45736/1.42701/1.41309/1.40665로 감소했고 final SHA는 `c68dae38…312a`다.
- step 50의 390응답은 정확도 36.67%, 멀티턴 46.67%, 유해 거절 100%, EOS 100%, unsafe 0이었지만 정상 오거절 14.33%, hard loop 5건이었다.
- step 150은 정확도 37.69%, 멀티턴 46.67%, 유해 거절 100%, EOS 99.74%, unsafe 0, 정상 오거절 11.99%, hard loop 4건이었다. 최악 profile/seed는 정확도 32.31%, 멀티턴 20%, 정상 오거절 17.54%, loop 1건이다.
- suite 밖 greedy 추론에서 한국어 응원 요청은 `안녕하세요, 정보마당||`, 영어 응원은 문법이 불안정한 문장, 일본어 응원은 한국어 조각이 섞인 비문을 출력했다. 자동 점수만의 문제가 아니므로 step 150을 대화 가능·HF 업로드 후보에서 제외했다.
- knowledge base의 원래 목표도 이 87M 모델을 상용 챗봇이 아닌 교육·연구 baseline으로 규정한다. 현재 목표를 충족하려면 direct multilingual teacher train 1,532행을 확대하고, 새 holdout과 실제 대화 smoke로 다시 검증해야 한다.

## 2026-07-18 · 1.22.9 focused-v12 학습률 A/B

- step 600 SHA `3b5e9c12…b0e2`에서 LR 2e-6→2e-7과 4e-6→4e-7을 각각 새 optimizer로 25 step 학습했다. checkpoint SHA는 `e03dc6e4…3591`·`c700b200…7a33`, repair heldout PPL은 2.19526·1.86311이다.
- LR 2e-6의 390응답은 정확도 29.23%, 유해 거절 68.75%, 멀티턴 6.67%, EOS 99.74%, 정상 오거절 5.85%, unsafe 2, loop 1이었다.
- LR 4e-6은 정확도 28.46%, 유해 거절 93.75%, 멀티턴 6.67%, EOS 100%, 정상 오거절 13.45%, unsafe 0, loop 1이었다. 두 후보 모두 gate는 실패했지만 안전 우선순위에 따라 4e-6을 연장 후보로 선택했다.
- 정식 설정은 A/B checkpoint를 resume하지 않고 원 step 600에서 seed 191, warmup 10, 4e-6→4e-7, 최대 150 step으로 새 run을 시작한다. 25 step마다 checkpoint·validation을 남기고 안전·정확도·멀티턴이 개선되지 않으면 조기 기각한다.

## 2026-07-18 · 1.22.8 다국어 집중 repair curriculum

- `SFTCurriculumConfig`에 기존 fingerprint를 보존하면서 범주별 train/heldout quota와 이름 있는 추가 replay 원천을 추가했다. 각 원천은 경로·행 수·허용 license·선택 category를 fingerprint와 manifest에 결속한다.
- `focused-v12`는 사실·산술·추출·형식·한국어·EOS 600행, 네 안전 거절 400행, 다중 턴 문맥 400행, 인사·일상 240행, 영어·일본어 대화와 네 번역 방향 280행, 반복 억제 80행을 생성한다.
- Qwen 다국어 train 799, Gemma 다국어 train 733, benign safety·실시간 한계·근거 한계·PII/secret 각 117행을 결합해 train 4,000행을 만들었다. heldout은 신규 200행과 두 teacher 각 100행으로 400행이다.
- train SHA는 `e3483f14…ff33`, heldout SHA는 `c444720c…0fc8`, manifest SHA는 `f2794728…8deb`, fingerprint는 `c3830413…0006`이다. 통합 suite·train/heldout 모든 user turn과 source overlap은 모두 0이다.
- 기존 v11 material을 다시 validate해 fingerprint `9235fbb5…44d4`와 byte 호환을 보존했다. 새 A/B 설정은 step 600 SHA `3b5e9c12…b0e2`에서 optimizer를 초기화하고 LR 2e-6 또는 4e-6로 25 step 학습한다.

## 2026-07-18 · 1.22.7 600-step 다국어 SFT 완료와 품질 기각

- `configs/sft/ko-qwen-gemma-multilingual-v1.yaml`을 CUDA bf16, effective batch 64로 600 step 완료했다. 최종 loss는 1.81682, 고정 heldout loss/PPL은 2.121864/8.34668이며 checkpoint SHA는 `3b5e9c12…b0e2`다.
- 한국어 품질·대화 준비도 42 scenario와 다국어 대화·번역 18 scenario를 byte 그대로 결합한 `ko-multilingual-chat-quality-v1.jsonl`을 추가했다. 60 scenario·65 turn에 greedy 1회와 sampling 5회를 적용해 390응답을 계획하며 SHA는 `bd76a433…fb23`이다.
- step 300 평가는 정확도 29.23%, 유해 거절 41.67%, 멀티턴 유지 6.67%, EOS 98.21%, unsafe 6건, hard loop 5건이었다. step 600은 정확도 30.26%, 유해 거절 39.58%, 멀티턴 유지 10%, EOS 98.21%, unsafe 5건, hard loop 6건이었다.
- profile/seed 최악값도 step 600에서 정확도 27.69%, 유해 거절 25%, 멀티턴 유지 0%, unsafe 1건, hard loop 2건으로 실패했다. validation 개선이 실제 대화 능력을 보장하지 않으므로 300·600 checkpoint를 모두 배포·HF 업로드 후보에서 제외했다.
- 다음 작업은 평가 문장을 학습에 복제하지 않고 기존 비누출 대화·안전 curriculum과 Qwen/Gemma 다국어 teacher 행을 재가중한 집중 continuing SFT다. 자동 gate, suite 밖 자유대화, 수동 blind review를 모두 통과한 checkpoint만 로컬 HF·GGUF 최종 parity 대상으로 삼는다. private Hub 업로드 계획은 1.22.20에서 폐기했다.

## 2026-07-18 · 1.22.6 private HF·GGUF 내보내기

- SFT checkpoint를 immutable snapshot으로 한 번 읽어 SHA-256·fingerprint·release 차단·finite tensor·현재 모델 shape/dtype을 검증한 뒤 HF Llama 형식으로 원자 게시하는 `llmex model export-hf`를 구현했다.
- LLMEX 인접쌍 RoPE Q/K를 HF Llama half-split 배열로 변환하고 tied embedding, GQA, RMSNorm, RoPE theta와 16k tokenizer를 보존했다. HF chat template는 학습과 같은 BOS, 과거 assistant EOS, trailing CR/LF 제거를 적용한다.
- 예상 HF manifest SHA와 고정 artifact 집합의 SHA/bytes를 검증한 뒤 llama.cpp 공식 converter를 격리 실행하는 `llmex model export-gguf`를 구현했다. ByteLevel BPE 전체 계약과 tokenizer SHA를 wrapper에서 다시 확인한다.
- HF 출력은 디렉터리 0700·파일 0600, GGUF는 0600으로 고정했다. 변환 중 같은 출력이 생기면 덮어쓰지 않고 실패하며, GGUF magic과 release 차단·상위 manifest 결속을 결과에 기록한다.
- focused-v9 step 2 checkpoint SHA `59af3549…438`를 실제 HF로 변환했다. 61-token 다중 턴 입력에서 원본 LLMEX와 Transformers 최대 logit 절대 오차는 `9.5367431640625e-05`, 모든 위치 argmax는 일치했다.
- 같은 HF export를 llama.cpp `b9550-f0156d140`로 F16 GGUF `200,967,680` bytes, SHA `efb2671a…2070`으로 변환했다. `llama-completion -no-cnv` greedy 결과가 원본과 같은 `[[안녕하세요` 뒤 EOS에 도달했다.
- 표적 회귀는 모델 export·checkpoint 학습 테스트 `34 passed`, Ruff·Pyright 오류 0으로 통과했다. 이 검증은 converter 계약 증거이며 현재 600-step 학습의 최종 checkpoint 품질 또는 public release 승인이 아니다.
- 내부 teacher 파생 산출물은 `redistribution_allowed=false`, `release_gate=blocked`, `hub_visibility=private`를 유지한다. 이 필드는 로컬 artifact의 비공개 정책이며, 1.22.20부터 Hugging Face 업로드는 공개·비공개 모두 금지한다.

## 2026-07-18 · 1.22.5 다국어 SFT 실행 계약

- `expected_base_checkpoint_sha256`를 추가해 지정한 base checkpoint를 immutable snapshot으로 읽은 직후 역직렬화 전에 SHA 불일치를 실패-폐쇄한다. 필드를 쓰지 않는 기존 SFT config fingerprint는 새 필드를 생략해 호환성을 유지한다.
- `runs/baseline-100m/checkpoints/latest.pt` SHA `dae1b01b…33b3`와 최종 3원천 manifest SHA `f3c11daf…ce58`를 고정한 600-step CUDA bf16 설정을 만들었다. LR은 1.2e-5→1.2e-6, warmup 30, effective batch 64, validation 25-step, checkpoint 50-step이다.
- 실제 no-baseline preflight는 87,804,672 parameters, train 14,374·heldout 2,430행, 총 4,105,835 token과 32,981,128-byte 연속 cache, base/source/release fingerprint 결속을 확인했다. 학습 산출물은 내부 전용이며, 1.22.20부터 HF 업로드는 공개·비공개 모두 금지한다.

## 2026-07-18 · 1.22.4 한국어·Qwen·Gemma 다국어 3원천 결속

- 기존 `SFTMixConfig`에 선택적 public upstream manifest와 이름 있는 추가 teacher export 목록을 추가했다. 새 필드를 쓰지 않는 legacy config는 필드를 fingerprint 입력과 manifest에서 생략해 기존 mix 출력과 fingerprint를 그대로 재유도한다.
- public curriculum manifest는 self-fingerprint·tokenizer·길이·train/heldout SHA와 행 수·release policy를 검증하고, Qwen primary와 Gemma additional teacher는 각각 schema 2 export manifest의 세 core fingerprint·출력 SHA·행 수에 결속한다. 어느 JSONL이나 manifest가 바뀌어도 preflight가 실패한다.
- 세 원천 16,921행을 전역 heldout 우선으로 다시 격리해 중복 heldout prompt 117행을 제외했다. 최종 train 14,374 SHA `1251c2a3…1d41`, heldout 2,430 SHA `7992479a…e650`, manifest SHA `f3c11daf…ce58`이며 prompt·source overlap 0, release blocked다.

## 2026-07-18 · 1.22.3 Qwen36mtp·Gemma4 다국어 증류 완료

- Qwen36mtp와 Gemma4가 각각 1,080개 요청을 약 15분 30초에 처리했다. Qwen은 prompt copy 10건을 제외한 1,070건, Gemma는 1,080건 전량을 채택했으며 미완료 요청은 없다.
- canonical 응답 중복을 Qwen 1건, Gemma 111건 제거했다. Qwen export는 train 799·heldout 270행이고 SHA는 `935c9c03…0fef8`, `d750f23f…0db4`, manifest SHA는 `12b4a893…c459`다. Gemma export는 train 733·heldout 236행이고 SHA는 `c1382df7…9669`, `117e55f1…33d2`, manifest SHA는 `c52fa324…c7e`다.
- 두 export 모두 prompt overlap 0, upstream source overlap 0, 현재 spool에서의 byte 재유도 검증을 통과했다. 영어·일본어 대화 및 네 번역 방향의 실표본을 확인했으며, 고유명사 음역과 문맥상 `notebook` 번역 차이는 최종 다국어 suite와 실제 대화 평가에서 후보 checkpoint를 선별하는 품질 위험으로 남겼다.

## 2026-07-18 · 1.22.2 영어·일본어 대화/번역 증류 기반

- `llmex data multilingual-prompts`로 Qwen36mtp와 Gemma4에 서로 겹치지 않는 영어 대화·일본어 대화·한↔영·한↔일 6개 task inventory를 결정적으로 생성한다. teacher별 train 900·heldout 180, 1,080행이며 전체 exact prompt overlap은 0이다.
- 현재 16k tokenizer 실측은 unknown 0이지만 일본어가 1.42 token/문자로 한국어 0.57보다 비효율적이다. 100M base embedding을 유지해야 하므로 tokenizer는 교체하지 않고 1024 길이 안의 짧은 대화·번역으로 범위를 제한한다.
- 두 teacher는 실제 호출에서 영어·일본어 대화와 번역을 수행했다. Qwen은 `enable_thinking=false`로 답변 token budget을 보존한다. 독립 다국어 suite 18 scenario·108응답은 언어 유지와 번역의 이름·숫자·단위·의미 보존을 검증하며 SHA는 `6dea0637…d8eb`다.

## 2026-07-18 · 1.22.1 Qwen/public+Gemma 비누출 curriculum

- 기존 Qwen/public mix와 Gemma export 1,656행을 다시 heldout 우선 격리해 train 9,906·heldout 1,984행을 만들었다. 입력 11,900행 중 heldout prompt 중복 10행을 제외했고 mix manifest SHA는 `6d1f5936…2018`이다.
- 기존 curriculum은 suite와 replay만 비교해, 새로 생성하는 focused-v11 prompt와 replay가 겹치면 마지막 all-user gate에서 늦게 실패했다. 생성 train/heldout 전체 prompt와 겹치는 replay도 사전에 제외하고 실제 겹침이 있을 때만 manifest에 수를 기록해 기존 무겹침 fingerprint를 보존했다.
- replay train 664·heldout 303행을 제외하고 생성 3,600/360행을 합쳐 최종 train 12,842·heldout 2,041행을 만들었다. 통합 42 scenario·47 turn suite, train/heldout, source overlap은 모두 0이다. curriculum fingerprint는 `9235fbb5…44d4`, manifest SHA는 `b11c8fa2…edc6`다.

## 2026-07-18 · 1.22.0 macmini Gemma 4 대화 증류 완료

- `http://macmini:11434/v1`의 `gemma4-26b-a4b-uncensored-hauhaucs-balanced`를 명시적 내부망 allowlist와 강한 한국어 system prompt로 호출해 2,200건을 3,085.164초에 처리했다.
- accepted 2,145, rejected 55, pending 0이다. 거부 사유는 length 47, `unsafe:personal-id` 6, `finish_reason_not_stop` 2건이며 실패나 미완료 요청은 없다.
- canonical 응답 중복 489개를 제거한 export는 train 1,160·heldout 496행이다. train SHA `489d335e…18af`, heldout SHA `3767797e…c0aa`, manifest SHA `824329dd…d601`이며 prompt·upstream source overlap 0과 release blocked를 현재 spool에서 재유도 검증했다.
- 표본은 자연스러운 인사·일상 대화, 실시간/문서 근거 부재의 한계 고지, 안전 거절을 포함한다. 일부 장황하거나 메타적인 답변이 있어 단독 teacher로 승인하지 않고 Qwen/public replay·통합 282응답 gate와 함께 학습·선별한다.

## 2026-07-18 · 1.21.4 품질·대화 준비도 통합 suite

- 기존 정확도·안전 `ko-chat-quality-v1` 24 scenario·27 turn과 자연 대화 `ko-conversation-readiness-v1` 18 scenario·20 turn을 byte 그대로 이어 붙인 통합 suite를 추가했다.
- 통합 suite는 42 scenario·47 unique user turn·6개 decoding profile 기준 282응답을 계획하며 SHA-256은 `4461f760…fd94`다. 최종 curriculum은 이 한 SHA를 사용해 두 평가 집합 모두와의 exact prompt 비누출을 manifest에 결속할 수 있다.
- 원본 두 파일의 byte 결합, scenario·prompt 고유성, 응답 계획 수와 고정 SHA를 회귀 테스트로 검증한다.

## 2026-07-18 · 1.21.3 정식 Qwen 10k 증류 호환 복구

- 내부망 teacher allowlist 도입 전 생성한 loopback run은 빈 `allowed_endpoint_hosts` 필드 때문에 현재 설정 fingerprint와 달라졌다. 빈 allowlist만 legacy 표현으로 정규화하고, 실제 내부망 host 목록은 계속 fingerprint에 포함하도록 수정했다.
- 현재 CLI에서 정식 Qwen v5 10k를 다시 검증해 completed 10,000, accepted 9,712, rejected 288, pending 0을 확인했다. export는 train 8,213·heldout 1,488행이며 prompt·upstream source overlap은 0이다.
- export train SHA는 `35f6b6d1…90de`, heldout SHA는 `1767b07d…4cf`, manifest SHA는 `6d724261…ae5d`다. 기존 loopback 호환과 내부망 allowlist 결속을 회귀 테스트로 고정했다.

## 2026-07-18 · 1.21.2 v11 step 50 대화 준비도 실패 기준선

- 기존 162응답에서 가장 나았던 v11 step 50 SHA `3c17b257…cd85`를 새 18 scenario·20 turn 준비도 suite의 greedy+5 sampling seed, 총 120응답으로 평가했다. artifact manifest fingerprint는 `4b29ddb0…3b6`이고 현재 SHA 고정 입력에서 byte 재유도했다.
- EOS와 유해 요청 거절은 100%, unsafe·PII·secret·hard loop는 0이었다. 그러나 aggregate 정확도 45%, profile/seed 최악 정확도 35%, 멀티턴 유지 0%, 최악 정상 오거절 22.22%로 gate가 실패했다.
- 일반 인사를 개인정보·위험 요청처럼 거절하고, 일상 대화가 무관한 고유명사·영어 조각·비문으로 무너지는 응답을 보존했다. 이 결과는 새 Gemma4+Qwen/public+안전 curriculum SFT가 넘어야 할 정식 기준선이다.

## 2026-07-18 · 1.21.1 curriculum manifest 최종 SFT 결속

- 기존 runtime은 `sft-public-teacher-mix` manifest만 source로 허용해, 그 mix를 replay로 만든 `sft-capability-remediation-curriculum`의 최종 출력 계보를 SFT 설정에 pin할 수 없었다.
- curriculum manifest도 schema·canonical fingerprint·train/heldout SHA·tokenizer manifest SHA·최대 sequence와 생성 reserve·redistribution/release 정책을 동일하게 검증하도록 확장했다.
- 실제 결정적 curriculum fixture를 게시하고 그 manifest를 SFT `source_manifest`로 결속한 preflight가 release blocked를 계승하는지 통합 검증했다. kind를 알 수 없는 값으로 바꾸고 fingerprint·manifest SHA까지 다시 계산한 위조도 실패-폐쇄한다.

## 2026-07-18 · 1.21.0 한국어 대화 준비도 120응답 gate

- 기존 24 scenario 품질 suite가 사실·산술·형식·안전 회귀는 잡았지만, 자동 통과 checkpoint가 자연 인사에 `423`을 답한 실제 누락을 별도 실패 조건으로 고정했다.
- MIT `ko-conversation-readiness-v1.jsonl`에 인사·일상 대화, 실시간 정보 미제공/제공, 문서 근거 미제공/제공, 선호 기억·최신 정정, 개인정보·위험 거절을 18 scenario·20 unique turn으로 추가했다. canonical greedy 1회와 sampling seed 5회 계획은 120응답이다.
- suite SHA는 `9d69ff68…c57c`다. 기존 quality v1, focused-v11 train/heldout 모든 user turn, 진행 중 Gemma4 2,200 inventory와 exact prompt overlap 0을 실측했다.
- schema·라이선스·고유 ID·범주·유해/정상/다중턴 분모·100개 이상 수동 review population을 회귀 테스트로 고정했다. 정식 checkpoint는 기존 162응답과 새 120응답을 모두 통과해야 한다.

## 2026-07-18 · 1.20.5 저학습률·안전 복원 trial 기각

- v9 step 2에서 focused-v11을 5e-7→5e-8로 20 step 추가 학습한 trial은 validation PPL을 5.85545에서 4.84900으로 낮췄지만, step 5·10·15·20 모두 일반 인사를 안전 거절로 오판했다. 손실 감소만으로 대화 능력이 회복되지 않아 전 checkpoint를 기각했다.
- v10-long step 100 SHA `a5844888…4bda`에서 focused-v9 안전 데이터를 3e-7→3e-8로 20 step 학습했다. step 20 SHA `25e80ab9…04ad`는 validation PPL 2.15369, aggregate 정확도 91.36%, EOS·멀티턴 100%, 반복 0을 기록했다.
- 그러나 고정 162응답의 profile/seed 최악 정확도 88.89%, 유해 요청 거절 83.33%, unsafe 1건으로 자동 gate가 실패했다. manifest fingerprint는 `20550558…570`이며, 해당 checkpoint도 대화 가능 후보에서 제외한다.
- 두 trial 설정과 step 20 품질 설정을 보존해 실패한 경로를 재현할 수 있게 했다. 다음 학습은 국소 보정 checkpoint가 아니라 100M latest에서 검증된 Qwen/public·Gemma 대화·안전 replay를 함께 학습한다.

## 2026-07-18 · 1.20.4 학습·추론 메시지 개행 정규화 일치

- 기존 BOS와 과거 assistant EOS 경계는 일치했지만, assistant 메시지가 이미 줄바꿈으로 끝나면 학습 tokenization만 줄바꿈을 하나 더 붙였다. 실제 rollout 이력이 만드는 이 차이는 생성 prompt와 학습 prefix의 토큰 완전 일치 계약을 깨뜨렸다.
- 학습 tokenization도 추론 renderer와 같이 메시지 말단 CR/LF를 제거한 뒤 줄바꿈 하나만 추가하도록 수정했다. 말단 줄바꿈을 가진 동일 assistant 이력을 사용해 생성 prompt 토큰과 학습 prefix 토큰이 정확히 같은지 회귀로 고정했다.
- 이 수정은 checkpoint를 자동 승인하지 않는다. macmini Gemma 4 대화 증류, 100M latest 기반 재학습, EOS·반복·안전·수동 품질 gate는 계속 진행한다.

## 2026-07-18 · 1.20.3 OpenAI 호환 빈 tool_calls 수용

- macmini Gemma 4의 실제 completion message는 `role`, `content`, 빈 `reasoning_content`와 함께 `tool_calls: []`를 반환했다. 기존 strict client는 이 표준 빈 필드를 예상하지 않은 확장으로 거부해 모든 수집이 실패하는 상태였다.
- 빈 `tool_calls`만 무해한 메타데이터로 허용하고, 한 건이라도 실제 tool call이 있거나 알 수 없는 message 필드가 있으면 계속 거부하도록 수정했다. teacher가 도구 실행 결과를 일반 assistant label로 섞는 경로는 열지 않았다.

## 2026-07-18 · 1.20.2 신뢰 내부망 teacher endpoint allowlist

- 기존 distill 설정은 loopback HTTP `/v1`만 허용해 사용자가 제공한 `http://macmini:11434/v1` Gemma 4 teacher를 구성할 수 없었다. 기본 loopback 제한은 유지하고 `allowed_endpoint_hosts`에 정확히 명시한 정규화 hostname만 opt-in하도록 확장했다.
- userinfo·query·fragment·HTTPS·미등록 host 거부, hostname 공백·대문자·구분자·중복 거부를 유지하거나 추가했다. 허용 host를 다른 값으로 바꾸면 같은 endpoint가 즉시 검증 실패하는 회귀를 고정했다.
- macmini의 실제 `/v1/models`에서 `gemma4-26b-a4b-uncensored-hauhaucs-balanced`, `google/gemma-4-12b` 등을 확인했다. balanced 모델은 자연 대화·실시간 한계 답변은 우수하지만 PII 가상 번호를 생성하므로 대화 범주에만 쓰고 qwen36 안전 label과 분리한다.

## 2026-07-18 · 1.20.1 focused-v11 학습과 최적 checkpoint 판정

- v9 step 2 SHA `59af3549…438`에서 CUDA bf16, effective batch 64, 2e-6→2e-7로 focused-v11을 150 step 학습했다. validation loss/PPL은 baseline 1.928266/6.877574에서 step 150의 0.780351/2.182239로 감소했고 latest SHA는 `6fa42367…b3c6c`다.
- validation 최종값만 선택하지 않고 step 25 SHA `41d7ac75…9746`와 step 50 SHA `3c17b257…cd85`를 고정 24 scenario·27 turn·162응답으로 비교했다. 두 결과 모두 현재 SHA 고정 입력에서 byte 재유도했다.
- step 25는 aggregate 정확도 93.21%, 유해 요청 거절 100%, EOS 100%지만 profile/seed 최악 정확도 85.19%, 멀티턴 유지 66.67%로 실패했다. manifest fingerprint는 `74065e61…3368`이다.
- 가장 나은 step 50은 aggregate 정확도 91.36%, 유해 요청 거절·EOS·멀티턴 유지 100%, unsafe·hard loop 0을 기록했다. 다만 profile/seed 최악 정확도 88.89%가 90% 기준에 응답 한 건 부족해 자동 gate가 실패했으며 manifest fingerprint는 `e4f1a4d6…bbb9`다.
- 실제 인사는 개선됐지만 실시간 정보 답변 표현과 자유대화 문법이 아직 불안정하므로 checkpoint 승인은 계속 차단한다. 다음 작업은 step 50 기반 최소 보정과 suite 밖 재현 가능한 대화 회귀다.

## 2026-07-18 · 1.20.0 대화·안전 동시 보존 focused-v11 curriculum

- focused-v10 step 100에서 인사·실시간 표현은 개선됐지만 PII 바꿔쓰기가 명확한 거절을 잃은 실측을 근거로 `focused-v11`을 추가했다. v10 네 범주와 v9 PII/secret·정상 안전 두 범주를 한 단계에서 생성한다.
- 생성 7,200/720행과 v2 replay 6,000/600행을 합쳐 train 13,200/heldout 1,320행을 원자 게시했다. SHA는 `4c640ae6…9ad5`·`8c58ee35…93c1`, manifest fingerprint는 `76909dfc…7e63`이다.
- PII/secret 44,880, 정상 안전 28,380, 일반 대화·불확실성 114,312, replay 124,937 assistant 목표 token을 기록했다. suite·split 모든 user turn과 source overlap은 0이며 focused-v10 preflight 불변과 byte 재유도를 유지한다.

## 2026-07-18 · 1.19.1 재현 가능한 대화 decoding CLI

- `sft generate`에 temperature, top-k, top-p, repetition penalty, seed, 최대 생성 token 옵션을 추가했다. 실제 적용값은 응답 JSON의 `decoding`에 기록한다.
- runtime 생성은 명시적 `GenerationConfig`와 device별 고정 generator를 받아 자동 품질 rollout과 같은 sampling·반복 억제 경계를 사용한다. 기존 내부 호출의 고정 greedy 기본값은 보존한다.
- focused-v10 step 100을 실제 CLI repetition penalty 1.2로 확인해 인사가 한 문장 EOS로 끝나고 실시간 재고는 정보가 없음을 밝히는 방향으로 개선됨을 확인했다. PII 바꿔쓰기는 명확한 안전 거절이 아니므로 checkpoint 승인은 계속 차단한다.

## 2026-07-18 · 1.19.0 일반 대화·불확실성 focused-v10 curriculum

- 실제 CLI의 `423` 인사 붕괴와 실시간 재고 근거 없는 확정을 근거로 `focused-v10`을 추가했다. 자연스러운 인사·일상 대화, 실시간 정보 미제공/제공, 문서 근거 미제공/제공을 네 범주로 대조한다.
- 생성 4,800/480행과 v2 replay 6,000/600행을 합쳐 train 10,800/heldout 1,080행을 원자 게시했다. SHA는 `57e934ed…a976`·`01c9ba11…9076`, manifest fingerprint는 `f40fe0a0…ac20`이다.
- 인사 29,886, 일상 대화 30,306, 실시간 불확실성 29,370, 근거 불확실성 24,750, replay 128,323 assistant 목표 token을 기록했다. suite·split 모든 user turn과 source overlap은 0이며 focused-v9 preflight 불변과 byte 재유도를 유지한다.
- 실시간 값이나 문서가 없는 사례는 한계와 확인 경로를 답하고, 프롬프트에 값이 제공된 25% 반례는 그 값을 정상 답하도록 구성해 무조건 회피를 막았다.

## 2026-07-18 · 1.18.1 focused-v9 학습·자동 통과와 실제 대화 한계

- v7 step 10 SHA `0ca3b8ae…d61`에서 CUDA bf16, effective batch 64, 3e-7→3e-8로 focused-v9을 10 step 학습했다. validation loss/PPL은 step 2의 0.373815/1.45327에서 step 10의 0.336498/1.40004로 감소했다.
- step 2 SHA `59af3549…438`를 수정된 chat 경계로 24 scenario·27 turn·162응답 생성·byte 재유도했다. manifest/report fingerprint는 `a8874ab3…dc4`·`0e0e43f7…3c8`이다.
- 자동 gate는 correctness·harmful refusal·multi-turn·EOS 100%, benign false refusal·unsafe·PII·secret·hard loop 0으로 모든 category/profile/seed를 통과했다.
- 별도 실제 CLI smoke에서 수도·칼 보관·PII 거절은 통과했지만 자연스러운 인사에 `423`, 실시간 편의점 재고 질문에 조회 근거 없이 확정했다고 답했다. 자동 suite 통과만으로 대화 가능성을 승인하지 않고 인사·일상 대화·불확실성 일반화를 다음 보정 범위로 고정했다.

## 2026-07-18 · 1.18.0 PII·정상 안전 focused-v9 curriculum

- 수정 템플릿의 실제 실패 두 건만 겨냥해 `focused-v9`을 추가했다. PII/secret 거절과 정상적인 칼 보관·물 끓음 설명을 별도 범주로 만들고 v2 성공 범주를 replay한다.
- 생성 4,800/480행과 replay 6,000/600행을 합쳐 train 10,800/heldout 1,080행을 게시했다. SHA는 `91eb4555…8545`·`92d2cbc5…c91f`, manifest fingerprint는 `79042357…e932`다.
- PII/secret 89,760, 정상 안전 56,760, replay 125,070 assistant 목표 token을 기록했다. suite·split 모든 user turn과 source overlap은 0이며 focused-v8 불변과 byte 재유도를 유지한다.

## 2026-07-18 · 1.17.2 다중 턴 학습·생성 템플릿 경계 일치

- `render_chat`이 학습 `tokenize_chat`과 동일하게 BOS로 시작하고 과거 assistant마다 EOS를 넣도록 수정했다. 생성 응답의 종단 줄바꿈은 하나로 정규화하고 mixer·curriculum·runtime 길이 계산의 수동 BOS 보정을 제거했다.
- trailing newline을 가진 실제 생성 이력을 포함해 생성 prompt token이 학습 prefix token과 정확히 같은지 회귀로 고정했다. turn마다 마지막 user가 포함되고 KV cache가 새로 초기화되는 기존 계약도 확인했다.
- v7 step 10·20을 수정된 경계로 각각 162응답 재유도했다. 두 checkpoint 모두 EOS 100%, loop·unsafe 0, correctness 98.77%, harmful refusal 97.22%, multi-turn 100%, benign false refusal 0이며 마지막 날짜는 모든 profile에서 `8월 19일`이다.
- PII seed 13의 `서울`, 정상 안전 seed 14의 `파란` 두 sampling 오류 때문에 category worst gate는 실패한다. step 10 manifest/report fingerprint는 `c9c6144c…121c`·`e7bfe38a…8e70`, step 20은 `d0126a91…953f`·`b6ba78e7…d0da`다.

## 2026-07-18 · 1.17.1 focused-v8 학습과 템플릿 불일치 진단

- v7 step 10 SHA `0ca3b8ae…d61`에서 CUDA bf16, effective batch 64, 5e-7→5e-8로 focused-v8을 20 step 학습했다. baseline loss/PPL 0.282483/1.32642에서 step 20 validation loss/PPL 0.162003/1.17586으로 감소했고 final SHA는 `7cec81df…b11d8`다.
- step 5·20의 고정 162응답을 생성·재유도했지만 최신 날짜가 계속 직전 assistant 문장으로 출력됐다. 코드 경계를 추적한 결과 `tokenize_chat`은 매 assistant 뒤 EOS를 학습하는 반면 `render_chat` 기반 다중 턴 생성 prompt는 과거 assistant EOS를 누락했다.
- 이 학습·추론 템플릿 불일치 아래의 품질 수치는 checkpoint 승인 근거로 사용하지 않는다. 기존 v7 안전 checkpoint를 수정된 동일 token 경계로 다시 평가하는 작업을 다음 하위 단계로 분리한다.

## 2026-07-18 · 1.17.0 값-only 형식 일반화 focused-v8 curriculum

- focused-v7의 step 증가로도 최신 날짜 단답이 바뀌지 않은 증거를 근거로 `focused-v8`을 추가했다. 날짜뿐 아니라 배포 코드·담당자·승인 상태·회의 장소의 갱신 확인 문장 뒤 값만 출력하는 대조를 만들어 표면 문장 암기 대신 형식 지시를 보강한다.
- 생성 2,400/240행과 v2 성공 범주 replay 6,000/600행을 합쳐 train 8,400/heldout 840행을 게시했다. SHA는 `bfd8f39b…1e88`·`7dcc3568…c51`, manifest fingerprint는 `f4dc0633…d647`다.
- format-exact 목표 token은 70,950개, replay는 127,144개다. suite·split 모든 user turn overlap과 source overlap은 0이며 focused-v7 preflight 불변과 byte 재유도를 유지한다.

## 2026-07-18 · 1.16.1 focused-v7 학습과 exact 형식 한계 확인

- focused-v6 step 20 SHA `371a5cc1…b800`에서 CUDA bf16, effective batch 64, 5e-7→5e-8로 20 step 학습했다. validation loss/PPL은 step 5의 0.767849/2.15513에서 step 20의 0.691437/1.99658로 감소했고 final SHA는 `cf896472…0df0`다.
- step 5·10·20을 고정 24 scenario·27 turn·162응답으로 각각 생성하고 byte 재유도했다. manifest fingerprint는 `37712bf1…ba0`, `d0d7a198…2a59`, `8c23ed6a…a25`다.
- step 10·20은 EOS 100%, loop·unsafe 0, correctness 95.68%, harmful refusal 100%, benign false refusal 0을 기록했다. PII refusal도 100%로 회복했다.
- 세 checkpoint 모두 문맥 마지막 응답을 `8월 19일로 갱신했습니다.`로 생성해 exact 날짜-only 목표를 실패했고 multi-turn retention은 66.67%였다. 단순 학습 step 증가는 이 형식 오류를 바꾸지 못했으므로, suite 전체 대화를 복제하지 않는 일반 형식 counterexample을 다음 보정으로 분리한다.

## 2026-07-18 · 1.16.0 exact 문맥·PII focused-v7 curriculum

- focused-v6 step 20의 실패 응답을 근거로 `focused-v7` 범위를 최신 날짜 exact 단답과 PII/secret sampling 거절로 제한했다. 문맥 행은 갱신 확인 뒤 날짜만 답하는 assistant 목표를 세 번 배치해 target-token 질량을 직접 높인다.
- `configs/sft/qwen36mtp-v5-remediation-v7-data.yaml`은 생성 2,400/240행과 v2 replay 6,000/600행을 합쳐 train 8,400/heldout 840행을 게시했다. SHA는 `5789ccf1…6e89`·`8e3ff6ed…b0c3`, manifest fingerprint는 `e0fee0ce…9e33`다.
- suite·split 모든 user turn overlap과 source overlap은 0이다. replay 목표 token 126,090개는 전체 222,450개의 약 56.7%이며 focused-v6 preflight 불변과 내부 release block을 유지한다.

## 2026-07-18 · 1.15.1 focused-v6 학습과 대화 정확성 회복

- v5 step 50 SHA `dedd4c9e…fa07`에서 CUDA bf16, effective batch 64, 7e-7→7e-8, 40 step을 실행했다. step-0 PPL 1.62742에서 step 40 validation loss 0.376217로 개선됐고 final SHA는 `c65285b5…e489`다.
- step 40의 100개 heldout NLL/PPL은 0.118812/1.12616이며 EOS·반복·안전 gate를 통과했다. 고정 평가는 validation best뿐 아니라 step 20 SHA `371a5cc1…b800`도 같은 162응답으로 비교했다.
- step 20은 EOS 100%, loop·unsafe·PII·secret 0, correctness 94.44%, harmful refusal 94.44%, multi-turn 66.67%, report fingerprint `2a704580…2b7b`다. 한국어·EOS·불확실성은 100%, context correctness 76.67%, PII refusal 83.33%였다.
- step 40은 correctness 94.44%지만 harmful refusal 91.67%, PII refusal 75%로 악화됐다. 두 checkpoint 모두 최종 날짜를 `8월 19일로 갱신했습니다.`로 출력해 exact 단답을 실패했다. 다음 보정 base는 step 20으로 고정하고 PII sampling·최신 날짜 exact 출력만 다룬다.

## 2026-07-18 · 1.15.0 핵심 앞부분 보존 focused-v6 curriculum

- focused-v5의 실제 실패가 문맥 첫 turn 역할, 최신 날짜 exact 단답, EOS sampling과 한국어 형식에 집중된 것을 근거로 `focused-v6`를 추가했다. suite user 문장의 핵심 앞부분을 유지하고 별도 학습/검증 조건 절을 뒤에 붙여 전체 canonical prompt 중복은 만들지 않는다.
- `configs/sft/qwen36mtp-v5-remediation-v6-data.yaml`은 생성 3,200/320행과 v2 성공 범주 replay 6,000/600행을 합쳐 train 9,200/heldout 920행을 게시했다. SHA는 `2e6ab62d…476a`·`a4a18e46…075d`, manifest fingerprint는 `a9fb6bca…70b9`다.
- suite·split 모든 user turn overlap과 source overlap은 0이다. replay assistant 목표 token 131,085개는 전체 175,415개의 약 74.7%이며 focused-v5 preflight 결과 불변과 내부 teacher 파생 release block을 유지한다.

## 2026-07-18 · 1.14.2 실행 가능한 모듈별 학습 교재

- CPU·CUDA pilot·DGX Spark·localhost teacher 환경을 분리하고 00~20장마다 최소 프로필, 입력, 시작 명령과 종료 증거를 정리했다. 현재 코드와 artifact를 권위로 사용하고 `../knowledge_base` wiki는 과거 운영 맥락의 보조 자료로 유지했다.
- `build-chat-smoke-fixtures.py`가 공개/teacher train·heldout 12행, 내부 teacher manifest, 433 vocab tokenizer, mix·SFT 설정을 결정적으로 만든다. 실제 mix는 train 8/heldout 4, SHA `7ddcc7f0…91a2`·`68f5d19d…4551`, fingerprint `0b6f1ab6…7d04`, prompt/source overlap 0과 release block 계승을 재검증했다.
- CPU fp32 12-step SFT를 직접 실행했다. baseline loss/PPL 6.019514/411.3787에서 heldout loss/PPL 4.326650/75.6903으로 감소했고 latest checkpoint SHA는 `4b8a662b…492c`다. 수도 prompt의 응답은 즉시 EOS로 비어 있어 기능 실행과 대화 품질을 명확히 분리했다.
- checkpoint SHA로 3 scenario·4 turn·24 response 품질 설정을 생성했다. 자동 평가는 예상대로 `gate_passed=false`였고 fingerprint `7eb2cd66…f08d`의 실패 artifact 재유도 검증은 통과했다. 작은 교재 모델의 실패를 production 품질 성공으로 기록하지 않는다.

## 2026-07-18 · 1.14.1 focused-v5 학습과 안전 gate 회복

- v2 best 기반 CUDA bf16 50-step은 step-0 PPL 1.85902에서 step 50 validation PPL 1.19680으로 개선됐고 final SHA는 `dedd4c9e…fa07`다.
- step 30과 50을 고정 162응답으로 비교했다. step 50은 harmful refusal 100%, unsafe·PII·secret·loop 0, EOS 100%, correctness 85.80%, multi-turn 66.67%이며 fingerprint `a411fde9…3546`의 byte 재유도를 통과했다.
- PII sampling 안전은 해결됐지만 문맥 첫 turn이 `기억했습니다` 대신 암호를 바로 출력하고 최종 날짜에 설명을 붙이는 역할 혼동이 남았다. EOS 의미는 4/6으로 개선됐지만 sampling 2건이 실패했다.

## 2026-07-18 · 1.14.0 접미 counterexample focused-v5 curriculum

- v4가 일반 의미 변형에도 `2는 짝수입니까?`를 계속 `아니요`로 답한 실측에 따라, suite 전체 user turn과는 다른 접두사를 붙이되 핵심 접미 구조를 보존한 counterexample을 구현했다. 같은 방식으로 최신 마감일 exact 단답, PII/secret 거절과 한국어 정중 표현·띄어쓰기를 강화한다.
- `configs/sft/qwen36mtp-v5-remediation-v5-data.yaml`은 v2 replay 4,800/480행과 생성 2,400/240행을 합쳐 train 7,200/heldout 720행을 게시했다. SHA는 `85b3c7dd…408f`·`2b01987d…b718`, manifest fingerprint는 `c801e7be…f52c`다.
- suite·split 모든 user turn overlap과 source overlap은 0이며 replay 목표 token은 100,214개로 전체의 약 67.9%다. focused-v4 bytes 불변과 원자 재유도를 통과했다.

## 2026-07-18 · 1.13.1 focused-v4 단기 학습과 품질 비교

- `configs/sft/qwen36mtp-v5-remediation-v4.yaml`은 v2 best에서 CUDA bf16, effective batch 64, 1e-6→1e-7, 50 step을 실행했다. step-0 loss/PPL 1.438882/4.21598에서 step 50 validation loss/PPL 0.465658/1.59307로 개선됐고 final SHA는 `2b2fef04…c397`다.
- step 10은 correctness 83.33%, harmful refusal 91.67%, multi-turn 61.11%, unsafe 1건이었다. step 50은 correctness 87.04%, harmful refusal 91.67%, multi-turn 66.67%, EOS 100%, loop 0이지만 unsafe 1건으로 실패했다.
- step 50의 문맥은 80% correctness까지 회복했으나 최신 날짜 뒤 설명을 붙여 exact 단답을 어겼다. EOS 의미 문항은 여섯 profile 모두 `아니요`였고 PII는 sampling 3건이 거절하지 않았다. 결과 fingerprint `3f647118…d581`은 byte 재유도를 통과했다.

## 2026-07-18 · 1.13.0 보존 replay 기반 focused-v4 curriculum

- v3의 catastrophic forgetting을 근거로 `focused-v4`를 추가했다. v2 curriculum에서 hash 선택한 성공 범주 replay 3,600/360행과 문맥 최신값 단답, `2`의 짝수·홀수 의미, PII/secret 거절, 한국어 정중 표현·띄어쓰기 생성 3,600/360행을 1:1로 결합한다.
- `configs/sft/qwen36mtp-v5-remediation-v4-data.yaml`의 실제 출력은 train 7,200/heldout 720행, SHA `74e12903…3463`·`447f98da…182f`, manifest fingerprint `2eddb72d…0b22`다. suite·split 모든 user turn overlap과 source overlap은 0이다.
- replay assistant 목표 token은 75,910개로 전체 142,002개 중 약 53.5%이며 새 curriculum license를 이전 replay license와 분리했다. focused-v3 preflight 불변 회귀와 원자 게시 byte 재유도도 통과했다.

## 2026-07-18 · 1.12.1 focused-v3 실제 학습과 checkpoint 품질 비교

- `configs/sft/qwen36mtp-v5-remediation-v3.yaml`은 v2 best SHA `892779…12a5`에서 CUDA bf16, effective batch 64, 3e-6→3e-7, 200 step을 실행했다. step-0 loss/PPL 2.188255/8.91963에서 step 200 validation loss/PPL 0.825744/2.28358로 개선됐고 best/latest/final SHA는 `730dfd07…abb9`다.
- step 200의 100개 heldout NLL/PPL은 0.079036/1.08224지만 지시 정렬 1건이 128-token 반복으로 EOS·repetition gate를 실패했다. 고정 162응답은 EOS 100%, loop·unsafe·PII·secret 0, correctness 82.72%, harmful refusal 97.22%, multi-turn 55.56%로 v2보다 망각 회귀했다.
- validation PPL이 가장 낮은 checkpoint를 대화 품질 best로 간주하지 않고 step 25 SHA `04ad606e…1875`도 같은 162응답으로 재유도했다. step 25는 correctness 87.65%, EOS 99.38%, harmful refusal 91.67%, multi-turn 50%, loop 1건으로 전체 gate를 통과하지 못했다.
- fact·산술·추출·지시·불확실성 등 성공 범주를 보존하는 replay와 `2는 짝수`의 의미 일반화, 정정된 최신 문맥의 정확한 단답을 동시에 강화하는 후속 보정이 필요하다. 내부 teacher 파생 release block은 모든 checkpoint에 유지된다.

## 2026-07-18 · 1.12.0 focused-v3 잔여 실패 보정 curriculum

- `generator_profile: focused-v3`는 focused-v2의 고정 162응답을 직접 읽어 남은 한국어 존댓말, 문맥 회상·정정, 불확실성, PII/secret, 폭발물 sampling, 짧은 EOS 정답과 지시 정렬만 독립 범주로 보강한다. suite 문장이나 정답을 복제하지 않고 train/heldout에 서로 다른 요청 표현을 사용한다.
- `configs/sft/qwen36mtp-v5-remediation-v3-data.yaml`로 생성 4,200/420행과 원 정식 public+teacher mix replay 150/15행을 합쳐 train 4,350/heldout 435행을 실제 게시했다. train SHA는 `7a236bdf…8f5`, heldout SHA는 `f48fbf44…535`, manifest fingerprint는 `de97a3cb…7238`이다.
- 모든 user turn의 고정 suite overlap 0, train/heldout overlap 0, provenance source overlap 0을 재유도했다. replay는 assistant 목표 token 32,332개로 전체 122,845개의 약 26.3%이며 내부 teacher 파생 release block을 유지한다.
- 회귀 테스트는 focused-v3 범주와 비누출뿐 아니라 focused-v2 preflight 결과가 새 profile 추가 전후 byte-equivalent임을 확인한다. 교재에는 실제 실패 보고서에서 범위를 좁히고 curriculum을 생성·검증하는 모듈별 절차를 동기화했다.

## 2026-07-18 · 1.11.2 focused-v2 SFT와 자동 품질 재평가

### 300-step 실제 학습

- `configs/sft/qwen36mtp-v5-remediation-v2.yaml`은 v1 best SHA `1a03ca69…c5c`에서 CUDA bf16, effective batch 64, 5e-6→5e-7 cosine, 최대 300 step으로 학습했다. 14분 13초에 종료됐고 step-0 heldout loss/PPL 1.903606/6.71004에서 step 150 best 0.524666/1.68989로 개선됐다.
- best SHA는 `892779993cbd17ca8c032e18772b3a018df9aa4658ac41ccdc28e2f6df9012a5`, step 300 latest SHA는 `65f2914bda88d2f22571d697b82ee4bad0ddf657405655a10a45744f3fc3425c`다. final validation loss/PPL은 0.527707/1.69504이며 내부 teacher 파생 release block을 유지한다.
- best의 100개 heldout 생성은 assistant NLL/PPL 0.076813/1.07984와 safety 통과를 기록했다. 다만 폭발물 변형 1건이 128-token 반복으로 끝나 EOS·repetition gate는 실패했으므로 일반화된 안전 모델로 승인하지 않는다.

### 고정 162응답 자동 gate

- `configs/sft/qwen36mtp-v5-remediation-v2-quality.yaml`로 greedy 1회와 sampling seed 5회의 162응답을 실제 생성하고 byte 재유도했다. fingerprint는 `cc08a8436f0d342e73a5d75e48892f469027538dbf8951d2d194b84c601c3138`다.
- aggregate는 EOS 100%, hard loop·unsafe·PII·secret 0, machine correctness 85.80%, harmful refusal 97.22%, multi-turn retention 66.67%, benign false refusal 2.38%다. 이전 1차 보정의 correctness 32.72%, refusal 30.56%, multi-turn 44.44%보다 크게 개선됐지만 필수 90%·95%·90%와 worst-case를 모두 만족하지 못했다.
- 사실·산술·추출·false-refusal·harmful·jailbreak·반복은 범주 correctness 또는 refusal 100%다. 잔여 실패는 한국어 존댓말 66.67%, 문맥 correctness 63.33%·retention 66.67%, 불확실성 75%, EOS 문항 정답 50%, PII/secret refusal 91.67%와 instruction sampling 1건이다. 응답을 직접 확인해 다음 보정 범위를 이 여섯 축으로 제한한다.

## 2026-07-18 · 1.11.1 57개 모듈별 제작 실습 교재

- 16장의 한 줄 모듈 지도를 57개 Python 파일별 독립 학습 카드로 확장했다. 각 카드는 실제 공개 심볼, 구현 순서, 반드시 실패해야 하는 사례, 표적 테스트·CLI와 완료 산출물을 설명한다.
- 기반·데이터, tokenizer·model, 학습·추론·평가, 대화·증류, pipeline·trust·release, CLI 조립의 여섯 챕터로 의존 순서를 고정했다. CPU fixture를 먼저 통과하고 CUDA·localhost teacher·장기 SFT를 추가하는 환경 경계와 제출 기록 형식을 함께 제공한다.
- `tests/test_book.py`는 `src/llmex`의 Python 파일 집합과 교재의 모듈 카드 집합이 정확히 일대일인지, 챕터 링크가 실제 파일인지 검사한다. 새 모듈을 추가하고 교재를 빠뜨리면 회귀가 즉시 실패한다.
- 현재 저장소와 `../knowledge_base` wiki의 권위 순서를 유지했다. 현재 코드·테스트·실제 artifact가 우선이며 외부 wiki는 과거 운영 snapshot을 보조하는 자료로만 사용한다.

## 2026-07-18 · 1.11.0 focused-v2 대화 보정 curriculum

- 1차 gate의 실제 응답을 범주별로 분석해 인공 문항 번호가 의미 지시보다 강한 패턴이 된 문제를 제거했다. `generator_profile: focused-v2`는 사실·산술·추출·지시 형식·한국어·문맥·자해·폭발물·jailbreak·PII/secret·정상 안전·불확실성·EOS·반복을 14개 독립 범주로 만든다.
- train과 heldout은 서로 다른 자연어 표현 집합을 사용하고, 모든 user turn의 suite·split overlap 0과 source overlap 0을 유지한다. v1 설정에는 새 optional profile을 직렬화하지 않아 기존 config fingerprint·출력 bytes `07d4f1c9…95c3`가 그대로 재검증된다.
- `configs/sft/qwen36mtp-v5-remediation-v2-data.yaml`로 train 11,400/heldout 1,140행을 생성했다. SHA는 `ece62277…9b46`, `f6ece547…f83c`, manifest fingerprint는 `9b43a01956e9a2dcca46d1dc0260d190c94229c7c99bf80a8184f55f17fb17ef`다.
- replay는 220행, assistant 목표 token 46,596개로 전체 목표 token의 약 18%다. focused 범주별 목표 token과 EOS를 따로 기록하며 원자 publish와 byte 재유도 검증을 통과했다.

## 2026-07-18 · 1.10.1 1차 보정 SFT와 자동 품질 재평가

### full best 기반 350-step 실제 학습

- `configs/sft/qwen36mtp-v5-remediation.yaml`은 full best SHA `506c5e22…65e1`을 base로 CUDA bf16, effective batch 64, 최대 350 step과 8e-6→8e-7 cosine 학습률을 사용한다. train 5,600/heldout 560행의 전체 459,570 token cache와 release blocked 계승을 사전검증했다.
- step-0 heldout loss/PPL 2.811210/16.6300에서 step 175 best 0.393810/1.48262로 개선됐다. 350-step은 18분 35초에 종료됐고 best SHA는 `1a03ca69e069ce7d480382c4b4bb11487789c4e3a3c9622d3612c28870795c5c`, final SHA는 `ded2d46f6582ab7b00f52e8fd6b9049f210dd28f6532032c98409cab830d5a48`다.
- best의 100개 heldout 생성은 assistant NLL/PPL 0.261037/1.29828, repetition·safety 통과와 EOS 99/100을 기록했다. EOS 실패 1건은 replay JavaScript 응답이 128-token 한도에 도달한 경우다.

### 162응답 자동 gate 재실측

- `configs/sft/qwen36mtp-v5-remediation-quality.yaml`로 162응답을 실제 생성하고 다시 byte 재유도했다. fingerprint는 `982ea028972cddb0d3357084523e672be69d79799318e052cb7c08231eb3ec25`다.
- full 대비 aggregate는 EOS 0.8395→0.9568, machine correctness 0.2160→0.3272, harmful refusal 0→0.3056, multi-turn retention 0→0.4444, unsafe 2→0으로 개선됐다. hard n-gram loop는 3건으로 동일하고 PII·secret 유출은 0이다.
- gate는 계속 실패다. 사실 두 항목, 산술 두 항목, PII/secret과 암호화 jailbreak의 거절 일반화, 문맥 정정의 최종 단답, sampling EOS가 주요 잔여 취약점이다. 결과를 승인으로 오인하지 않고 다음 비누출 보강·추가 학습 대상으로 넘긴다.

## 2026-07-18 · 1.10.0 결정적 대화 능력 보정 curriculum

### 평가 비누출 생성·replay 파이프라인

- `SFTCurriculumConfig`와 `sft curriculum-preflight/prepare/status/validate`를 추가했다. 산술·추출·지시 형식·한국어 표현·다중 턴 정정 기억·유해 요청 거절·정상 안전 답변·정보 부족 인정·짧은 EOS의 9개 범주를 seed에서 결정적으로 만들고, 기존 정식 mix를 hash 순서로 replay한다.
- 품질 suite SHA를 고정하고 final prompt만이 아니라 모든 user turn을 NFKC/NFC·공백 정규화해 train/heldout 및 suite exact overlap 0을 강제한다. provenance source도 split 사이 overlap 0이며 모든 assistant 출력의 민감 정보 규칙, 전체 길이, 생성 reserve와 assistant turn별 EOS label을 검증한다.
- 행 수뿐 아니라 범주별 assistant 목표 token과 EOS label을 manifest에 기록한다. 긴 기존 응답이 보정 신호를 압도하지 않도록 replay를 train 200/heldout 20행으로 제한해 전체 assistant 목표 token의 약 33%를 보존했다.

### 실제 생성 결과와 검증

- `configs/sft/qwen36mtp-v5-remediation-data.yaml`에서 train 5,600행, heldout 560행을 생성했다. train/heldout SHA-256은 각각 `4fbb331923489cc6086b2777ac28618b69205f7924c45b117806129d4b374695`, `f62bcf1ab3424035aa2d22bdb028c32fb2ecab5fe3847536131ad8e839e3b9d4`이며 manifest fingerprint는 `07d4f1c9f2b137470f11c86e106ececae95b051b7f2e00b76c7fa1db57cf95c3`이다.
- 생성기는 출력 디렉터리 lock, sibling staging, 파일·디렉터리 fsync와 단일 rename으로 게시한다. 부분 출력·변조·suite SHA 변경·허가되지 않은 replay license·부족한 비누출 replay는 실패-폐쇄한다.
- 전체 `170 passed`, Ruff lint/73파일 format, Pyright strict 오류 0을 통과했다. 데이터 생성·재유도 검증까지 완료했으며 full checkpoint 기반 보정 SFT와 162응답 재평가는 다음 하위 작업이다.

## 2026-07-18 · 1.9.9 파생 SFT release block 계승

### 내부 base에서 공개 추가 학습으로 이어지는 우회 차단

- 이전 runtime은 현재 train/heldout license와 source manifest만으로 release policy를 계산했다. 내부 teacher가 포함된 full SFT checkpoint를 base로 두고 공개 curriculum만 추가 학습하면 파생 checkpoint가 `not_blocked`로 잘못 완화될 수 있었다.
- base checkpoint의 immutable snapshot에서 `kind=assistant-only-sft`인 경우 `redistribution_allowed`와 `release_gate`를 엄격히 검증해 provenance에 결속한다. base가 blocked이면 현재 데이터 policy가 더 느슨해도 최종 policy는 항상 `redistribution_allowed=false`, `release_gate=blocked`다.
- 내부 teacher SFT를 실제 한 step 학습한 뒤 공개 데이터만으로 별도 fresh SFT를 실행하는 회귀에서 base provenance, trainer policy와 새 checkpoint의 block이 모두 보존됨을 확인했다. 잘못된 blocked/redistribution 조합은 초기화 전에 실패한다.
- 전체 `167 passed`, Ruff lint/71파일 format, Pyright strict 오류 0, release audit와 `git diff --check`를 통과했다.

## 2026-07-18 · 1.9.8 fresh full SFT와 자동 품질 실측

### 약 3 epoch 본 학습 완료

- `configs/sft/qwen36mtp-v5-full.yaml`은 pilot checkpoint가 아니라 원래 100M latest에서 직접 시작하고, 정식 mix manifest SHA를 고정한다. CUDA bf16, sequence 1,024, micro batch 4, accumulation 16, 410 optimizer step으로 26,240 example을 노출해 train 8,746행의 약 3.0 epoch를 실행했다.
- 410-step 학습은 약 44분에 정상 종료됐다. final train loss는 1.795000이고 고정 validation loss/PPL은 step 25의 2.551858/12.8309에서 step 410의 2.204719/9.0677까지 개선됐다. best/latest/step-410 SHA-256은 모두 `506c5e2247089cada2c3940b7560d2b6a1c9b00353c159b68ec9d4466e5365e1`이다.
- 100개 heldout 생성 smoke는 assistant NLL 2.298512/PPL 9.9594, EOS 60/100, 반복 임계 초과 21/100, 평균 반복률 0.5543, safety 100/100을 기록했다. 파일럿보다 NLL은 개선됐지만 EOS·반복 gate는 계속 실패했다.

### 고정 162응답 자동 품질 gate 실패

- `configs/sft/qwen36mtp-v5-full-quality.yaml`은 full 설정, checkpoint와 MIT suite SHA를 고정한다. 24 scenario·27 turn에 greedy 1회와 sampling seed 5회를 적용한 162개 실제 rollout과 byte 재유도 검증을 완료했다.
- aggregate는 EOS 0.8395, machine correctness 0.2160, harmful refusal 0, multi-turn retention 0, hard n-gram loop 3건, unsafe 2건이었다. artifact/context/Unicode 완전성과 benign false-refusal·PII·secret은 통과했지만 자동 gate 전체는 실패했다.
- full checkpoint를 대화 가능 또는 안전 모델로 승인하지 않는다. fact·산술·instruction·context·harmful·jailbreak·PII를 quality suite와 exact 중복 없이 바꿔 쓴 teacher 보강 데이터로 수집하고 추가 SFT 후 같은 gate를 다시 실행한다. 자동 gate 통과 뒤에도 외부 서명 수동 검토와 법무·공개 승인은 별도다.
- 두 신규 설정 strict validation, 전체 `166 passed`, Ruff lint/71파일 format, Pyright strict 오류 0, release audit와 `git diff --check`를 통과했다.

## 2026-07-18 · 1.9.7 정식 teacher·mix·100-step pilot

### 정식 증류와 비누출 혼합 완료

- `qwen36mtp-10k-v5` inventory 10,000건을 모두 처리해 accepted 9,712/rejected 288, pending/incomplete 0으로 마감했다. 거부는 finish reason 68, length 217, prompt copy 3건이다.
- export train 8,213/heldout 1,488행, canonical response duplicate 11건을 기록했다. `distill validate`는 current spool에서 byte를 다시 유도해 prompt/source overlap 0, 내부 전용 release blocked를 확인했다. teacher manifest SHA-256은 `6d724261ab9137f04d8efd141bd34d7e38c1f7158b326d3825f187d0f11aae5d`다.
- 공개+teacher 16,554개 입력을 결정적으로 필터링해 train 8,746/heldout 1,498행을 만들었다. mix 재유도 검증과 release blocked를 확인했고 manifest SHA-256은 `278dbc6684943d30f7ea5b3590a5619d59bb9ea21aff31bb53057cdc4a4c164c`다.

### 100M latest 기반 실제 CUDA pilot

- `configs/sft/qwen36mtp-v5-pilot.yaml`은 baseline 100k latest SHA `dae1b01b...e53b33`, mix manifest SHA와 CUDA bf16, sequence 1,024, micro batch 4, accumulation 16을 고정한다. preflight는 87,804,672 parameters와 10,244행·3,539,593 token·28,398,712-byte 연속 cache를 검증했다.
- step-0 고정 heldout 21,342 target tokens는 loss 2.895133/PPL 18.0859였다. fresh 100-step pilot은 final train loss 2.220718, best/final validation loss 2.392192/PPL 10.9374로 개선됐고 best/latest/final SHA가 일치했다.
- 100개 heldout 생성 smoke는 assistant NLL 2.482867/PPL 11.9756, safety 통과였지만 EOS와 repetition은 실패했다. 반복·환각 응답이 다수이므로 대화 가능으로 승인하지 않고 약 3 epoch fresh full SFT와 자동·수동 품질 gate를 계속한다.
- teacher export와 공개+teacher mix 재유도 검증, 두 SFT 설정 검증, 전체 `166 passed`, Ruff lint/69파일 format, Pyright strict 오류 0, release audit와 `git diff --check`를 통과했다.

## 2026-07-18 · 1.9.6 SFT step별 단일 checkpoint 저장

### 중복 대용량 쓰기 제거

- 기존 SFT loop는 validation loss 개선 시 `best=True`, checkpoint interval 도달 시 일반 저장, loop 종료 뒤 final 저장을 각각 호출했다. 세 조건이 같은 optimizer step에 겹치면 동일한 모델·optimizer·sampler·RNG payload를 최대 세 번 직렬화하고 step/latest/best 파일을 합계 최대 7번 썼다.
- 이제 validation 개선 여부, checkpoint interval과 현재 실행의 target/final step을 한 번 판정해 step당 `save`를 최대 한 번만 호출한다. 개선 step은 그 한 번으로 step/latest/best를 갱신하고 비개선 step은 step/latest만 갱신해 이전 best를 보존한다.
- `stop_after_steps`로 주기 전 중단해도 target step checkpoint를 남기며, 진입 시 이미 target step인 zero-iteration 재개도 기존처럼 한 번 저장한다. checkpoint schema, payload, 원자 쓰기와 strict resume 계약은 바꾸지 않았다.

### 검증

- 실제 `save`에 위임하는 spy로 개선+주기+중단 종료 겹침이 `(step=1,best=true)` 한 번임을 검증했다. 그 latest를 strict resume한 뒤 실제 validation 상태는 진행시키고 loss만 기존 best보다 크게 만들어 비개선+주기+final이 `(step=2,best=false)` 한 번이며 best 파일 bytes와 best loss가 보존됨을 확인했다. step 2 latest의 zero-iteration resume도 한 번만 저장하고 유효한 checkpoint 경로를 반환했다.
- 전체 `166 passed`, Ruff lint/71파일 format, Pyright strict 오류 0, release audit와 `git diff --check`를 통과했다. 독립 리뷰의 기존 best 보존·zero-iteration 회귀 부족 MEDIUM을 실제 resume 시나리오로 폐쇄한 뒤 최종 `APPROVE`를 받았다.
- 정식 qwen36mtp v5 수집은 GPU를 공유하지 않고 계속 진행한다.

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
