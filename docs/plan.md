# LLMEX 구현 계획

## 1. 권장 저장소 구조

```text
llmex/
  AGENTS.md
  README.md
  pyproject.toml
  uv.lock
  .env.example
  .gitignore
  Makefile
  0.ref/
    README.md
    SHA256SUMS
    llm_math_book/       # 기반 교재의 읽기 전용 참조 코드
  configs/
    data/sample.yaml
    data/kowiki.yaml
    model/smoke.yaml
    model/baseline-100m.yaml
    train/smoke.yaml
    train/baseline.yaml
  docs/
    README.md
    prd.md
    plan.md
    todo.md
    decisions.md
    data-card.md
    model-card.md
  src/llmex/
    cli.py
    config.py
    paths.py
    data/download.py
    data/extract.py
    data/clean.py
    data/dedup.py
    data/split.py
    data/report.py
    tokenizer/train.py
    tokenizer/evaluate.py
    tokenizer/pack.py
    model/config.py
    model/norm.py
    model/rope.py
    model/attention.py
    model/block.py
    model/lm.py
    train/dataset.py
    train/schedule.py
    train/checkpoint.py
    train/trainer.py
    eval/perplexity.py
    eval/generation.py
    eval/contamination.py
    eval/memorization.py
    inference/generate.py
  tests/
    fixtures/kowiki-sample.xml.bz2
    unit/
    integration/
  scripts/
  data/              # gitignore
  artifacts/         # gitignore
  runs/              # gitignore
```

## 2. 기술 선택

- Python 3.11+
- 패키지 관리: `uv`
- 설정: Pydantic Settings + YAML, CLI override는 Typer
- 모델: PyTorch 2.x, `torch.nn.functional.scaled_dot_product_attention`
- 토크나이저: Hugging Face `tokenizers`
- dump parsing: `mwxml` + `mwparserfromhell` 또는 검증된 WikiExtractor 비교 후 ADR
- 저장: JSONL.ZST 문서 corpus, NumPy memmap token shards
- 품질: pytest, hypothesis, ruff, pyright
- 메트릭: JSONL 필수, TensorBoard 선택
- 대규모 artifact: 로컬 파일/객체 저장소, Git에는 manifest와 checksum만

### DGX Spark 실행 기준

- host: NVIDIA DGX OS, ARM64
- runtime: Docker + NVIDIA Container Runtime (`--gpus=all`)
- image: 실행 시점의 DGX Spark 호환 NGC PyTorch tag를 검증한 뒤 digest까지 고정
- persistence: repository, `data/`, `artifacts/`, `runs/`를 host NVMe에서 bind mount
- IPC: 학습 container에 `--ipc=host` 또는 검증된 `--shm-size` 설정
- network: dump/이미지 pull 단계만 허용하고 학습은 오프라인 실행 가능
- secrets: NGC credential은 Docker credential store, 저장소에는 넣지 않음

최초 검증 예시이며 CUDA image tag는 장비의 현재 driver와 공식 호환성을 확인해 바꿀 수 있다.

```bash
nvidia-smi
uname -m                       # aarch64 확인
docker run --rm --gpus=all \
  nvcr.io/nvidia/cuda:13.0.1-devel-ubuntu24.04 nvidia-smi
```

`nvidia-smi`가 iGPU memory usage를 `Not Supported`로 표시할 수 있으므로 이것을 GPU 미인식으로 오판하지 않는다. 실제 PyTorch CUDA tensor 생성과 matmul로 최종 확인한다.

의존성 버전은 구현 시작일에 공식 문서와 호환성을 확인해 lock한다. 계획 문서에 임의 최신 버전을 고정하지 않는다.

### 기반 교재 코드 참조

선별 원본은 [`0.ref/README.md`](../0.ref/README.md)에 인덱싱되어 있다. 구현자는 관련 모듈을 시작하기 전에 다음 순서로 확인한다.

| 구현 영역 | 우선 참조 |
|---|---|
| tokenizer | `0.ref/llm_math_book/notebooks/ch12_tokenizers.ipynb`, `bench_tokenizer.py` |
| attention/GQA | Ch 14, 15, 27, 31 notebook과 `bench_attention.py` |
| RoPE/position | Ch 16, 31 notebook |
| decoder/GPT | Ch 17, 18, 31 notebook과 `bench_nano_gpt.py` |
| pretraining | Ch 19, 31 notebook과 `bench_training_loop.py` |
| 후속 SFT/LoRA | Ch 32 notebook; MVP 범위 밖 |

`0.ref`는 production dependency가 아니다. `src/llmex`에서 import하지 않고, 필요한 동작을 새 typed 모듈과 독립 테스트로 재구현한다. 구현 PR/commit에는 참고한 파일과 달라진 설계 이유를 남긴다.

무결성 검사:

```bash
cd 0.ref
shasum -a 256 -c SHA256SUMS
```

## 3. CLI 계약

모든 명령은 resolved config, 입력 fingerprint, 출력 manifest를 기록하고 같은 입력에 재실행 가능해야 한다.

```bash
llmex data download --config configs/data/kowiki.yaml
llmex data extract --config configs/data/sample.yaml
llmex data clean --config configs/data/sample.yaml
llmex data dedup --config configs/data/sample.yaml
llmex data split --config configs/data/sample.yaml
llmex data report --config configs/data/sample.yaml

llmex tokenizer train --config configs/tokenizer/bpe-16k.yaml
llmex tokenizer evaluate --config configs/tokenizer/bpe-16k.yaml
llmex tokenizer pack --config configs/tokenizer/bpe-16k.yaml

llmex model inspect --config configs/model/smoke.yaml
llmex train --config configs/experiment/smoke.yaml
llmex eval --run runs/<run-id>
llmex generate --checkpoint runs/<run-id>/checkpoints/latest.pt --prompt "대한민국의 수도는"
```

각 명령은 `--dry-run`, `--force`, `--log-level`을 공통 지원한다. 기존 출력이 있고 fingerprint가 다르면 자동 덮어쓰지 않고 실패한다.

## 4. 데이터 계약

### document JSONL schema

```json
{
  "schema_version": 1,
  "page_id": 123,
  "revision_id": 456,
  "title": "문서 제목",
  "text": "정제된 본문",
  "source_url": "https://ko.wikipedia.org/?curid=123",
  "dump_date": "YYYYMMDD",
  "license": "CC BY-SA / GFDL; verify page-specific notices",
  "sha256": "...",
  "quality": {"chars": 1000, "hangul_ratio": 0.72},
  "split": "train"
}
```

원문 전체를 별도 JSON에 중복 저장하지 않는다. raw XML은 immutable하게 보관하고 정제 데이터가 raw page/revision으로 역추적 가능해야 한다.

### token shard manifest

```json
{
  "schema_version": 1,
  "dtype": "uint16",
  "tokenizer_sha256": "...",
  "corpus_sha256": "...",
  "eos_id": 2,
  "shards": [{"path": "train-00000.bin", "tokens": 10000000, "sha256": "..."}]
}
```

vocab이 65,535를 넘으면 dtype을 자동 검증해 `uint32`를 사용한다.

## 5. 모델 계약

입력 `input_ids: int64[B,T]`, 출력 `logits: float[B,T,V]`, 선택적 `loss`다.

```text
token embedding
-> N x [RMSNorm -> RoPE GQA causal attention -> residual
        RMSNorm -> SwiGLU -> residual]
-> RMSNorm
-> tied LM head
```

필수 불변조건:

- `d_model % n_heads == 0`
- `n_heads % n_kv_heads == 0`
- `T <= max_seq_len`
- causal mask 때문에 위치 t는 t 이후 토큰에 의존하지 않음
- loss는 `logits[:, :-1]`와 `targets[:, 1:]` 비교
- padding을 사용하면 loss ignore index가 적용됨
- RoPE cache는 device/dtype/length에 맞음

## 6. 학습 run 구조

```text
runs/<timestamp>-<name>/
  resolved-config.yaml
  environment.json
  git.json
  data-manifest.json
  tokenizer-manifest.json
  metrics.jsonl
  samples.jsonl
  checkpoints/step-00001000.pt
  checkpoints/latest.pt
  evaluation.json
  training-report.md
```

checkpoint 필수 상태:

- model, optimizer, scheduler, GradScaler
- global step, tokens seen, best validation loss
- Python/NumPy/PyTorch CPU/CUDA RNG
- sampler 또는 데이터 cursor 상태
- resolved config hash, data/tokenizer fingerprint

임시 파일에 저장하고 `fsync` 후 atomic rename한다. config/data/tokenizer fingerprint 불일치 checkpoint는 기본적으로 재개하지 않는다.

## 7. 구현 단계

### M0. 저장소 기반

산출물: 패키지 skeleton, CLI, config validation, CI, fixture, 참조 코드 무결성 확인.

검증:

```bash
uv sync
uv run ruff check .
uv run pyright
uv run pytest -q
uv run llmex --help
cd 0.ref && shasum -a 256 -c SHA256SUMS
```

종료 조건: 네트워크/GPU 없이 CI가 통과하고 모든 config 오류가 사용자 친화적으로 실패한다.

### M1. 데이터 파이프라인

1. 날짜 고정 URL, checksum, resume download
2. XML fixture stream parse
3. namespace/redirect 필터
4. markup 정제 및 metadata 보존
5. quality filter와 exact dedup
6. document hash split
7. manifest/data report

테스트:

- 손상 다운로드 checksum 실패
- redirect/다른 namespace 제외
- 동일 입력의 동일 JSONL hash
- split 상호 배타성
- 정제 결과에 markup 잔해 threshold 이하
- attribution 필드 누락 0건

종료 조건: sample fixture E2E와 1,000문서 canary run 통과.

### M2. 토크나이저와 packing

1. train split iterator
2. byte-level BPE 학습
3. special token 고정
4. round-trip/효율 평가
5. EOS document packing
6. memmap shard와 manifest

테스트:

- 한글 자모, 완성형, emoji, 한자, ASCII round-trip
- vocab ID 범위와 dtype
- EOS 경계
- sequence sample의 next-token 정렬
- val/test가 tokenizer 학습에 사용되지 않음

종료 조건: tokenizer report와 deterministic shard checksum 생성.

### M3. 모델

1. RMSNorm
2. RoPE와 cache
3. GQA causal attention
4. SwiGLU
5. decoder block/LM/weight tying
6. parameter/VRAM inspect

테스트:

- 교재 수식과 reference tensor 비교
- 미래 토큰 변경이 이전 logits에 영향 0
- GQA shape/property tests
- CPU forward/backward
- state_dict save/load 동일 출력
- `torch.compile`은 선택 기능이며 eager correctness가 기준

종료 조건: unit tests와 128문서 overfit 통과.

### M4. Trainer

1. memmap dataset와 deterministic sampler
2. AdamW parameter grouping
3. warmup/cosine
4. accumulation, clipping, mixed precision
5. metric/sample logging
6. atomic checkpoint/resume/SIGTERM

테스트:

- scheduler 경계값
- accumulation과 큰 batch update 비교
- resume 전후 다음 step loss 허용 오차
- NaN injection이 즉시 실패하고 batch/step 기록
- CPU smoke 50 step

종료 조건: 중단·재개 포함 smoke run 자동 검증.

### M5. 평가

1. held-out NLL/perplexity
2. 고정 cloze JSONL 생성·동결
3. generation prompt suite
4. repetition/distinct-n
5. contamination exact/MinHash
6. canary/memorization

평가셋 정답은 train corpus에서 직접 복사하지 않고 별도 provenance와 hash를 기록한다. Wikipedia 기반 cloze는 test split에서 만들 경우 해당 목적과 한계를 명시한다.

종료 조건: `llmex eval` 한 명령이 machine-readable JSON과 Markdown report를 생성.

### M6. baseline 학습

사전 조건:

- GPU 모델/VRAM/시간/비용 기록
- DGX OS, driver, CUDA, container image digest, ARM64 기록
- unified memory available/RSS/swap/peak allocation 관측 확인
- 전체 dump checksum과 data report 승인
- token budget과 중단 기준 승인
- smoke의 모든 gate 통과

절차:

1. 1% token pilot
2. OOM/throughput/loss 검토
3. baseline 전체 실행
4. 주기적 validation/checkpoint
5. best/final 평가 비교

중단 기준: 반복 NaN, validation 악화 지속, 데이터 결함, 예상 비용 120% 초과, checkpoint 복구 실패.

### DGX Spark baseline 운용

1. `smoke`를 host CPU와 container CUDA에서 각각 실행한다.
2. 100M 모델의 100-step microbenchmark로 tokens/s와 peak unified memory를 측정한다.
3. context 512/1024, bf16, gradient checkpointing on/off를 비교한다.
4. dataloader worker 수를 0/2/4에서 비교해 ARM CPU와 shared memory 병목을 확인한다.
5. 가장 안정적인 설정으로 1% token pilot을 수행한다.
6. 예상 wall time과 SSD 여유 공간을 계산한 뒤 전체 run을 승인한다.

장기 학습은 SSH 세션과 분리된 `systemd`, `tmux` 또는 container restart policy를 사용한다. checkpoint와 metrics는 container 내부가 아니라 host bind mount에 기록한다. 온도, 전력, swap 증가와 disk 사용량을 주기적으로 기록한다.

### M7. 공개 준비

- data card, model card, training/eval report
- attribution과 라이선스 검토
- 비밀·로컬 경로 제거
- artifact checksum과 재현 명령
- 독립 코드/데이터/안전 리뷰

## 8. 병렬 작업 경계

M1 진행 중 독립적으로 할 수 있는 일:

- 모델 수학 unit test fixture 작성
- tokenizer 평가 문장셋 설계
- model/data card 템플릿 작성

병렬화하지 말아야 할 일:

- corpus schema가 확정되기 전 packer 구현
- tokenizer ID가 확정되기 전 model config 기본값 고정
- checkpoint schema 전에 trainer resume 구현
- smoke gate 전에 전체 dump/GPU 학습

## 9. 첫 개발 세션 실행안

1. repo root에 `AGENTS.md`, `pyproject.toml`, `.gitignore`, `README.md` 생성
2. DGX Spark에서 host 정보와 Docker GPU smoke 결과를 `docs/environment.md`에 기록
3. ARM64 호환 NGC PyTorch image를 검증하고 digest를 고정
4. `uv init --package` 후 의존성 그룹 구성
5. Typer root CLI와 Pydantic config 작성
6. 작은 합법적 fixture XML과 checksum fixture 추가
7. `data download --dry-run` 및 `data extract` 최소 vertical slice
8. unit/integration test, Ruff, Pyright 실행
9. `todo.md` M0 체크 및 실행 ledger 기록

첫 세션 완료 증거:

```text
uv run llmex --help
uv run llmex data download --config configs/data/sample.yaml --dry-run
uv run llmex data extract --config configs/data/sample.yaml
uv run pytest -q
uv run ruff check .
uv run pyright
```

## 10. Definition of Done

코드는 작성만으로 완료되지 않는다. 해당 milestone의 테스트, manifest/report, 문서, TODO 체크가 함께 존재해야 한다. GPU 결과는 실제 run ID와 metrics/checkpoint hash가 없으면 완료로 인정하지 않는다.
