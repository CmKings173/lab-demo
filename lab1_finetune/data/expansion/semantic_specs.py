"""Small semantic request objects shared by wording and data generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from lab1_finetune.data.expansion.scenarios import ScenarioContext
from lab1_finetune.data.frozen_contracts import ProductFilter, ProductType


@dataclass(frozen=True)
class ComparisonSpec:
    target_type: Literal["product", "configuration"]
    target_ids: tuple[str, str]

    def __post_init__(self) -> None:
        if any(not target_id for target_id in self.target_ids):
            raise ValueError("Comparison targets must be non-empty")
        if self.target_ids[0] == self.target_ids[1]:
            raise ValueError("Comparison targets must be distinct")


class MultiToolFlow(StrEnum):
    ESTIMATE_THEN_SEARCH = "estimate_then_search"
    SEARCH_THEN_GET_THEN_DOCUMENT = "search_then_get_then_document"
    SEARCH_THEN_GET = "search_then_get"
    GET_THEN_DOCUMENT = "get_then_document"


MULTI_TOOL_FLOW_SCHEDULE = (
    MultiToolFlow.ESTIMATE_THEN_SEARCH,
    MultiToolFlow.SEARCH_THEN_GET_THEN_DOCUMENT,
    MultiToolFlow.ESTIMATE_THEN_SEARCH,
    MultiToolFlow.SEARCH_THEN_GET_THEN_DOCUMENT,
    MultiToolFlow.SEARCH_THEN_GET,
    MultiToolFlow.GET_THEN_DOCUMENT,
)


@dataclass(frozen=True)
class MultiToolFlowSpec:
    flow: MultiToolFlow
    product_id: str
    product_type: ProductType
    filters: ProductFilter | None = None
    document_field: Literal["max_ram_gb", "max_gpu_slots"] | None = None


@dataclass(frozen=True)
class TechnicalFactSpec:
    product_id: str
    field_name: Literal["max_ram_gb", "max_gpu_slots"]


@dataclass(frozen=True)
class RequirementChangeSpec:
    old: ScenarioContext
    new: ScenarioContext

    @property
    def changed_fields(self) -> frozenset[str]:
        return frozenset(
            field
            for field in ("model_size_b", "usage", "budget_vnd", "concurrent_users")
            if getattr(self.old, field) != getattr(self.new, field)
        )

    @property
    def template_id(self) -> str:
        templates = {
            frozenset({"model_size_b"}): "requirement_change_model_v3",
            frozenset({"usage"}): "requirement_change_usage_v3",
            frozenset({"budget_vnd"}): "requirement_change_budget_v3",
            frozenset({"model_size_b", "concurrent_users"}): "requirement_change_multiple_v3",
        }
        try:
            return templates[self.changed_fields]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported requirement delta: {sorted(self.changed_fields)}"
            ) from exc


@dataclass(frozen=True)
class ContradictionSpec:
    subtype: Literal[
        "single_gpu_vs_large_model", "context_vram_constraint", "large_model_low_budget"
    ]
    context: ScenarioContext
    gpu_memory_gb: int | None = None
