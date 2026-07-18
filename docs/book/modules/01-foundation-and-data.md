# 기반과 데이터 모듈 구현 교재

이 문서는 빈 `src/llmex`에서 공통 기반과 Wikimedia 데이터 파이프라인을 다시 만드는 실습서다. 각 절은 공개 계약을 테스트로 먼저 고정한 뒤 구현한다. 전체 묶음의 기준 검증은 `uv run pytest -q tests/test_foundation.py tests/test_config.py tests/test_m1_data.py`다. 파이프라인·신뢰·릴리스와 CLI 조립은 각각 5부와 6부에서 다룬다.

## 1부. 패키지와 공통 기반

### `src/llmex/__init__.py`

- **책임:** 설치된 패키지의 공개 버전 `__version__`을 한 곳에서 제공한다.
- **먼저 구현할 계약:** 문자열 `__version__`; `pyproject.toml`, `uv.lock`, CLI가 같은 버전을 가리키게 한다.
- **단계별 구현:** ① 패키지 docstring을 둔다. ② 현재 프로젝트 버전을 상수로 선언한다. ③ CLI callback이 이 값을 읽도록 연결한다.
- **반드시 실패해야 할 사례:** 버전 누락, package metadata와 값 불일치, `llmex --version`이 0이 아닌 코드로 종료하는 경우다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_foundation.py -k version`; `uv run llmex --version`.
- **완료 산출물:** import 가능한 `llmex.__version__`과 동일한 CLI 버전 한 줄이다.

### `src/llmex/__main__.py`

- **책임:** `python -m llmex`를 console script와 같은 Typer 애플리케이션에 연결한다.
- **먼저 구현할 계약:** `from llmex.cli import app` 뒤 `app()`를 호출하는 최소 진입점이다.
- **단계별 구현:** ① `llmex.cli.app`를 import한다. ② 별도 명령 해석 없이 호출한다. ③ module 실행과 설치 명령의 help를 비교한다.
- **반드시 실패해야 할 사례:** 별도 parser로 CLI 표면이 갈라짐, import 시 순환 의존, 예외를 삼켜 종료 코드가 0이 되는 경우다.
- **관련 테스트와 명령:** `uv run python -m llmex --help`; `uv run pytest -q tests/test_foundation.py -k cli`.
- **완료 산출물:** `llmex --help`와 같은 명령군을 보여 주는 module entrypoint다.

### `src/llmex/errors.py`

- **책임:** 예상 가능한 실패를 안정적인 프로세스 종료 코드로 분류한다.
- **먼저 구현할 계약:** `ExitCode`의 `SUCCESS=0`, `CONFIG=2`, `INPUT=3`, `CONFLICT=4`, `INTEGRITY=5`, `INTERNAL=70`; `LlmexError`, `ConfigError`, `InputError`, `ConflictError`, `IntegrityError`다.
- **단계별 구현:** ① `IntEnum` 종료 코드를 만든다. ② 기반 예외가 message와 code를 보존하게 한다. ③ 구체 예외 생성자가 고정 코드를 넘기게 한다. ④ CLI의 `_emit_error`와 연결한다.
- **반드시 실패해야 할 사례:** 손상 파일을 일반 성공으로 처리, 설정 오류를 integrity로 오분류, 예상 예외가 traceback만 내고 계약된 코드 없이 끝나는 경우다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_foundation.py -k 'config_error_code or cli'`; 잘못된 YAML로 `uv run llmex config validate <파일> --kind data`를 실행한다.
- **완료 산출물:** 호출자가 `exc.code`만으로 종료 상태를 결정할 수 있는 예외 계층이다.

### `src/llmex/fingerprint.py`

- **책임:** 파일과 JSON 직렬화 가능 mapping의 결정적 SHA-256을 계산한다.
- **먼저 구현할 계약:** `sha256_file(path, chunk_size=1MiB) -> str`, `fingerprint(value) -> str`다.
- **단계별 구현:** ① 파일을 chunk streaming으로 읽는다. ② `OSError`를 `InputError`로 감싼다. ③ mapping은 UTF-8 canonical JSON(`sort_keys=True`, compact separator)으로 만든다. ④ 64자리 소문자 hex를 반환한다.
- **반드시 실패해야 할 사례:** 없는 파일, 읽기 불가 파일, key 삽입 순서에 따라 fingerprint가 달라지는 구현이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_foundation.py -k fingerprint`; `uv run llmex fingerprint file pyproject.toml`.
- **완료 산출물:** manifest와 checkpoint 결속에 재사용할 결정적 digest다.

### `src/llmex/paths.py`

- **책임:** 저장소 루트를 찾고 상대 경로를 그 루트 기준으로 해석한다.
- **먼저 구현할 계약:** `MARKERS=("pyproject.toml", ".git")`, `project_root(start=None)`, `resolve_from_root(path, root=None)`다.
- **단계별 구현:** ① `LLMEX_ROOT` override를 먼저 처리한다. ② 현재 위치부터 부모를 순회하며 두 marker를 모두 요구한다. ③ 절대 경로는 resolve하고 상대 경로는 루트에 결합한다.
- **반드시 실패해야 할 사례:** marker 하나만 있는 디렉터리 채택, 루트를 찾지 못했는데 cwd를 묵시적으로 사용, 환경 변수의 `~`를 확장하지 않는 경우다. 이 모듈은 `..` 자체를 차단하지 않으므로 보안 경계의 경로 정책과 혼동해서는 안 된다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_foundation.py -k paths`.
- **완료 산출물:** 실행 위치와 무관하게 같은 프로젝트 파일을 가리키는 절대 경로다.

### `src/llmex/logging.py`

- **책임:** 표준 로그를 한 줄짜리 UTF-8 JSON event로 직렬화한다.
- **먼저 구현할 계약:** `JsonFormatter.format(record)`, `configure_logging(level="INFO")`다.
- **단계별 구현:** ① UTC timestamp, level, logger, message를 기본 필드로 둔다. ② `record.fields`가 dict면 병합한다. ③ key를 정렬해 JSON으로 만든다. ④ root handler를 강제로 하나의 구조화 stderr handler로 설정한다.
- **반드시 실패해야 할 사례:** JSON 파싱 불가, 한 event가 여러 줄로 출력, dict가 아닌 `fields` 때문에 충돌하는 경우다. formatter는 비밀 redaction을 하지 않으므로 secret을 넘기는 호출자도 실패 설계 대상으로 둔다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_foundation.py -k json_formatter`; `uv run llmex --log-level DEBUG --version`.
- **완료 산출물:** 로그 수집기가 그대로 parse할 수 있는 JSON Lines다.

### `src/llmex/config.py`

- **책임:** 모든 YAML 설정의 strict schema와 loader를 소유한다.
- **먼저 구현할 계약:** 기반 `StrictModel`, `YamlPath`, `load_yaml`; 데이터의 `PathConfig`, `DumpConfig`, `CleaningConfig`, `DownloadConfig`, `DataConfig`; 모델·학습·평가의 `ModelConfig`, `TokenizerConfig`, `OptimizerConfig`, `TrainingConfig`, `EvaluationConfig`; 대화·증류·파이프라인의 `SFTConfig`, `SensitiveOutputRegex`, `SFTMixConfig`, `SFTCurriculumConfig`, `SFTQualityThresholds`, `SFTQualityProfile`, `SFTQualityConfig`, `UnsafeConceptConfig`, `DistillationConfig`, `BudgetConfig`, `PipelineStageConfig`, `PipelineConfig`다.
- **단계별 구현:** ① `extra="forbid"`, `strict=True` 기반을 만든다. ② 문자열 YAML 경로만 `Path`로 바꾸는 before validator를 둔다. ③ 각 필드 범위와 literal을 선언한다. ④ `ModelConfig`의 head 나눗셈·짝수 head dimension, 학습 길이·warmup, pinned dump URL, 기본 loopback과 명시적 내부망 allowlist의 `/v1` teacher endpoint 같은 교차 필드 validator를 추가한다. ⑤ `load_yaml`에서 I/O·YAML·Pydantic 오류를 한국어 `ConfigError`로 정규화한다.
- **반드시 실패해야 할 사례:** 알 수 없는 key, 문자열 `"1"`을 정수로 묵시 변환, `latest` dump URL, `d_model % n_heads != 0`, model 문맥보다 긴 sequence, localhost가 아닌 증류 endpoint, 자동 품질 임계값을 안전 하한보다 낮추는 설정이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_config.py tests/test_foundation.py -k config`; `uv run llmex config validate configs/model/smoke.yaml --kind model`.
- **완료 산출물:** 이후 모듈이 별도 방어 없이 타입과 범위를 신뢰할 수 있는 resolved config 객체다.

### `src/llmex/locking.py`

- **책임:** 출력 디렉터리마다 회수 가능한 단일 writer lock을 보장한다.
- **먼저 구현할 계약:** context manager `exclusive_run_lock(directory, filename, label)`; 내부 `_pid_is_live`, `_write_lock`이다.
- **단계별 구현:** ① `O_EXCL|O_NOFOLLOW`와 mode `0600`으로 lock을 만든다. ② schema version, PID, host, UTC 시작 시각을 fsync한다. ③ 기존 lock은 같은 host의 종료 PID일 때만 flock 뒤 byte 재확인하여 회수한다. ④ 종료 시 자신이 잡은 inode와 같을 때만 unlink한다.
- **반드시 실패해야 할 사례:** live PID, 다른 host, 잘못된 JSON/schema, 검사 중 바뀐 lock, symlink lock이다. 정리·close 실패는 `IntegrityError`여야 한다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_distill.py tests/test_sft_mixer.py -k lock`.
- **완료 산출물:** 동시 writer 중 정확히 하나만 임계 구역에 들어가는 context다.

### `src/llmex/run.py`

- **책임:** config fingerprint가 포함된 실행 디렉터리와 환경·Git 증거를 만든다.
- **먼저 구현할 계약:** immutable dataclass `RunInfo(path, fingerprint)`, `create_run(...)`, 내부 `_git_revision(root)`다.
- **단계별 구현:** ① canonical config fingerprint를 만든다. ② UTC timestamp·name·digest prefix로 run ID를 만든다. ③ resolved YAML, Python/platform/architecture/PID 환경 JSON, commit/dirty Git JSON을 쓴다. ④ 기존 경로는 `force=False`에서 충돌시킨다.
- **반드시 실패해야 할 사례:** 기존 run 묵시 덮어쓰기, Git 명령 실패를 깨끗한 상태로 위장, 환경 JSON에 config fingerprint 누락이다.
- **관련 테스트와 명령:** `uv run llmex run create --help`; `uv run pytest -q tests/test_foundation.py`.
- **완료 산출물:** `resolved-config.yaml`, `environment.json`, `git.json`과 `RunInfo`다.

### `src/llmex/sensitive.py`

- **책임:** PII·secret·위험 출력의 built-in 규칙과 추가 정규식의 안전한 부분집합을 정의한다.
- **먼저 구현할 계약:** `SensitiveOutputRule`, `BUILTIN_*` 상수, `matched_sensitive_output_rules`, `has_builtin_sensitive_output`, `validate_safe_extra_pattern`, `validate_safe_assertion_pattern`이다.
- **단계별 구현:** ① 주민번호·전화·이메일·API key 등 이름 있는 built-in을 고정한다. ② 최대 scan 길이와 별도 길이 차단 rule을 둔다. ③ 추가 regex의 길이·syntax·중첩 반복·위험 lookaround/backreference를 거부한다. ④ assertion parser가 허용된 bounded 구조만 받게 한다. ⑤ 매치된 rule 이름을 결정적 순서로 반환한다.
- **반드시 실패해야 할 사례:** 과도하게 긴 입력, catastrophic nested quantifier, 임의 backreference/lookbehind, built-in과 중복된 추가 규칙, secret이 있는데 빈 결과를 내는 경우다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_sft_mixer.py tests/test_sft_quality.py -k 'sensitive or regex or secret or pii'`.
- **완료 산출물:** mix·quality·release가 공유하는 fail-closed 민감 출력 판정이다.

## 2부. 데이터 파이프라인

### `src/llmex/data/__init__.py`

- **책임:** M1 데이터 패키지의 최소 공개 API를 선언한다.
- **먼저 구현할 계약:** `Document`를 import하고 `__all__ = ["Document"]`로 제한한다.
- **단계별 구현:** ① schema가 안정된 뒤 export한다. ② pipeline 구현을 package root에서 과도하게 노출하지 않는다. ③ import smoke를 수행한다.
- **반드시 실패해야 할 사례:** 존재하지 않는 symbol export, import 순환, 내부 helper가 우연히 공개되는 경우다.
- **관련 테스트와 명령:** `uv run python -c 'from llmex.data import Document; print(Document)'`; `uv run pytest -q tests/test_m1_data.py`.
- **완료 산출물:** `from llmex.data import Document`가 가능한 좁은 경계다.

### `src/llmex/data/schema.py`

- **책임:** 정제 corpus의 attribution, 품질 측정, document schema v1을 정의한다.
- **먼저 구현할 계약:** `Attribution`, `Quality`, `Document.attribution()`, `Document.json_row()`다.
- **단계별 구현:** ① 양수 page/revision ID와 날짜·SHA pattern을 고정한다. ② 0~1 품질 비율과 policy 통계를 선언한다. ③ title/text 비어 있음과 split literal을 제한한다. ④ attribution projection과 JSON row 직렬화를 구현한다.
- **반드시 실패해야 할 사례:** provenance 누락, 64 hex가 아닌 SHA, 빈 text/title, 범위 밖 ratio, 정의되지 않은 split이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m1_data.py -k 'markup_policy or split'`.
- **완료 산출물:** 모든 downstream 단계가 재검증할 수 있는 schema version 1 JSON row다.

### `src/llmex/data/io.py`

- **책임:** 원자 bytes/JSON 쓰기와 결정적 JSONL.ZST streaming I/O, output fingerprint 충돌 보호를 제공한다.
- **먼저 구현할 계약:** `atomic_write_bytes`, `prepare_output`, `write_json`, `write_jsonl_zst`, `read_jsonl_zst`다.
- **단계별 구현:** ① 같은 디렉터리 `.tmp`에 쓰고 file fsync→replace→directory fsync한다. ② operation fingerprint sidecar를 먼저 만든다. ③ system `zstd -T1 -3` stdin/stdout streaming을 구현한다. ④ 한 행이 dict인지 검증하고 subprocess 종료 코드를 확인한다.
- **반드시 실패해야 할 사례:** zstd 미설치, 기존 output에 sidecar 없음, 다른 fingerprint 덮어쓰기, 압축 subprocess 실패, JSONL 행이 객체가 아님이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m1_data.py tests/test_m2_tokenizer.py -k 'conflict or deterministic'`; `zstd --version`.
- **완료 산출물:** crash 후에도 완전한 이전/새 파일 중 하나만 남는 JSON·JSONL.ZST와 fingerprint sidecar다.

### `src/llmex/data/download.py`

- **책임:** 날짜 고정 Wikimedia metadata를 조회하고 `.part` HTTP Range resume 뒤 immutable raw dump를 게시한다.
- **먼저 구현할 계약:** `fetch_metadata(base_url, filename, timeout)`, `download(url, destination, expected_sha256, timeout, retries, backoff, disk_overhead_ratio)`다.
- **단계별 구현:** ① `dumpstatus.json`과 `SHA256SUMS`에서 대상 checksum 하나만 찾는다. ② 기존 완성 파일은 SHA가 맞을 때만 재사용한다. ③ `.part` 크기로 Range를 요청하고 206일 때만 append한다. ④ 예상 크기×overhead의 disk 여유를 검사한다. ⑤ exponential backoff 후 SHA를 검증하고 chmod `0444`로 승격한다.
- **반드시 실패해야 할 사례:** checksum 항목 0/복수, 저장 공간 부족, retry 소진, 서버가 Range를 무시했는데 append, 최종 SHA 불일치다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m1_data.py -k 'range_resume or retry_exhaustion'`; `uv run llmex data download --help`.
- **완료 산출물:** 검증된 read-only raw dump와 path/bytes/SHA/resumed offset 결과다.

### `src/llmex/data/extract.py`

- **책임:** bzip2 MediaWiki XML을 메모리 제한 streaming으로 읽어 main namespace의 최신 비 redirect revision을 방출한다.
- **먼저 구현할 계약:** `RawPage`, `stream_pages(path, max_documents=None)`; namespace 독립 child helper `_child`다.
- **단계별 구현:** ① `bz2.open`과 `ElementTree.iterparse(events=("end",))`를 사용한다. ② page 끝에서 `ns==0`, redirect 없음만 선택한다. ③ 마지막 revision의 id/text와 page id/title을 검증한다. ④ yield 뒤 element를 clear한다. ⑤ 방출 수가 max에 도달하면 종료한다.
- **반드시 실패해야 할 사례:** 손상 bz2/XML, redirect·다른 namespace 포함, revision/text 누락 row 방출, 전체 tree를 보존해 메모리가 증가하는 구현이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m1_data.py -k stream_extract`; `uv run llmex data extract --help`.
- **완료 산출물:** `page_id`, `revision_id`, `title`, `text`만 가진 streaming `RawPage` iterator다.

### `src/llmex/data/clean.py`

- **책임:** MediaWiki markup 정책, NFC 정규화, 품질 측정, provenance 있는 `Document` 생성을 수행한다.
- **먼저 구현할 계약:** `CleanResult`, `parse_markup`, `normalize_text`, `quality`, `clean_page`; 고정 `LICENSE`다.
- **단계별 구현:** ① 표·ref·comment·template은 제거하고 math/list/link 표시문은 보존한다. ② HTML unescape 뒤 NFC와 제어문자·공백을 정규화한다. ③ 문자/byte, 한글·반복·잔여 markup 비율을 계산한다. ④ config 임계값을 순서대로 적용해 reason을 반환한다. ⑤ normalized text SHA와 Wikimedia attribution으로 `Document`를 만든다.
- **반드시 실패해야 할 사례:** 짧음/낮은 한글 비율/높은 반복/markup 잔존이 통과, source page/revision/license 유실, 같은 정규 text가 다른 SHA를 갖는 경우다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m1_data.py -k 'markup_policy or filters'`; `uv run llmex data clean --help`.
- **완료 산출물:** 성공 시 `Document`, 제외 시 안정된 reason을 가진 `CleanResult`와 policy 통계다.

### `src/llmex/data/dedup.py`

- **책임:** normalized SHA exact 중복과 선택적 결정적 MinHash near 중복을 제거한다.
- **먼저 구현할 계약:** `shingles(text, size)`, `signature(text, size, permutations=64)`, `deduplicate(documents, near, threshold, shingle_size)`다.
- **단계별 구현:** ① whitespace를 단일 공백으로 정규화해 문자 shingle set을 만든다. ② `seed:item` SHA 앞 8바이트의 permutation별 최소값을 signature로 쓴다. ③ exact SHA set을 먼저 검사한다. ④ near mode에서 signature 일치율이 threshold 이상이면 제외한다. ⑤ iterator와 공유 stats를 반환한다.
- **반드시 실패해야 할 사례:** exact 중복이 near=False에서 통과, threshold 이상 near duplicate 통과, 빈/짧은 text에서 `min()` 실패, 통계와 실제 방출 수 불일치다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m1_data.py -k 'exact_and_near_dedup or filters'`; `uv run llmex data dedup --help`.
- **완료 산출물:** unique document iterator와 `exact_duplicates`, `near_duplicates` 카운터다.

### `src/llmex/data/split.py`

- **책임:** document 내용 SHA와 seed로 순서 독립적인 98/1/1 split을 결정한다.
- **먼저 구현할 계약:** `split_for(document_hash, seed) -> "train"|"validation"|"test"`다.
- **단계별 구현:** ① `seed:document_hash` SHA 앞 8바이트를 정수로 바꾼다. ② 10,000 bucket으로 줄인다. ③ `<9800`, `<9900`, 나머지 경계를 적용한다. ④ 입력 순서를 바꿔 결과가 같은지 검사한다.
- **반드시 실패해야 할 사례:** row index/random 전역 상태를 사용, 같은 hash가 서로 다른 split에 배치, 경계 9800/9900을 잘못 분류하는 경우다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m1_data.py -k split_disjoint`; `uv run llmex data split --help`.
- **완료 산출물:** 내용 identity에 고정된 상호 배타 split 문자열이다.

### `src/llmex/data/pipeline.py`

- **책임:** raw→extract→clean→dedup→split을 조립하고 manifest, 보고서, 감사 표본을 생성한다.
- **먼저 구현할 계약:** `raw_manifest`, `extract_rows`, `clean_rows`, `dedup_rows`, `split_rows`, `build_report`, `report_markdown`, `audit_sample`, `run_e2e`다.
- **단계별 구현:** ① 각 stage를 iterable 변환으로 작성한다. ② `Counter`에 before/after/filter/policy/split 통계를 누적한다. ③ 최종 corpus SHA와 config/input/max-documents fingerprint를 manifest에 봉인한다. ④ 사람이 읽는 `data-report.md`와 seed 고정 100건 audit JSON/표를 만든다. ⑤ `run_e2e`가 단계별 압축 중간물과 최종물을 순서대로 게시한다.
- **반드시 실패해야 할 사례:** input SHA가 manifest와 불일치, schema가 아닌 row 통과, split overlap, 감사 표본이 요청 수보다 많음, max_documents가 fingerprint에서 빠지는 경우다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m1_data.py -k 'deterministic_e2e or cli'`; `uv run llmex data sample-e2e --config configs/data/sample.yaml --input tests/fixtures/kowiki-sample.xml.bz2 --output-dir data/book/sample-corpus --max-documents 1000 --force`.
- **완료 산출물:** `extracted.jsonl.zst`, `cleaned.jsonl.zst`, `deduplicated.jsonl.zst`, `corpus-v1.jsonl.zst`, `data-manifest.json`, `data-report.md`, `audit-sample.{json,md}`다.

## 묶음 완료 기준

1. `uv run pytest -q tests/test_foundation.py tests/test_config.py tests/test_m1_data.py`가 통과한다.
2. `uv run ruff check src/llmex tests/test_foundation.py tests/test_config.py tests/test_m1_data.py`가 통과한다.
3. 같은 fixture와 config로 만든 corpus SHA와 split이 재실행에서도 같다.
4. 손상·누락·충돌 입력은 `ConfigError`, `InputError`, `ConflictError`, `IntegrityError` 중 의도한 코드로 실패한다.
