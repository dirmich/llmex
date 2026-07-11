# M2 토크나이저 보고서

## 구현 계약

- Hugging Face `tokenizers`의 byte-level BPE를 사용한다.
- 학습 입력은 schema v1 JSONL.ZST의 `train` split만 streaming으로 읽는다.
- `<pad>=0`, `<bos>=1`, `<eos>=2`, `<unk>=3`을 고정한다.
- ByteLevel initial alphabet과 byte fallback으로 유효 Unicode의 lossless round-trip과 UNK 0건을 검증한다.
- `configs/tokenizer/bpe-16k.yaml`과 `bpe-32k.yaml`을 제공한다.
- `tokenizer.json`, `vocab.json`, `merges.txt`, `config.json`, corpus/artifact checksum manifest를 저장한다.

## 효율 지표와 byte baseline

`llmex tokenizer evaluate`는 전체 split을 학습 없이 동일 tokenizer로 인코딩해 문자/토큰, UTF-8 바이트/토큰, 단어당 토큰을 계산한다. 비교 기준은 UTF-8 한 바이트를 한 토큰으로 보는 raw byte tokenizer이며, `1 - BPE 토큰 수 / UTF-8 바이트 수`를 감소율로 기록한다. fixture 수치는 생성 artifact의 `evaluation.json`과 `evaluation.md`에 저장하며 실제 Wikipedia 수치로 오인하지 않는다.

## shard 형식

각 source 문서를 독립 인코딩한 뒤 EOS를 한 개 붙인다. 전체 stream의 문서 `start`, `end`, `eos`, source SHA-256을 manifest에 남기므로 shard 물리 경계와 무관하게 next-token 정렬과 문서 경계를 복원할 수 있다. 실제 vocab 최대 ID가 65,535 이하면 little-endian `uint16`, 그보다 크고 32-bit 범위 이하면 `uint32`를 선택한다. shard는 임시 memmap을 flush/fsync한 뒤 atomic rename하며 checksum, token 수, 최소/최대 ID를 기록한다.

## 검증 범위와 한계

오프라인 M1 형식 fixture에서 한글 완성형, 호환 자모, NFD 자모, emoji ZWJ, 한자, ASCII, combining marks를 검증한다. Hypothesis Unicode property test와 seed가 고정된 10,000표본도 round-trip과 UNK 0건을 확인한다. validation/test 문장을 바꿔도 학습 tokenizer checksum이 같아야 하며 source SHA-256이 split 사이에 겹치면 즉시 실패한다. M2 완료는 fixture 재현성에 대한 결론이며, 실제 전체 Wikipedia의 16k/32k 품질 선택은 M6에서 수행한다.
