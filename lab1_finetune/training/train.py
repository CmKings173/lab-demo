"""LoRA supervised fine-tuning for the frozen Lab 1 Qwen exports."""

import argparse
import hashlib
import json
import re
from importlib.metadata import version
from pathlib import Path
from typing import Any

from lab1_finetune.training.config import TrainingConfig
from lab1_finetune.training.data import load_qwen_export


def validate_training_inputs(config: TrainingConfig) -> None:
    if not config.use_lora or config.use_qlora:
        raise ValueError("This trainer supports BF16 LoRA, not full fine-tuning or QLoRA")
    if not Path(config.model_name).is_dir() and not re.fullmatch(
        r"[0-9a-fA-F]{40}", config.model_revision or ""
    ):
        raise ValueError("Remote model requires model_revision pinned to a 40-character commit SHA")
    if config.train_file.resolve() == config.validation_file.resolve():
        raise ValueError("Training and validation files must be different")
    for path in (config.train_file, config.validation_file):
        if not path.is_file():
            raise FileNotFoundError(f"Qwen export not found: {path}")
    if config.output_dir.exists() and any(config.output_dir.iterdir()):
        raise ValueError(f"Output directory is not empty: {config.output_dir}")


def inspect_token_lengths(
    rows: list[dict[str, Any]], tokenizer: Any, max_seq_length: int
) -> dict[str, int]:
    """Reject truncation before it can remove tool calls or assistant answers."""
    lengths = []
    oversized = []
    for index, row in enumerate(rows, 1):
        token_ids = tokenizer.apply_chat_template(
            row["messages"], tools=row["tools"], tokenize=True, add_generation_prompt=False
        )
        if isinstance(token_ids, dict):
            token_ids = token_ids["input_ids"]
        count = len(token_ids)
        lengths.append(count)
        if count > max_seq_length:
            oversized.append((index, count))
    if oversized:
        example, count = oversized[0]
        raise ValueError(
            f"{len(oversized)} conversations exceed max_seq_length={max_seq_length}; "
            f"first row {example} has {count} tokens. Increase the limit or review data."
        )
    ordered = sorted(lengths)
    return {
        "count": len(ordered),
        "p95": ordered[int(0.95 * (len(ordered) - 1))],
        "max": ordered[-1],
    }


def _check_assistant_mask(tokenizer: Any, rows: list[dict[str, Any]]) -> None:
    """Verify the trainer's patched Qwen template supervises tool calls, not tool results."""
    plain_row = next(
        (row for row in rows if not any(message.get("tool_calls") for message in row["messages"])),
        None,
    )
    tool_row = next(
        (row for row in rows if any(message.get("tool_calls") for message in row["messages"])),
        None,
    )
    samples = [row for row in (plain_row, tool_row) if row is not None]
    for row in samples:
        encoded = tokenizer.apply_chat_template(
            row["messages"],
            tools=row["tools"],
            tokenize=True,
            add_generation_prompt=False,
            return_dict=True,
            return_assistant_tokens_mask=True,
        )
        ids = encoded["input_ids"]
        mask = encoded.get("assistant_masks")
        if mask is None or len(mask) != len(ids) or not any(mask) or all(mask):
            raise ValueError(
                "Qwen training template did not produce a usable assistant-only loss mask"
            )
        if row is tool_row:
            supervised = tokenizer.decode([token for token, selected in zip(ids, mask) if selected])
            if "<tool_call>" not in supervised or "<tool_response>" in supervised:
                raise ValueError("Assistant mask must include tool calls and exclude tool results")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_data_and_tokenizer(config: TrainingConfig) -> tuple[Any, list, list, dict]:
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Install the Lab 1 training dependencies before running training"
        ) from exc

    train_rows = load_qwen_export(config.train_file)
    validation_rows = load_qwen_export(config.validation_file)
    model_kwargs = {"local_files_only": config.local_files_only}
    if config.model_revision:
        model_kwargs["revision"] = config.model_revision
    tokenizer = AutoTokenizer.from_pretrained(config.model_name, **model_kwargs)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    lengths = {
        "train": inspect_token_lengths(train_rows, tokenizer, config.max_seq_length),
        "validation": inspect_token_lengths(validation_rows, tokenizer, config.max_seq_length),
    }
    return tokenizer, train_rows, validation_rows, lengths


def preflight(config: TrainingConfig) -> dict[str, Any]:
    """Check artifacts and token lengths without loading the 14B model."""
    validate_training_inputs(config)
    _, train_rows, validation_rows, lengths = _load_data_and_tokenizer(config)
    return {
        "train_examples": len(train_rows),
        "validation_examples": len(validation_rows),
        "token_lengths": lengths,
        "train_sha256": _sha256(config.train_file),
        "validation_sha256": _sha256(config.validation_file),
    }


def train(config: TrainingConfig) -> Path:
    """Train a BF16 LoRA adapter; keep independent gold evaluation untouched."""
    validate_training_inputs(config)
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:
        raise RuntimeError(
            "Install the Lab 1 training dependencies before running training"
        ) from exc
    if not torch.cuda.is_available():
        raise RuntimeError("A CUDA GPU is required for this training configuration")
    if config.bf16 and not torch.cuda.is_bf16_supported():
        raise RuntimeError("The CUDA GPU does not support BF16")

    tokenizer, train_rows, validation_rows, lengths = _load_data_and_tokenizer(config)
    model_kwargs: dict[str, Any] = {
        "local_files_only": config.local_files_only,
        "dtype": torch.bfloat16 if config.bf16 else torch.float32,
    }
    if config.model_revision:
        model_kwargs["revision"] = config.model_revision
    model = AutoModelForCausalLM.from_pretrained(config.model_name, **model_kwargs)
    model.config.use_cache = False
    lora_config = LoraConfig(
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=config.lora_target_modules,
        task_type=config.task_type,
    )
    arguments = SFTConfig(
        output_dir=str(config.output_dir),
        max_length=config.max_seq_length,
        eos_token="<|im_end|>",
        packing=False,
        assistant_only_loss=True,
        per_device_train_batch_size=config.per_device_batch_size,
        per_device_eval_batch_size=config.per_device_eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        gradient_checkpointing=config.gradient_checkpointing,
        learning_rate=config.learning_rate,
        num_train_epochs=config.num_train_epochs,
        lr_scheduler_type=config.lr_scheduler_type,
        warmup_ratio=config.warmup_ratio,
        weight_decay=config.weight_decay,
        eval_strategy=config.eval_strategy,
        save_strategy=config.save_strategy,
        save_total_limit=config.save_total_limit,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=config.bf16,
        seed=config.seed,
        data_seed=config.seed,
        report_to="none",
        push_to_hub=False,
    )
    trainer = SFTTrainer(
        model=model,
        args=arguments,
        train_dataset=Dataset.from_list(train_rows, on_mixed_types="use_json"),
        eval_dataset=Dataset.from_list(validation_rows, on_mixed_types="use_json"),
        processing_class=tokenizer,
        peft_config=lora_config,
    )
    _check_assistant_mask(trainer.processing_class, train_rows)
    result = trainer.train()
    adapter_path = config.output_dir / "best_adapter"
    trainer.save_model(str(adapter_path))
    trainer.processing_class.save_pretrained(str(adapter_path))
    manifest = {
        "config": config.model_dump(mode="json"),
        "train_sha256": _sha256(config.train_file),
        "validation_sha256": _sha256(config.validation_file),
        "token_lengths": lengths,
        "versions": {
            name: version(name)
            for name in ("torch", "transformers", "trl", "peft", "datasets", "accelerate")
        },
        "train_metrics": result.metrics,
    }
    (config.output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return adapter_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Lab 1 Qwen3-14B LoRA trainer")
    parser.add_argument("--model-name", default="Qwen/Qwen3-14B")
    parser.add_argument("--model-revision", help="Pinned Hugging Face commit SHA")
    parser.add_argument("--train-file", type=Path)
    parser.add_argument("--validation-file", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-seq-length", type=int)
    parser.add_argument("--num-train-epochs", type=int)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    overrides = {key: value for key, value in vars(args).items() if value is not None}
    preflight_only = overrides.pop("preflight_only")
    overrides["local_files_only"] = not overrides.pop("allow_download")
    config = TrainingConfig(**overrides)
    if preflight_only:
        print(json.dumps(preflight(config), ensure_ascii=False, indent=2))
    else:
        print(train(config))


if __name__ == "__main__":
    main()
