"""checkpoint 기반 평가, 생성, 오염 검사와 latency/memory benchmark."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false

import json
import math
import time
from typing import Any

import torch
from torch.nn import functional as F

from llmex.config import EvaluationConfig
from llmex.data.io import atomic_write_bytes, write_json
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.inference import load_runtime
from llmex.model import GenerationConfig
from llmex.tokenizer.core import SPECIAL_IDS, iter_documents
from llmex.train.data import TokenShardDataset

FROZEN_CLOZE = (
    {
        "id": "ko-wiki-001",
        "prompt": "대한민국의 수도는 [MASK]이다.",
        "answer": "서울",
        "candidates": ["서울", "부산", "평양"],
        "provenance": "고정 합성 평가 문항; Wikipedia 사실 형식",
    },
    {
        "id": "ko-wiki-002",
        "prompt": "훈민정음을 창제한 왕은 [MASK]이다.",
        "answer": "세종대왕",
        "candidates": ["세종대왕", "태조", "정조"],
        "provenance": "고정 합성 평가 문항; Wikipedia 사실 형식",
    },
)


def _generation(config: EvaluationConfig) -> GenerationConfig:
    return GenerationConfig(
        max_new_tokens=config.max_new_tokens,
        temperature=config.temperature,
        top_k=config.top_k,
        top_p=config.top_p,
        eos_id=SPECIAL_IDS["<eos>"],
        use_cache=config.use_cache,
        repetition_penalty=config.repetition_penalty,
    )


def _generator(device: torch.device, seed: int) -> torch.Generator:
    generator = torch.Generator(device=device.type)
    generator.manual_seed(seed)
    return generator


def _finalize(
    config: EvaluationConfig, stem: str, payload: dict[str, Any], markdown: str
) -> dict[str, Any]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    payload["fingerprint"] = fingerprint(payload)
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    write_json(json_path, payload)
    atomic_write_bytes(md_path, markdown.encode("utf-8"))
    checksums = {
        json_path.name: sha256_file(json_path),
        md_path.name: sha256_file(md_path),
    }
    checksum_path = config.output_dir / f"{stem}.checksums.json"
    write_json(
        checksum_path,
        {"schema_version": 1, "files": checksums, "fingerprint": fingerprint(checksums)},
    )
    return {
        **payload,
        "artifacts": {
            "json": str(json_path),
            "markdown": str(md_path),
            "checksums": str(checksum_path),
        },
    }


def _distinct(ids: list[int], n: int) -> float:
    grams = [tuple(ids[index : index + n]) for index in range(max(0, len(ids) - n + 1))]
    return len(set(grams)) / len(grams) if grams else 0.0


def _repetition(ids: list[int]) -> float:
    return 0.0 if not ids else 1.0 - len(set(ids)) / len(ids)


def _contamination(config: EvaluationConfig, needles: list[str]) -> dict[str, Any]:
    if config.corpus is None:
        return {"status": "미실행", "reason": "corpus 경로가 설정되지 않았습니다"}
    exact = dict.fromkeys(needles, False)

    def shingles(text: str, size: int = 5) -> set[str]:
        normalized = " ".join(text.split())
        return {normalized[i : i + size] for i in range(max(0, len(normalized) - size + 1))}

    needle_shingles = {needle: shingles(needle) for needle in needles}
    near = dict.fromkeys(needles, 0.0)
    documents = 0
    for row in iter_documents(config.corpus, split="train"):
        text = str(row["text"])
        documents += 1
        right = shingles(text)
        for needle, left in needle_shingles.items():
            exact[needle] = exact[needle] or needle in text
            union_size = len(left) + len(right) - len(left & right)
            score = len(left & right) / union_size if union_size else 0.0
            near[needle] = max(near[needle], score)
    return {
        "status": "완료",
        "algorithm": "single-pass-bounded-5gram",
        "exact": exact,
        "near_jaccard": near,
        "train_documents": documents,
    }


def _conditional_score(
    runtime: Any, prefix: str, candidate: str, suffix: str = ""
) -> dict[str, Any]:
    combined = prefix + candidate + suffix
    encoding = runtime.tokenizer.encode(combined)
    full_ids = encoding.ids
    candidate_start, candidate_end = len(prefix), len(prefix) + len(candidate)
    target_indexes = [
        index
        for index, (start, end) in enumerate(encoding.offsets)
        if start < candidate_end and end > candidate_start
    ]
    if (
        not prefix
        or not candidate
        or not target_indexes
        or target_indexes[0] == 0
        or len(full_ids) > runtime.model.config.max_seq_len
    ):
        raise IntegrityError("cloze/canary 문항을 유효한 문맥으로 인코딩할 수 없습니다")
    values = torch.tensor([full_ids], dtype=torch.long, device=runtime.device)
    with torch.no_grad():
        log_probs = F.log_softmax(runtime.model(values).logits[0, :-1], dim=-1)
    scores = [float(log_probs[index - 1, full_ids[index]]) for index in target_indexes]
    total = sum(scores)
    return {
        "log_likelihood": total,
        "mean_log_likelihood": total / len(scores),
        "tokens": len(scores),
    }


def _canary(runtime: Any, config: EvaluationConfig) -> dict[str, Any]:
    if config.canaries_file is None:
        return {"status": "미실행", "gate": "실패", "reason": "canary provenance 파일 없음"}
    try:
        payload = json.loads(config.canaries_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError("canary provenance가 손상되었습니다") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or not payload.get("canaries")
    ):
        raise IntegrityError("canary provenance schema/items가 비었습니다")
    rows = []
    for item in payload["canaries"]:
        candidates = item.get("candidates")
        secret = item.get("secret")
        if not isinstance(candidates, list) or secret not in candidates:
            raise IntegrityError("canary secret/candidates 계약이 유효하지 않습니다")
        scored = [
            {"candidate": value, **_conditional_score(runtime, item["prefix"], value)}
            for value in candidates
        ]
        scored.sort(key=lambda value: value["mean_log_likelihood"], reverse=True)
        rank = next(index + 1 for index, value in enumerate(scored) if value["candidate"] == secret)
        rows.append(
            {
                "id": item["id"],
                "secret_rank": rank,
                "exposed": rank <= config.canary_max_rank,
                "scores": scored,
            }
        )
    exposed = any(row["exposed"] for row in rows)
    return {
        "status": "완료",
        "gate": "실패" if exposed else "통과",
        "threshold_rank": config.canary_max_rank,
        "canaries": rows,
        "provenance_sha256": sha256_file(config.canaries_file),
    }


def generate(config: EvaluationConfig, prompt: str | None = None) -> dict[str, Any]:
    runtime = load_runtime(config)
    prompts = [prompt] if prompt is not None else config.prompts
    rows: list[dict[str, Any]] = []
    for index, text in enumerate(prompts):
        ids = runtime.tokenizer.encode(text).ids
        if not ids:
            raise IntegrityError("prompt를 token으로 인코딩할 수 없습니다")
        if len(ids) > runtime.model.config.max_seq_len:
            raise IntegrityError("prompt token 수가 모델 문맥 길이를 초과합니다")
        inputs = torch.tensor([ids], dtype=torch.long, device=runtime.device)
        output = runtime.model.generate(
            inputs, _generation(config), generator=_generator(runtime.device, config.seed + index)
        )
        generated = output[0, len(ids) :].tolist()
        decoded = runtime.tokenizer.decode(output[0].tolist())
        try:
            decoded.encode("utf-8", errors="strict")
            unicode_valid = True
        except UnicodeEncodeError:
            unicode_valid = False
        rows.append(
            {
                "prompt": text,
                "text": decoded,
                "prompt_tokens": len(ids),
                "generated_tokens": len(generated),
                "token_ids": output[0].tolist(),
                "eos_reached": SPECIAL_IDS["<eos>"] in generated,
                "context_limit_reached": output.size(1) == runtime.model.config.max_seq_len,
                "repetition_rate": _repetition(generated),
                "distinct_1": _distinct(generated, 1),
                "distinct_2": _distinct(generated, 2),
                "unicode_valid": unicode_valid,
            }
        )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "generation",
        "seed": config.seed,
        "sampling": _generation(config).__dict__,
        "fingerprints": runtime.fingerprints,
        "generations": rows,
    }
    sections: list[str] = []
    for index, row in enumerate(rows):
        sections.append(
            f"## 프롬프트 {index + 1}\n\n"
            f"- 입력: `{row['prompt']}`\n- 출력: {row['text']}\n"
            f"- 생성 토큰: {row['generated_tokens']}\n"
            f"- 반복률: {row['repetition_rate']:.6f}\n"
            f"- Unicode 유효: {row['unicode_valid']}"
        )
    markdown = "# M5 생성 보고서\n\n" + "\n\n".join(sections) + "\n"
    return _finalize(config, "generation-report", payload, markdown)


def evaluate(config: EvaluationConfig) -> dict[str, Any]:
    runtime = load_runtime(config)
    split_results: dict[str, Any] = {}
    sequence_length = runtime.training.sequence_length
    for split in config.splits:
        dataset = TokenShardDataset(config.shards_manifest, split, sequence_length)
        starts = list(range(0, dataset.window_count, sequence_length - 1))
        if config.max_batches is not None:
            starts = starts[: config.max_batches * config.batch_size]
        nll_sum = 0.0
        tokens = 0
        byte_count = 0
        with torch.no_grad():
            for offset in range(0, len(starts), config.batch_size):
                batch_starts = starts[offset : offset + config.batch_size]
                values = torch.stack([dataset.window(start) for start in batch_starts]).to(
                    runtime.device
                )
                logits = runtime.model(values).logits[:, :-1]
                targets = values[:, 1:]
                nll_sum += float(
                    F.cross_entropy(
                        logits.reshape(-1, logits.size(-1)), targets.reshape(-1), reduction="sum"
                    )
                )
                tokens += targets.numel()
                byte_count += sum(
                    len(runtime.tokenizer.decode(row.tolist()).encode("utf-8"))
                    for row in targets.cpu()
                )
        if tokens == 0 or byte_count == 0:
            raise IntegrityError(f"{split} 평가 token/byte 수가 0입니다")
        nll_token = nll_sum / tokens
        nll_byte = nll_sum / byte_count
        split_results[split] = {
            "nll_sum": nll_sum,
            "predicted_tokens": tokens,
            "decoded_bytes": byte_count,
            "nll_per_token": nll_token,
            "loss": nll_token,
            "perplexity": math.exp(min(nll_token, 80.0)),
            "nll_per_byte": nll_byte,
            "bits_per_byte": nll_byte / math.log(2.0),
            "byte_perplexity": math.exp(min(nll_byte, 80.0)),
        }
    generations = generate(config)["generations"]
    cloze: list[dict[str, Any]] = []
    correct = 0
    for item in FROZEN_CLOZE:
        prompt = str(item["prompt"])
        prefix, suffix = prompt.split("[MASK]")
        candidates = [str(value) for value in item["candidates"]]
        scored = [
            {
                "candidate": candidate,
                **_conditional_score(runtime, prefix, candidate, suffix),
            }
            for candidate in candidates
        ]
        scored.sort(key=lambda value: value["mean_log_likelihood"], reverse=True)
        rank = next(
            index + 1 for index, value in enumerate(scored) if value["candidate"] == item["answer"]
        )
        correct += rank == 1
        cloze.append(
            {
                **item,
                "answer_rank": rank,
                "correct": rank == 1,
                "scores": scored,
            }
        )
    needles = [str(item["answer"]) for item in FROZEN_CLOZE] + config.prompts
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "evaluation",
        "fingerprints": runtime.fingerprints,
        "splits": split_results,
        "cloze_schema": {
            "version": 2,
            "scoring": "conditional mean log-likelihood; higher is better",
            "accuracy": correct / len(cloze),
            "items": cloze,
        },
        "generation_quality": generations,
        "contamination": _contamination(config, needles),
        "canary_exposure": _canary(runtime, config),
        "long_train_match": _contamination(config, [row["text"] for row in generations]),
    }
    lines = [
        "# M5 평가 보고서",
        "",
        "## 언어 모델 지표",
        "",
        "| split | loss/NLL·token | perplexity | bits/byte |",
        "|---|---:|---:|---:|",
    ]
    for split, metrics in split_results.items():
        lines.append(
            f"| {split} | {metrics['nll_per_token']:.6f} | "
            f"{metrics['perplexity']:.6f} | {metrics['bits_per_byte']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## 평가 계약",
            "",
            "- 고정 cloze schema와 provenance 포함",
            "- exact/문자 5-gram Jaccard 오염 검사 포함",
            "- 생성별 반복률, distinct-n, Unicode, EOS/문맥 종료 포함",
            "",
        ]
    )
    return _finalize(config, "evaluation-report", payload, "\n".join(lines))


def benchmark(config: EvaluationConfig) -> dict[str, Any]:
    runtime = load_runtime(config)
    prompt = config.prompts[0]
    ids = runtime.tokenizer.encode(prompt).ids
    if not ids:
        raise IntegrityError("benchmark prompt가 비었습니다")
    inputs = torch.tensor([ids], dtype=torch.long, device=runtime.device)
    generation = _generation(config)
    times: list[float] = []
    if runtime.device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(runtime.device)
    output = inputs
    for index in range(config.benchmark_warmup + config.benchmark_iterations):
        if runtime.device.type == "cuda":
            torch.cuda.synchronize(runtime.device)
        started = time.perf_counter()
        output = runtime.model.generate(
            inputs, generation, generator=_generator(runtime.device, config.seed + index)
        )
        if runtime.device.type == "cuda":
            torch.cuda.synchronize(runtime.device)
        elapsed = time.perf_counter() - started
        if index >= config.benchmark_warmup:
            times.append(elapsed)
    generated = max(0, output.size(1) - inputs.size(1))
    latency = sum(times) / len(times)
    payload = {
        "schema_version": 1,
        "kind": "benchmark",
        "device": str(runtime.device),
        "fingerprints": runtime.fingerprints,
        "iterations": len(times),
        "generated_tokens": generated,
        "latency_seconds_mean": latency,
        "tokens_per_second": generated / latency if latency else 0.0,
        "peak_memory_bytes": torch.cuda.max_memory_allocated(runtime.device)
        if runtime.device.type == "cuda"
        else None,
    }
    markdown = (
        f"# M5 추론 benchmark\n\n- 장치: {runtime.device}\n"
        f"- 평균 latency: {latency:.6f}초\n"
        f"- 처리량: {payload['tokens_per_second']:.3f} token/s\n"
        f"- peak CUDA memory: {payload['peak_memory_bytes']} byte\n"
    )
    return _finalize(config, "benchmark-report", payload, markdown)
