from pydantic import Field

from shared.contracts.models import ContractModel


class TrainingConfig(ContractModel):
    model_name: str = "Qwen3-8B"
    output_dir: str = "artifacts/lab1/adapters"
    max_seq_length: int = Field(default=4096, ge=128)
    learning_rate: float = Field(default=2e-4, gt=0)
    num_train_epochs: int = Field(default=1, ge=1)
    per_device_batch_size: int = Field(default=1, ge=1)
    gradient_accumulation_steps: int = Field(default=8, ge=1)
    lora_rank: int = Field(default=16, ge=1)
    lora_alpha: int = Field(default=32, ge=1)
    lora_dropout: float = Field(default=0.05, ge=0, lt=1)
    use_lora: bool = True
    bf16: bool = True
    use_qlora: bool = False
    seed: int = 42
