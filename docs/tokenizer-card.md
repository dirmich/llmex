# LLMEX 토크나이저 카드 1.0

byte-level BPE와 ByteLevel pre-tokenizer/decoder, byte fallback을 사용한다. 특수 ID는
`<pad>=0`, `<bos>=1`, `<eos>=2`, `<unk>=3`이다. 학습에는 train split만 사용하며 유효 Unicode
round-trip과 UNK 0건을 검사한다.

16k가 조건부 기본값이다. canary에서 32k가 token 수를 8.46% 줄였지만 embedding 비용과 전체
corpus 처리량 비교가 미승인이다. tokenizer, config, corpus checksum을 항상 함께 보존한다.
