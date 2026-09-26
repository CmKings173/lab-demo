from __future__ import annotations

# ruff: noqa: E501
from dataclasses import dataclass
from random import Random

from lab1_finetune.data.frozen_contracts import ProductType, UsageType
from lab1_finetune.data.schema import ScenarioType


@dataclass(frozen=True)
class ScenarioContext:
    domain: str
    model_name: str
    model_size_b: float
    usage: UsageType
    budget_vnd: int
    concurrent_users: int
    context_length: int
    storage_gb: int
    product_type: ProductType


DOMAINS = (
    "chatbot nội bộ cho phòng nhân sự",
    "hỏi đáp tài liệu pháp chế",
    "trợ lý viết mã cho nhóm kỹ thuật",
    "tìm kiếm tri thức cho bộ phận chăm sóc khách hàng",
    "trợ lý nghiên cứu cho nhóm phân tích dữ liệu",
    "API tóm tắt tài liệu trong mạng nội bộ",
    "trợ lý vận hành cho đội hạ tầng",
    "hệ thống phân loại yêu cầu hỗ trợ",
    "trợ lý soạn thảo tài liệu kỹ thuật",
    "dịch vụ hỏi đáp cho nhóm bán hàng",
    "nền tảng thử nghiệm model tại phòng R&D",
    "trợ lý tra cứu quy trình sản xuất",
)

MODELS = ("Qwen", "Llama", "Mistral", "Qwen coder", "Yi", "Llama coder")
MODEL_SIZES = (7.0, 8.0, 14.0, 32.0, 34.0, 70.0)
BUDGETS = (120_000_000, 180_000_000, 240_000_000, 320_000_000, 500_000_000, 800_000_000)
CONCURRENCY = (2, 3, 4, 6, 7, 10, 13, 16, 17, 19, 23, 24, 29, 31, 37, 41, 47, 53, 61, 71)
CONTEXT_LENGTHS = (
    4096,
    5120,
    6144,
    7168,
    7680,
    8192,
    8704,
    9216,
    12288,
    14336,
    16384,
    18432,
    18944,
    24576,
    25600,
    26624,
    27648,
    28672,
    30720,
    31744,
    32768,
)
STORAGE_GB = (512, 1024, 2048, 4096)


def context_for(seed_or_index: int | str, index: int | None = None, *, fine_tune: bool = False) -> ScenarioContext:
    """Choose each context field independently from a deterministic local PRNG."""
    key = str(seed_or_index) if index is None else f"{seed_or_index}:{index}"
    rng = Random(key)
    model_size = rng.choice(MODEL_SIZES)
    usage = UsageType.FINE_TUNE if fine_tune else UsageType.INFERENCE
    return ScenarioContext(
        domain=rng.choice(DOMAINS),
        model_name=f"{rng.choice(MODELS)} {int(model_size)}B",
        model_size_b=model_size,
        usage=usage,
        budget_vnd=rng.choice(BUDGETS),
        concurrent_users=rng.choice(CONCURRENCY),
        context_length=rng.choice(CONTEXT_LENGTHS),
        storage_gb=rng.choice(STORAGE_GB),
        product_type=rng.choice((ProductType.AI_SERVER, ProductType.AI_WORKSTATION)),
    )


def context_for_scenario(
    *,
    seed: int,
    index: int,
    scenario_type: ScenarioType,
    persona_id: str | None = None,
) -> ScenarioContext:
    """Build deterministic context values that obey scenario invariants."""
    base = context_for(f"{seed}:{persona_id or 'default'}", index)
    rng = Random(f"{seed}:{index}:{scenario_type.value}:{persona_id or 'default'}")

    if scenario_type == ScenarioType.LARGE_MODEL_LOW_BUDGET:
        model_size = rng.choice((32.0, 34.0, 70.0))
        budget = rng.choice((120_000_000, 180_000_000, 240_000_000))
        return ScenarioContext(
            **{
                **base.__dict__,
                "model_size_b": model_size,
                "budget_vnd": budget,
                "model_name": f"{rng.choice(MODELS)} {int(model_size)}B",
            }
        )
    if scenario_type in {ScenarioType.FINETUNE_32B_SOLUTION, ScenarioType.GENERAL_LORA}:
        model_size = rng.choice((32.0, 34.0, 70.0))
        return ScenarioContext(
            **{
                **base.__dict__,
                "model_size_b": model_size,
                "usage": UsageType.FINE_TUNE,
                "model_name": f"{rng.choice(MODELS)} {int(model_size)}B",
            }
        )
    if scenario_type == ScenarioType.SEARCH_WORKSTATION_BY_RAM:
        return ScenarioContext(**{**base.__dict__, "product_type": ProductType.AI_WORKSTATION})
    if scenario_type == ScenarioType.SEARCH_SERVER_BY_GPU_SLOTS:
        return ScenarioContext(**{**base.__dict__, "product_type": ProductType.AI_SERVER})
    if scenario_type == ScenarioType.CONTRADICTORY_REQUIREMENT:
        model_size = rng.choice((32.0, 70.0))
        return ScenarioContext(
            **{
                **base.__dict__,
                "model_size_b": model_size,
                "model_name": f"{rng.choice(MODELS)} {int(model_size)}B",
            }
        )
    return base
