from pathlib import Path
from typing import Literal

from pydantic import Field

from shared.contracts.models import ContractModel


class TrainingConfig(ContractModel):
    model_name: str = "Qwen/Qwen3-14B"
    model_revision: str | None = None
    local_files_only: bool = True
    train_file: Path = Path("lab1_finetune/data/generated/exports/train_qwen.jsonl")
    validation_file: Path = Path("lab1_finetune/data/generated/exports/validation_qwen.jsonl")
    output_dir: Path = Path("artifacts/lab1/adapters")
    max_seq_length: int = Field(default=4096, ge=128, le=32768)
    learning_rate: float = Field(default=2e-4, gt=0)
    num_train_epochs: int = Field(default=3, ge=1)
    per_device_batch_size: int = Field(default=1, ge=1)
    per_device_eval_batch_size: int = Field(default=1, ge=1)
    gradient_accumulation_steps: int = Field(default=8, ge=1)
    lora_rank: int = Field(default=16, ge=1)
    lora_alpha: int = Field(default=32, ge=1)
    lora_dropout: float = Field(default=0.05, ge=0, lt=1)
    lora_target_modules: str = "all-linear"
    task_type: Literal["CAUSAL_LM"] = "CAUSAL_LM"
    use_lora: bool = True
    bf16: bool = True
    use_qlora: bool = False
    gradient_checkpointing: bool = True
    lr_scheduler_type: Literal["cosine"] = "cosine"
    warmup_ratio: float = Field(default=0.05, ge=0, lt=1)
    weight_decay: float = Field(default=0.01, ge=0)
    eval_strategy: Literal["epoch"] = "epoch"
    save_strategy: Literal["epoch"] = "epoch"
    save_total_limit: int = Field(default=2, ge=1)
    seed: int = 42
