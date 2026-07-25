"""Transformers + PEFT QLoRA 실행 경로."""

import importlib
import json
from pathlib import Path
from typing import Any

from llmex.chat.data import load_chat_jsonl
from llmex.errors import InputError, IntegrityError
from llmex.qwen3.config import Qwen3Config
from llmex.qwen3.data import Qwen3ChatDataset, Qwen3DataCollator
from llmex.qwen3.harness import language_gate, system_prompt

_OPTIONAL_MODULES = ("transformers", "peft", "bitsandbytes", "accelerate")
_INSTALL = "uv pip install -r configs/qwen3-14b/requirements.txt"
_DOWNLOAD = "hf download Qwen/Qwen3-14B --local-dir ~/work/models/Qwen3-14B"


def validate_model_dir(model_dir: Path) -> dict[str, object]:
    """로컬 디렉터리가 Qwen3 원본 safetensors인지 실패-폐쇄로 확인합니다."""

    if not model_dir.is_dir():
        raise InputError(
            f"로컬 Qwen3 모델 디렉터리가 없습니다: {model_dir}. 다운로드 예: {_DOWNLOAD}"
        )
    config_path = model_dir / "config.json"
    if not config_path.is_file():
        raise InputError(f"Transformers config.json이 없습니다: {config_path}")
    try:
        model_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"model config를 읽을 수 없습니다: {config_path}: {exc}") from exc
    if model_config.get("model_type") != "qwen3":
        raise IntegrityError(
            f"model_type이 qwen3가 아닙니다: {model_config.get('model_type')!r} ({config_path})"
        )
    shards = sorted(model_dir.glob("*.safetensors"))
    if not shards:
        raise InputError(
            f"원본 safetensors가 없습니다: {model_dir}. GGUF는 학습 입력으로 사용할 수 없습니다. "
            f"다운로드 예: {_DOWNLOAD}"
        )
    tokenizer_files = ("tokenizer.json", "tokenizer_config.json")
    missing = [name for name in tokenizer_files if not (model_dir / name).is_file()]
    if missing:
        raise InputError(f"Qwen tokenizer 파일이 없습니다: {', '.join(missing)} ({model_dir})")
    return {
        "model_dir": str(model_dir),
        "model_type": "qwen3",
        "safetensors_files": len(shards),
        "safetensors_bytes": sum(path.stat().st_size for path in shards),
    }


def require_optional_dependencies() -> None:
    missing: list[str] = []
    for module in _OPTIONAL_MODULES:
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    if missing:
        raise InputError(f"Qwen3 QLoRA 의존성이 없습니다: {', '.join(missing)}. 설치: {_INSTALL}")


def preflight(config: Qwen3Config, *, check_dependencies: bool = True) -> dict[str, object]:
    """모델·데이터·선택 의존성을 확인하고 GPU 메모리 사용 전 종료합니다."""

    model = validate_model_dir(config.model_dir)
    allowed = set(config.allowed_licenses)
    train_data = load_chat_jsonl(config.train_data, split="train", allowed_licenses=allowed)
    heldout_data = load_chat_jsonl(config.heldout_data, split="heldout", allowed_licenses=allowed)
    train_prompts = {item.prompt_sha256 for item in train_data.examples}
    heldout_prompts = {item.prompt_sha256 for item in heldout_data.examples}
    if overlap := train_prompts & heldout_prompts:
        raise IntegrityError(f"train/heldout final-user prompt가 겹칩니다: {len(overlap)}개")
    if check_dependencies:
        require_optional_dependencies()
    return {
        **model,
        "train_rows": len(train_data.examples),
        "heldout_rows": len(heldout_data.examples),
        "dependencies_checked": check_dependencies,
    }


def _libraries() -> tuple[Any, Any, Any]:
    require_optional_dependencies()
    return (
        importlib.import_module("transformers"),
        importlib.import_module("peft"),
        importlib.import_module("torch"),
    )


def _load(config: Qwen3Config, *, adapter_dir: Path | None = None) -> tuple[Any, Any]:
    transformers, peft, torch = _libraries()
    dtype = getattr(torch, config.qlora.compute_dtype)
    quantization = transformers.BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=config.qlora.quant_type,
        bnb_4bit_use_double_quant=config.qlora.double_quant,
        bnb_4bit_compute_dtype=dtype,
    )
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        config.model_dir, local_files_only=True, trust_remote_code=False
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = transformers.AutoModelForCausalLM.from_pretrained(
        config.model_dir,
        local_files_only=True,
        trust_remote_code=False,
        quantization_config=quantization,
        torch_dtype=dtype,
        device_map={"": 0},
    )
    if adapter_dir is not None:
        return peft.PeftModel.from_pretrained(model, adapter_dir, is_trainable=False), tokenizer
    model = peft.prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=config.gradient_checkpointing
    )
    lora = peft.LoraConfig(
        task_type="CAUSAL_LM",
        r=config.qlora.rank,
        lora_alpha=config.qlora.alpha,
        lora_dropout=config.qlora.dropout,
        target_modules=config.qlora.target_modules,
        bias="none",
    )
    return peft.get_peft_model(model, lora), tokenizer


def _datasets(config: Qwen3Config, tokenizer: Any) -> tuple[Qwen3ChatDataset, Qwen3ChatDataset]:
    allowed = set(config.allowed_licenses)
    train_data = load_chat_jsonl(config.train_data, split="train", allowed_licenses=allowed)
    heldout_data = load_chat_jsonl(config.heldout_data, split="heldout", allowed_licenses=allowed)
    eval_examples = heldout_data.examples[: config.max_eval_examples]
    return (
        Qwen3ChatDataset(train_data.examples, tokenizer, max_length=config.sequence_length),
        Qwen3ChatDataset(eval_examples, tokenizer, max_length=config.sequence_length),
    )


def _trainer(config: Qwen3Config, model: Any, tokenizer: Any, *, training: bool) -> Any:
    transformers, _, _ = _libraries()
    train_data, eval_data = _datasets(config, tokenizer)
    arguments = transformers.TrainingArguments(
        output_dir=str(config.output_dir),
        max_steps=config.max_steps,
        learning_rate=config.learning_rate,
        warmup_steps=config.warmup_steps,
        per_device_train_batch_size=config.micro_batch_size,
        per_device_eval_batch_size=config.eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        logging_steps=config.logging_steps,
        eval_steps=config.eval_steps,
        save_steps=config.save_steps,
        eval_strategy="steps" if training else "no",
        save_strategy="steps" if training else "no",
        bf16=config.qlora.compute_dtype == "bfloat16",
        fp16=config.qlora.compute_dtype == "float16",
        gradient_checkpointing=config.gradient_checkpointing,
        remove_unused_columns=False,
        report_to=[],
        seed=config.seed,
    )
    if tokenizer.pad_token_id is None:
        raise IntegrityError("tokenizer에 pad_token_id 또는 eos_token_id가 없습니다")
    return transformers.Trainer(
        model=model,
        args=arguments,
        train_dataset=train_data if training else None,
        eval_dataset=eval_data,
        data_collator=Qwen3DataCollator(tokenizer.pad_token_id),
    )


def train(config: Qwen3Config) -> dict[str, object]:
    """QLoRA adapter를 학습하고 tokenizer와 함께 저장합니다."""

    preflight(config)
    model, tokenizer = _load(config)
    trainer = _trainer(config, model, tokenizer, training=True)
    result = trainer.train()
    trainer.save_model(str(config.output_dir))
    tokenizer.save_pretrained(config.output_dir)
    return {
        "output_dir": str(config.output_dir),
        "global_step": result.global_step,
        "training_loss": result.training_loss,
    }


def evaluate(config: Qwen3Config, adapter_dir: Path | None = None) -> dict[str, object]:
    """저장한 adapter의 heldout loss를 계산합니다."""

    target = adapter_dir or config.output_dir
    if not target.is_dir():
        raise InputError(f"평가할 PEFT adapter 디렉터리가 없습니다: {target}")
    preflight(config)
    model, tokenizer = _load(config, adapter_dir=target)
    metrics = _trainer(config, model, tokenizer, training=False).evaluate()
    return {"adapter_dir": str(target), **metrics}


def generate(config: Qwen3Config, adapter_dir: Path, prompt: str, *, max_new_tokens: int = 128) -> dict[str, object]:
    """adapter를 로드해 한 턴을 생성하고 언어 gate 결과를 반환합니다."""

    if not adapter_dir.is_dir():
        raise InputError(f"추론할 PEFT adapter 디렉터리가 없습니다: {adapter_dir}")
    model, tokenizer = _load(config, adapter_dir=adapter_dir)
    transformers, _, torch = _libraries()
    messages = [{"role": "system", "content": system_prompt(prompt)}, {"role": "user", "content": prompt}]
    encoded = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, enable_thinking=False, return_tensors="pt"
    )
    if hasattr(encoded, "input_ids"):
        encoded = encoded.input_ids
    elif isinstance(encoded, dict):
        encoded = encoded["input_ids"]
    if hasattr(encoded, "to"):
        encoded = encoded.to(model.device)
    with torch.inference_mode():
        output = model.generate(encoded, max_new_tokens=max_new_tokens, do_sample=False, eos_token_id=tokenizer.eos_token_id)
    answer = tokenizer.decode(output[0][encoded.shape[-1] :], skip_special_tokens=True).strip()
    return {"prompt": prompt, "answer": answer, "language_gate": language_gate(prompt, answer)}
