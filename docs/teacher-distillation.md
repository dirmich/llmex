# teacher 증류 데이터 실행 가이드

LLMEX 1.22.18의 teacher 증류 경로는 로컬 OpenAI 호환 서버에서 한국어·영어·일본어 응답과 번역을 수집해 assistant-only SFT 입력을 만든다. 정식 `runs/distill/qwen36mtp-10k-v5`는 현재 CLI에서 10,000건을 모두 처리해 accepted 9,712/rejected 288로 완료했고 export·재유도 validate를 통과했다. 새 자연대화 수집은 exact hash와 의미 조합 범위뿐 아니라 source 결속 목표 언어·응답 계약도 검증한다. teacher 출력과 이를 포함한 가중치는 계속 내부 전용이며, 해당 checkpoint를 base로 추가 학습해도 release block은 해제되지 않는다.

1.22.15 조기 감사에서는 Gemma가 실시간 혼잡도를 직접 알 수 없다고 말한 뒤에도 지도 서비스의 혼잡도 정보를 참고하거나 제공 정보를 보라고 답하는 우회를 확인했다. 형태소 기반 긍정·부정 판정과 provider 경계 열거는 활용형, 인용, wrapper, 조사, target bait에서 양방향 오류가 반복됐다. 1.22.18은 uncertainty 라벨을 plain text로 제한해 HTML·Markdown·entity·bidi 표면을 전량 실패-폐쇄하고, 평문은 NFKC·Cf·한글 filler를 정규화한 compact·한글 전용 projection에서 지도·내비게이션·map 계열과 혼잡·붐빔·사람이 많음 계열이 함께 있으면 극성·문장 경계와 무관 `quality:unsupported_realtime_claim`으로 격리한다. `지도자`, `로드맵`, markup이 들어간 안전 응답까지 의도적으로 격리하는 데이터 손실 정책이며, 지도 언급 없이 공식 홈페이지·주최 측에 확인하라는 plain text 응답은 계속 허용한다. 해당 Gemma 한국어 v2 run은 보존·미export하고 강화 gate로 v3를 fresh 재개한다. Qwen 다국어 v2는 2,000건 중 accepted 662/rejected 1,337/failed 1이며 실패 1건을 해소하기 전 표본 감사와 export를 허용하지 않는다.

## 1.22.14 metadata-v1 응답 품질 gate

natural v1 수집은 Qwen 261/2,000과 Gemma 한국어 251/3,000에서 중단했다. 기존 필터의 `accepted`는 길이·Unicode·반복·prompt-copy만 통과했다는 뜻이며 학습 label 적합성을 뜻하지 않는다. Qwen은 목표 언어 유지와 이름·숫자·용어 번역을, Gemma는 writing 직접 출력과 실시간 정보의 인식론 경계를 실패했다. 두 run은 보존하지만 resume/export/학습 입력 사용을 금지한다.

v2 설정은 `quality_gate_version: metadata-v1`을 사용한다. 생성기가 target language, conversation/translation-only/direct-message/uncertainty mode, 문장 상한, 숫자·entity·핵심 용어 표면형을 typed provenance에 기록하며 inventory가 이를 잃으면 prepare가 실패한다. collector는 새 응답과 기존 spool 재검증에 같은 gate를 적용한다. 따라서 `accepted` 뒤에도 task/category 균등 표본 감사를 통과해야만 export할 수 있다.

```bash
uv run llmex distill preflight --config configs/distill/qwen36mtp-multilingual-natural-2000.yaml
uv run llmex distill collect --config configs/distill/qwen36mtp-multilingual-natural-2000.yaml
uv run llmex distill status --config configs/distill/qwen36mtp-multilingual-natural-2000.yaml
```

pending과 failed가 0인 전체 수집 뒤 다음 명령으로 task/category를 round-robin한 최대 50개 응답을 직접 읽고, 목표 언어·이름·숫자·핵심 용어·번역-only를 확인한 검토자만 `--approve`를 기록한다. Gemma 한국어는 writing이 메시지 한 문장뿐인지, uncertainty가 접근 한계와 실제 확인 경로를 모두 갖는지 별도 확인한다. `sample-audit.json`은 inventory와 전체 accepted spool 집합에 SHA로 결속되므로 부분 수집·누락·미승인·변조·수집 재개 후 stale artifact에서는 export가 실패한다.

```bash
uv run llmex distill audit-sample --config <natural-config.yaml> \
  --reviewer "검토자 식별자" --approve
uv run llmex distill export --config <natural-config.yaml>
uv run llmex distill validate --config <natural-config.yaml>
```

teacher 출력은 `LicenseRef-LLMEX-Internal-Distillation` 내부 전용이다. export manifest는 `redistribution_allowed=false`, `release_gate=blocked`를 강제한다. 수집 성공이나 휴리스틱 필터 통과는 최종 안전성·법무·공개 승인이 아니다.

## 1.22.13 natural source 재준비

expanded 1차 tranche는 teacher 표본에서 결함을 확인한 즉시 기각했다. Qwen 다국어는 1,296/2,000 처리 시점의 accepted 1,271·`prompt_copy` rejected 25, Gemma 다국어는 433/2,000, Gemma 한국어는 369/3,000에서 수집을 중단했다. `Reference`/serial 노출, 부자연스러운 조사와 큰 수치, teacher 답변 본문 중복이 확인됐으며 세 run 모두 export하지 않았다.

첫 natural source도 exact 문장은 달랐지만 train/heldout이 같은 의미 조합을 100% 공유하고 Qwen/Gemma prompt 본문이 의미상 중복됐다. 최종 생성기는 `prompt_index`에 전단사 순열을 적용해 split과 teacher마다 분리된 조합 범위를 선택한다. 독립 전수 감사에서 지시문을 제거한 canonical 본문의 모든 task/category 교집합이 0이고 장소·물체·스타일 축이 양 split에 모두 분포함을 확인했다.

- 다국어 natural-v3: Qwen SHA `3f4048811d17f9d026b49ff5a9a40e96f90cd7e9e6af9522c7478e2f24faac64`, Gemma SHA `04f7607d87a9fa4b56d950ca787d2b9c9f391a2472013a5a3ef6166189b89272`, manifest fingerprint `ff52580ce26acb1a1a966d08c1c08f76b7db5687423a51e3c1667323c46f166d`
- 한국어 natural-v2: SHA `f854929cf83afb168584aa63969479e69a8ca8e9d3e0ff96ea17646062d5c407`, manifest fingerprint `410a98b4330663213064d6f851e44facce9df421b276bb2d0c218af08d61cff8`

새 수집 설정과 실제 prepare 결과는 다음과 같다.

| 설정 | train/heldout | inventory fingerprint |
|---|---:|---|
| `configs/distill/qwen36mtp-multilingual-natural-2000.yaml` | 1,410/590 | `b5f44db90884f1f3232aacbc80477ced5304538227e5d73c0eeebd9353982dbe` |
| `configs/distill/gemma4-multilingual-natural-2000.yaml` | 1,421/579 | `6cb3e358ee4d50c9b7804e82a7cb97e0a54acfc77c3d497071abe2c5dccdc537` |
| `configs/distill/gemma4-conversation-natural-3000.yaml` | 2,167/833 | `c82eb66052990802929eef45364c2d0bbb49a57dff8e8981bc4540b8f5d9e2dd` |

세 inventory는 선택 request가 각각 2,000·2,000·3,000개로 모두 고유하고 Wikipedia 보충·prompt/source overlap이 0이다. release는 차단돼 있으며 `localhost:8081/v1` Qwen과 `macmini:11434/v1` Gemma endpoint preflight도 통과했다. 다음 명령을 각 설정에 대해 순서대로 실행한다.

```bash
uv run llmex distill collect --config <natural-config.yaml>
uv run llmex distill status --config <natural-config.yaml>
uv run llmex distill export --config <natural-config.yaml>
uv run llmex distill validate --config <natural-config.yaml>
```

세 export가 완료되면 통합 suite와 의미·exact 비누출 mix를 만들고 100M latest에서 SFT한다. 60 scenario·390응답과 suite 밖 자연대화 smoke를 모두 통과한 checkpoint만 로컬 HF·GGUF와 llama.cpp parity로 넘기며 Hugging Face 업로드는 하지 않는다.

## 1.22.11 대규모 자연대화 수집

기존 한국어 v10 source는 11,880행 중 고유 prompt가 2,294개뿐이라 target만 10,000으로 늘리면 Wikipedia 질문 7,706개가 섞인다. 다음 명령은 별도 자연대화 inventory 10,000개와 teacher별 다국어 6,000개를 먼저 생성하므로 Wikipedia 보충을 사용하지 않는다.

```bash
uv run llmex data korean-conversation-prompts \
  --output data/chat/korean-conversation-teacher-prompts-expanded-v1 \
  --train-rows-per-category 800 --heldout-rows-per-category 200
uv run llmex data multilingual-prompts \
  --output data/chat/multilingual-teacher-prompts-expanded-v2 \
  --train-rows-per-task 800 --heldout-rows-per-task 200 --profile expanded-v2

uv run llmex distill prepare --config configs/distill/qwen36mtp-multilingual-expanded-6000.yaml
uv run llmex distill prepare --config configs/distill/gemma4-multilingual-expanded-6000.yaml
uv run llmex distill prepare --config configs/distill/gemma4-conversation-10000.yaml
uv run llmex distill preflight --config configs/distill/qwen36mtp-multilingual-expanded-6000.yaml
uv run llmex distill preflight --config configs/distill/gemma4-multilingual-expanded-6000.yaml
uv run llmex distill preflight --config configs/distill/gemma4-conversation-10000.yaml
```

실제 prepare 결과는 Qwen 다국어 train/heldout 4,338/1,662, Gemma 다국어 4,334/1,666, Gemma 한국어 7,239/2,761이며 각 target 6,000·6,000·10,000, 고유 prompt target 일치, Wikipedia 보충 0, prompt/source overlap 0이다. 세 수집은 서로 다른 run directory에 재개 가능하게 기록한다. 완료 뒤 각각 `status → export → validate`를 실행하고, 새 SFT curriculum이 통합 품질 suite와 모든 user turn overlap 0을 증명하기 전에는 학습에 사용하지 않는다.

첫 품질 피드백은 같은 immutable inventory에서 한국어 3,000·Qwen/Gemma 다국어 각 2,000을 선택하는 1차 tranche로 얻는다. `configs/distill/gemma4-conversation-3000.yaml`, `qwen36mtp-multilingual-expanded-2000.yaml`, `gemma4-multilingual-expanded-2000.yaml`을 prepare→preflight→collect→export→validate 순서로 실행한다. 실패 시 full run의 기존 spool을 `resume`하며 tranche spool을 full run에 복사하지 않는다.

## macmini Gemma 4 대화 증류 결과

`configs/distill/gemma4-conversation-2200.yaml`은 `http://macmini:11434/v1`과 `gemma4-26b-a4b-uncensored-hauhaucs-balanced`를 사용한다. `allowed_endpoint_hosts`에는 `macmini`만 등록하고, 자연스러운 한국어·실시간 한계·민감정보/위험 요청 거절을 system prompt에 고정했다.

```bash
uv run llmex distill status --config configs/distill/gemma4-conversation-2200.yaml
uv run llmex distill export --config configs/distill/gemma4-conversation-2200.yaml
uv run llmex distill validate --config configs/distill/gemma4-conversation-2200.yaml
```

2,200건을 3,085.164초에 처리해 accepted 2,145, rejected 55, pending 0으로 완료했다. 거부는 length 47, 개인정보 패턴 6, 비정상 finish reason 2건이다. canonical 응답 중복 489개를 제거한 export는 train 1,160·heldout 496행이며 prompt·upstream source overlap은 모두 0이다.

- config fingerprint: `78e7c381b0aa422dd8f7dbfc38784079c4f383092e779e9534e91120ad76c376`
- inventory fingerprint: `24edbb65f64cfb1634111a69e6b53ef5f74cadeed5510e39a601b25898a74b3b`
- train SHA-256: `489d335ebe35569b87bc8bf6793d38f02812d57e02e6d4e99dccc2f5055818af`
- heldout SHA-256: `3767797e377e451c20be333f74e54fb65474976e028096393cf8098d97b9c0aa`
- manifest SHA-256: `824329dd4fd49571f392660dfe83360877c0a922b5c23a89e575d1835bfad601`

표본에는 자연 대화, 확인할 수 없는 실시간/문서 정보의 한계 고지와 안전 거절이 포함됐다. 일부 답변은 요구보다 장황하거나 답변 예시를 메타적으로 제시하므로, 이 export만으로 대화 가능성을 승인하지 않고 Qwen/public replay와 통합 품질 gate를 함께 사용한다.

## 영어·일본어 대화와 번역 증류

```bash
uv run llmex data multilingual-prompts
uv run llmex distill prepare --config configs/distill/qwen36mtp-multilingual-1080.yaml
uv run llmex distill prepare --config configs/distill/gemma4-multilingual-1080.yaml
uv run llmex distill preflight --config configs/distill/qwen36mtp-multilingual-1080.yaml
uv run llmex distill preflight --config configs/distill/gemma4-multilingual-1080.yaml
uv run llmex distill collect --config configs/distill/qwen36mtp-multilingual-1080.yaml
uv run llmex distill collect --config configs/distill/gemma4-multilingual-1080.yaml
uv run llmex distill export --config configs/distill/qwen36mtp-multilingual-1080.yaml
uv run llmex distill export --config configs/distill/gemma4-multilingual-1080.yaml
uv run llmex distill validate --config configs/distill/qwen36mtp-multilingual-1080.yaml
uv run llmex distill validate --config configs/distill/gemma4-multilingual-1080.yaml
```

inventory는 영어 대화, 일본어 대화, 한→영, 영→한, 한→일, 일→한의 6개 task를 teacher별 train 900·heldout 180으로 균형 배치한다. Qwen과 Gemma prompt 문구·source ID는 분리되어 exact overlap이 0이다. Qwen 요청도 client가 `chat_template_kwargs.enable_thinking=false`를 고정하므로 짧은 출력 예산이 내부 추론에 소진되지 않는다.

- Qwen inventory SHA: `2669e3e686de7e9acb270fb0c8dc716b55d8d654c53ad3904817c9e7e3035afc`
- Gemma inventory SHA: `ad0afe439dcce1c04f42728d41057ef14e5061594da4b311a2fa25f3e97d388c`
- 다국어 suite SHA: `6dea06376c0c7558551d28d507a001e755890934c2c12c5d64f54329b5cad8eb`

2026-07-18 실제 실행 결과:

- Qwen36mtp: 1,080요청 중 accepted 1,070, prompt-copy rejected 10, pending 0, 927.510초. canonical 중복 1건 제거 후 train 799(`935c9c03…0fef8`)·heldout 270(`d750f23f…0db4`), manifest `12b4a893…c459`.
- Gemma4: 1,080요청 전량 accepted, pending 0, 930.017초. canonical 중복 111건 제거 후 train 733(`c1382df7…9669`)·heldout 236(`117e55f1…33d2`), manifest `c52fa324…c7e`.
- 양쪽 모두 prompt overlap 0, upstream source overlap 0, `release_gate=blocked`를 현재 spool에서 재유도했다.

현재 tokenizer는 영어·일본어 모두 unknown token이 0이지만 일본어가 약 1.42 token/문자로 비효율적이다. 기존 100M checkpoint의 embedding shape를 유지하기 위해 tokenizer를 바꾸지 않고 짧은 1024-token 대화·번역만 학습한다. 향후 tokenizer 재학습은 다국어 사전학습부터 별도 세대로 수행해야 한다.

## 실행 전 확인

저장소 루트에서 잠긴 환경과 설정을 확인한다.

```bash
uv sync --frozen
uv run llmex config validate configs/distill/qwen36mtp-10k.yaml --kind distillation
uv run llmex distill preflight --config configs/distill/qwen36mtp-10k.yaml
```

preflight는 `GET /v1/models`에서 `qwen36mtp`가 실제 제공되는지 확인한다. 2026-07-17 실행 결과는 `status=ok`였으며 endpoint와 model이 설정과 일치했다.

요청은 `POST /v1/chat/completions`로 전송하며 다음 조건을 고정한다.

- system prompt: `질문에 한국어로 직접 답하세요. 내부 추론은 쓰지 말고, 핵심만 1~5문장과 500자 이내로 완결하세요. 불필요한 서론·목록·반복을 피하고 모르면 추측하지 마세요.`
- `temperature=0.2`, `max_tokens=512`
- `chat_template_kwargs.enable_thinking=false`
- 응답 role은 `assistant`, `finish_reason`은 `stop`, `reasoning_content`는 비어 있어야 한다.

## 실제 설정

`configs/distill/qwen36mtp-10k.yaml`의 주요 값은 다음과 같다.

| 항목 | 값 |
|---|---|
| schema | 2 |
| endpoint / model | `http://localhost:8081/v1` / `qwen36mtp` |
| run | `runs/distill/qwen36mtp-10k-v5` |
| 요청 수 / heldout | 10,000 / 1,000 basis points |
| 동시성 / 요청률 | 4 / 초당 1.5건 |
| timeout / 최대 응답 | 120초 / 1,048,576 bytes |
| 최대 시도 / retry 상한 | 5회 / 60초 |
| 응답 길이 | 8–500자 hard gate |
| repetition / prompt copy 상한 | 0.65 / 0.9 |
| 출력 라이선스 | `LicenseRef-LLMEX-Internal-Distillation` |

source chat 파일과 Wikipedia 보충 원천은 config에 명시한다. 원천이 사라지거나 내용이 달라지면 기존 v3/v4/v5 run을 임의 재생성하지 말고 provenance와 fingerprint를 다시 검토한다.

## pilot 교정과 최종 결과

- v3 정식 수집은 초반 5건에서 accepted 1건, `finish_reason_not_stop` rejected 4건을 확인한 즉시 안전 중단했다. v3 inventory·state·spool은 보존한다.
- v4/v4b는 별도 pilot run에서 prompt와 copy 오탐을 교정했다. 질문을 자연스럽게 요약한 정상 응답은 허용하면서 원문의 20%, 50%, 79% 연속 발췌와 한 단어만 바꾼 근접 복사는 `prompt_copy`로 차단한다.
- 최종 `runs/distill/qwen36mtp-pilot-v5` 30건은 prepare, preflight, collect, export, validate를 모두 통과했다.

| v5 pilot 항목 | 결과 |
|---|---:|
| accepted | 28/30, 93.3% |
| rejected | `length` 1, `finish_reason_not_stop` 1 |
| failed / incomplete / duplicate | 0 / 0 / 0 |
| 누적 시간 / 실효 처리율 | 122.0626초 / 0.245775 RPS |
| 상각 시간 | 요청당 4.069초 |
| accepted 길이 최소/평균/최대 | 67 / 226.0 / 357자 |
| export train/heldout | 25 / 3 |
| overlap / release | 0 / blocked |

30건 pilot은 경로 검증과 처리율 추정 근거이며 10k 전체 품질이나 최종 safety gate를 대신하지 않는다.

## inventory 준비 결과

```bash
uv run llmex distill prepare --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill status --config configs/distill/qwen36mtp-10k.yaml
```

정식 v5 inventory 실측은 다음과 같다.

| 항목 | 결과 |
|---|---:|
| source chat raw | 6,853 |
| 고유 prompt / 중복 제거 | 5,813 / 1,040 |
| upstream heldout 보존 | 630 |
| Wikipedia 보충 | 4,187 |
| 총 inventory | 10,000 |
| train / heldout | 8,445 / 1,555 |
| prompt·upstream source overlap | 0 / 0 |

- inventory SHA-256: `b6a02b20b76f698a7b292b54faf5c46c65fce246ff2cd79a21be99274bc42ea1`
- inventory fingerprint: `46248ba32985f7102a4d401dfa019c43884011c7fb080014d6888e8e20593e7b`
- config fingerprint: `4a3eea14ca4a5bf43eea8c0302043a13da8ea848f4c757b6375637363417bb9d`
- 최종 status: completed 10,000, accepted 9,712, rejected 288, pending 0
- export train/heldout: 8,213 / 1,488
- export train SHA-256: `35f6b6d1b5fa24e46f4cc3e211f6dd49d138038f0965805d253551ce3c1090de`
- export heldout SHA-256: `1767b07d5ff5c2aaf68a346527fdbf89c2cbfd97f820a9afd88d7a66fc2e34cf`
- export manifest SHA-256: `6d724261ab9137f04d8efd141bd34d7e38c1f7158b326d3825f187d0f11aae5d`
- pilot 실효 RPS 단순 환산 예상 시간: 약 11.3시간. 실제 시간은 teacher 부하, 응답 길이와 retry에 따라 달라질 수 있다.

1.20.2에서 내부망 teacher allowlist를 추가할 때 빈 `allowed_endpoint_hosts`까지 fingerprint 입력에 넣으면, 그 필드가 없던 과거 loopback run의 fingerprint가 달라진다. 1.21.3은 빈 allowlist를 legacy 표현으로 정규화해 기존 `localhost:8081` Qwen run을 현재 CLI로 그대로 검증하고, `macmini`처럼 비어 있지 않은 allowlist는 계속 fingerprint에 결속한다.

upstream heldout 630건은 distill heldout에 그대로 보존한다. 나머지는 seed 기반 결정적 분할을 사용하며 train과 heldout의 prompt 및 upstream source가 겹치면 중단한다.

## 실제 수집과 진행률

```bash
uv run llmex distill collect --config configs/distill/qwen36mtp-10k.yaml
```

`collect`는 최대 4개 요청만 동시에 유지하고 전체 요청률을 초당 1.5건으로 제한한다. 408/409/425/429/5xx와 네트워크 실패만 최대 5회 재시도하며 지수 backoff, 결정적 jitter, 유효한 `Retry-After`를 60초 상한 안에서 적용한다. 성공·거부·실패는 요청별 schema 2 JSON spool로 원자 저장된다.

다른 터미널에서 진행률을 확인한다.

```bash
watch -n 10 'uv run llmex distill status --config configs/distill/qwen36mtp-10k.yaml'
```

status는 total/completed/pending/accepted/rejected/failed, progress, 누적 elapsed, effective RPS, ETA, 마지막 성공·오류 시각을 JSON으로 출력한다. 처리 표본이 없으면 ETA는 `null`이며 수집이 진행된 뒤 실제 처리율로 계산한다.

## 중단과 재개

`Ctrl-C` 또는 처리 가능한 예외가 발생하면 완료 future를 먼저 spool에 기록하고 lock과 상태를 정리한다. 강제 종료나 SIGTERM으로 정리 절차를 밟지 못하면 다음 실행이 종료된 PID의 stale lock을 엄격히 검사해 회수한다. 같은 명령 또는 명시적 resume 명령은 검증된 완료 spool을 건너뛰고 pending과 retry가 소진된 failed 항목만 이어서 처리한다.

```bash
uv run llmex distill resume --config configs/distill/qwen36mtp-10k.yaml
```

run lock에는 schema, PID, host와 시작 시각을 기록한다. 같은 host의 살아 있는 PID 또는 해석할 수 없는 lock은 거부하고, 종료된 PID의 stale lock만 inode와 내용을 재확인한 뒤 회수한다. config fingerprint, inventory checksum·fingerprint, request ID/body hash와 spool record hash가 다르면 재개하지 않는다.

## export와 최종 검증

수집 상태가 10,000건 모두 완료된 뒤에만 다음 순서로 실행한다.

```bash
uv run llmex distill export --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill validate --config configs/distill/qwen36mtp-10k.yaml
```

export는 accepted 응답의 canonical 중복을 제거해 다음 파일을 원자적으로 만든다.

- `runs/distill/qwen36mtp-10k-v5/export/train.jsonl`
- `runs/distill/qwen36mtp-10k-v5/export/heldout.jsonl`
- `runs/distill/qwen36mtp-10k-v5/export/manifest.json`

각 행에는 source dataset/license/ID/hash/date, teacher model, request/response/raw-response SHA-256과 내부 전용 라이선스를 보존한다. manifest는 current inventory와 accepted spool ID·record/request/response hash 집합에 결속된다. export 이후 spool을 추가·교체·삭제하거나 stale export를 재사용하면 `validate`가 거부한다. 검증은 current spool에서 export를 다시 유도해 byte/hash 일치, JSONL schema/license, prompt와 upstream source overlap 0, 내부 전용 release gate를 확인한다.

## 공개 instruction과 안전하게 혼합

공개 데이터 자체의 train/heldout canonical prompt overlap은 152개다. 공개 train과 teacher heldout을 함께 비교하면 658개 고유 prompt가 겹치고 공개 train 879행이 영향을 받으므로 export JSONL을 공개 JSONL에 직접 concat하지 않는다.

정식 export와 `distill validate` 완료 뒤 `runs/distill/qwen36mtp-10k-v5/export/manifest.json`의 SHA-256을 새 `SFTMixConfig.expected_teacher_manifest_sha256`에 고정한다. mix preflight/prepare/validate는 teacher manifest와 source JSONL·tokenizer manifest를 결속하고 heldout prompt·원천을 train보다 우선 격리한다. prompt+generation reserve와 전체 chat 길이가 tokenizer 한도를 넘는 행은 제외하며 내부 전용 라이선스의 `redistribution_allowed=false`, `release_gate=blocked`를 SFT checkpoint와 평가까지 계승한다.

```bash
uv run llmex sft preflight-mix --help
uv run llmex sft prepare-mix --help
uv run llmex sft status-mix --help
uv run llmex sft validate-mix --help
```

정식 teacher manifest SHA는 `6d724261ab9137f04d8efd141bd34d7e38c1f7158b326d3825f187d0f11aae5d`다. `configs/sft/qwen36mtp-v5-mix.yaml`의 재유도 검증 결과는 train 8,746/heldout 1,498행, mix manifest SHA `278dbc6684943d30f7ea5b3590a5619d59bb9ea21aff31bb53057cdc4a4c164c`다. exact canonical prompt가 아닌 semantic paraphrase 누출은 contamination 검사와 수동 감사에서 별도로 판정한다.

## 네트워크·비밀정보 안전 경계

- endpoint는 기본적으로 loopback `http` 절대 URL과 `/v1` 경로만 허용한다. 신뢰하는 내부망 teacher는 `allowed_endpoint_hosts`에 정규화된 hostname을 명시한 경우에만 사용할 수 있다. userinfo, query, fragment, 미등록 외부 host와 HTTPS endpoint는 거부한다.
- OpenAI 호환 응답의 `tool_calls`는 빈 배열만 허용한다. 실제 tool call이나 알 수 없는 message 확장 필드는 label 본문으로 해석하지 않고 거부한다.
- 환경의 HTTP/HTTPS/all proxy를 사용하지 않으며 redirect를 추적하지 않는다. Authorization header가 proxy나 redirect 목적지로 전달되지 않는다.
- API key는 `api_key_env`가 지정된 경우에만 환경변수에서 읽고 artifact·오류 문구에 값을 기록하지 않는다.
- teacher가 credential 또는 `Bearer credential`을 echo하면 constant-time 검사로 `secret_leak` 처리하고 응답 본문과 raw/정규화 hash를 spool에 남기지 않는다.
- `Content-Length`와 실제 읽기 모두 `max_response_bytes`를 넘으면 거부한다. 예상하지 않은 message field, role, finish reason, thinking content와 빈 응답도 거부한다.
- 응답 길이, 반복, prompt 복사와 소수 위험 패턴 필터는 `heuristic_pre_filter_not_final_safety_gate`다. 독립 안전 평가와 수동 검토를 대체하지 않는다.

## 이후 순서

저장소 외부 운영 참고 문서 `../knowledge_base/Codex/LLMEX/프로젝트 계획.md`의 확정 결정, 품질 gate와 100M baseline 이후 순서를 참고했다. 실패 run과 산출물을 덮어쓰지 않고 별도 세대로 보존하며 secret이나 개인 절대경로는 기록하지 않는다.

1. 완료된 정식 export와 mix manifest SHA를 변경하지 않는다.
2. EOS·반복 smoke에 실패한 100-step pilot을 full 결과로 오인하지 않는다.
3. 동일 100k latest에서 fresh full SFT를 수행하고 best/latest를 비교한다.
4. 자동 대화 품질 gate 통과 뒤 최소 100개 blind template으로 독립 quality·safety 사람 검토를 실행한다. 수동 gate 코드는 구현됐지만 실제 모델 검토는 아직 미실행이다.
