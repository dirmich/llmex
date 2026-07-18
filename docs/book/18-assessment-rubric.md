# 18. 학습 평가, 해설과 capstone rubric

이 장은 코드 실행 성공과 개념 이해를 구분해 평가한다. 정답 코드를 복사하지 않고, 먼저 말이나 그림으로 불변식을 설명한 뒤 테스트와 artifact로 증명한다.

## 학습 목표

- 자신의 선수 지식과 적절한 진입 장을 판정한다.
- 장별 핵심 불변식을 말과 실행 증거로 설명한다.
- capstone을 기능·재현성·무결성·해석으로 나누어 평가한다.

## 선행지식

평가하려는 장을 직접 읽고 최소 한 번 해당 smoke 또는 검증 명령을 실행해야 한다. 실행하지 않은 장은 수치 점수 대신 미실행으로 표시한다.

## 시작 진단

각 문항을 `설명 가능 / 예를 보면 가능 / 아직 모름`으로 표시한다.

1. 파일 경로와 파일 내용 SHA가 왜 다른 식별자인가?
2. train/heldout split을 row 순서로 만들면 재정렬 때 어떤 문제가 생기는가?
3. causal mask가 막아야 하는 tensor 위치를 그릴 수 있는가?
4. assistant-only SFT에서 user token label을 `-100`으로 만드는 이유는 무엇인가?
5. 자동 품질 점수와 독립 수동 승인이 서로 대체되지 않는 이유는 무엇인가?

세 문항 이상이 `아직 모름`이면 00~02장을 먼저 진행한다. 3번이 어렵다면 05장, 4~5번이 어렵다면 09~13장을 순서대로 읽는다.

## 장별 exit ticket

### 00~04장: 기반·데이터·토크나이저

1. config fingerprint가 어떤 입력을 봉인하고 어떤 입력은 별도 SHA로 남겨야 하는지 설명한다.
2. normalized content hash가 attribution ID를 대체할 수 없는 이유를 설명한다.
3. tokenizer manifest를 바꾸지 않고 packed shard만 다시 만들 때 허용·거부 조건을 제시한다.

통과 기준: 각 답에 정상 사례 하나, 실패 사례 하나, 관련 artifact field 하나가 있어야 한다.

### 05~08장: 모델·학습·평가

1. GQA의 Q head 수와 KV head 수가 다를 때 tensor shape 변화를 적는다.
2. 완전 재개 checkpoint의 상태를 여덟 범주 이상 열거한다.
3. canary 입력이 없을 때 0점이 아니라 미실행 실패여야 하는 이유를 설명한다.

통과 기준: 수식/shape, 재개 parity test, 평가 JSON field를 각각 근거로 든다.

### 09~13장: 증류·혼합·SFT·품질

1. 요청 ID가 prompt text만으로 만들어지면 어떤 provenance collision이 생기는가?
2. heldout 우선 혼합이 train 우선 혼합보다 누출 차단에 유리한 이유를 설명한다.
3. 평균 EOS 성공률이 높아도 scenario worst-case gate가 실패해야 하는 예를 만든다.

통과 기준: request/source SHA, prompt/source overlap, profile/scenario 통계를 사용해 답한다.

### 14~17장: 공개·종합

1. wheel checksum, SBOM, provenance statement가 각각 무엇을 증명하는가?
2. GGUF parity가 미구현인 상태에서 문서가 할 수 있는 주장과 할 수 없는 주장을 나눈다.
3. 57개 모듈 중 외부 부작용을 소유하는 경계를 찾아 실패-폐쇄 검사를 제시한다.

통과 기준: 실제 파일·명령·미구현 경계를 정확히 인용한다.

## 연습문제 채점 원칙

| 유형 | 기본 점수 | 만점 조건 |
|---|---:|---|
| 계산·shape | 5 | 수식, 차원, 경계값과 단위가 모두 맞음 |
| 코드 | 10 | 정상·실패·변조 테스트와 정적 품질 gate 통과 |
| 설계 | 10 | 대안, 선택 이유, 실패 모드, 관찰 가능한 증거 제시 |
| 운영 | 10 | 재현 명령, 입력/설정/artifact SHA, rollback 또는 resume 포함 |

답이 맞더라도 SHA나 실행 범위를 생략하면 재현성 점수를 주지 않는다. 테스트를 통과해도 실패-폐쇄 이유를 설명하지 못하면 개념 점수를 주지 않는다.

## Capstone 100점 rubric

| 영역 | 배점 | 필수 증거 |
|---|---:|---|
| 기능 | 40 | 데이터→tokenizer→model→train→eval 또는 chat→SFT→quality 실제 명령 성공 |
| 재현성 | 25 | Git commit, config fingerprint, 입력·artifact SHA, fresh run manifest |
| 무결성 | 20 | 변조 실험 3개, split overlap 0, checkpoint resume parity, 실패-폐쇄 결과 |
| 해석 | 15 | loss/PPL/반복/EOS 수치의 범위와 미실행 항목, 남은 위험 설명 |

다음 중 하나라도 없으면 총점과 관계없이 미완료다.

- 데이터 license와 provenance
- tokenizer·base checkpoint·SFT source manifest 결속
- 중단·재개 검증
- 평가 입력과 checkpoint SHA
- 외부 미실행/미승인 항목의 명시

## 필수 변조 실험

1. config의 한 값을 바꾸고 기존 artifact 재사용이 거부되는지 확인한다.
2. checkpoint 또는 manifest 한 byte를 바꾸고 strict validate가 거부하는지 확인한다.
3. heldout prompt/source를 train에 복제하고 mix 또는 contamination gate가 거부하는지 확인한다.

원본 artifact를 직접 훼손하지 말고 임시 복사본에서 수행한다. 각 실험은 예상 exit code, 실제 stderr, 훼손 전후 SHA를 제출한다.

## 해설 작성 형식

```markdown
### 문제 번호

- 결론:
- 사용한 불변식:
- 반례 또는 실패 사례:
- 실행 명령:
- 관찰한 JSON field:
- artifact SHA:
- 아직 증명하지 못한 것:
```

이 형식은 “정답처럼 보이는 설명”과 실제 검증을 분리한다. 교재의 모범 해설도 같은 형식을 사용하며, 장기 GPU 수치나 외부 승인 결과는 실행 artifact 없이 정답으로 고정하지 않는다.
