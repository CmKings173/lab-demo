"""Lab 1 v1 tool wire contract, pinned independently of later lab extensions.

Do not change these models without intentionally versioning and rebuilding Lab 1.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    """Base contract pinned to the Lab 1 v1 wire format."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class ProductType(StrEnum):
    AI_SERVER = "ai_server"
    AI_WORKSTATION = "ai_workstation"


class UsageType(StrEnum):
    INFERENCE = "inference"
    FINE_TUNE = "fine_tune"


class PriceStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class CustomerRequirement(ContractModel):
    model_size_b: float | None = Field(default=None, gt=0)
    usage: UsageType | None = None
    budget_vnd: int | None = Field(default=None, gt=0)
    concurrent_users: int | None = Field(default=None, ge=1)
    context_length: int | None = Field(default=None, ge=1)
    storage_requirement_gb: int | None = Field(default=None, ge=1)
    expansion_requirement: str | None = None
    training_method: str | None = None

    def missing_required_fields(self) -> list[str]:
        return [
            field
            for field in ("model_size_b", "usage", "budget_vnd")
            if getattr(self, field) is None
        ]


class ToolCall(ContractModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(ContractModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    parameters: dict[str, Any]


class ChatMessage(ContractModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None


class ModelResponse(ContractModel):
    message: ChatMessage
    finish_reason: str | None = None


class ProductFilter(ContractModel):
    min_ram_gb: int | None = Field(default=None, ge=0)
    min_gpu_count: int | None = Field(default=None, ge=0)
    max_base_price_vnd: int | None = Field(default=None, ge=0)
    product_type: ProductType | None = None


class SearchProductsArgs(ContractModel):
    filters: ProductFilter = Field(default_factory=ProductFilter)
    query: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class GetProductArgs(ContractModel):
    product_id: str = Field(min_length=1)


class SearchProductDocumentsArgs(ContractModel):
    query: str = Field(min_length=1)
    product_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class CompareProductsArgs(ContractModel):
    product_ids: list[str] = Field(min_length=2)


class CompareConfigurationsArgs(ContractModel):
    configuration_ids: list[str] = Field(min_length=2)


class EstimateAIRequirementsArgs(ContractModel):
    model_parameters_b: float = Field(gt=0)
    usage: UsageType
    quantization: str | None = None
    context_length: int | None = Field(default=None, ge=1)
    concurrent_users: int | None = Field(default=None, ge=1)
    training_method: str | None = None


class Product(ContractModel):
    id: str
    sku: str
    name: str
    manufacturer: str
    product_type: ProductType
    platform: str | None = None
    cpu_options: list[str] = Field(default_factory=list)
    max_ram_gb: int | None = Field(default=None, ge=0)
    max_gpu_slots: int | None = Field(default=None, ge=0)
    max_storage_gb: int | None = Field(default=None, ge=0)
    storage_slots: int | None = Field(default=None, ge=0)
    power_w: int | None = Field(default=None, ge=0)
    form_factor: str | None = None
    base_price_vnd: int | None = Field(default=None, ge=0)
    base_price_includes: set[Literal["chassis", "cpu", "ram", "storage"]] = Field(
        default_factory=lambda: {"chassis"}
    )
    availability: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class ProductSearchResult(ContractModel):
    products: list[Product] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class DocumentChunk(ContractModel):
    id: str
    text: str = Field(min_length=1)
    source_url: str | None = None
    product_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    metadata: dict[str, str] = Field(default_factory=dict)


class DocumentHit(ContractModel):
    chunk: DocumentChunk
    retrieval_score: float | None = None
    rerank_score: float | None = None
    rank: int = Field(ge=1)
    retrieval_method: str


class DocumentSearchResult(ContractModel):
    hits: list[DocumentHit] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class SizingResult(ContractModel):
    estimated_model_memory_gb: float = Field(ge=0)
    recommended_total_vram_gb: float = Field(ge=0)
    recommended_system_ram_gb: int = Field(ge=0)
    recommended_storage_gb: int | None = Field(default=None, ge=0)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ConfigurationComparison(ContractModel):
    configuration_id: str
    product_id: str
    gpu_model: str | None = None
    gpu_count: int | None = None
    total_vram_gb: int | None = None
    configured_ram_gb: int | None = None
    configured_storage_gb: int | None = None
    price_status: PriceStatus
    estimated_price_vnd: int | None = None
    known_limitations: list[str] = Field(default_factory=list)
    unknown_facts: list[str] = Field(default_factory=list)


class ComparisonResult(ContractModel):
    product_ids: list[str]
    configuration_ids: list[str] = Field(default_factory=list)
    configurations: list[ConfigurationComparison] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    summary: str


T = TypeVar("T")


class ToolResult(ContractModel, Generic[T]):
    ok: bool
    data: T | None = None
    error: str | None = None

    @model_validator(mode="after")
    def check_result_state(self) -> "ToolResult[T]":
        if self.ok:
            if self.error is not None:
                raise ValueError("Successful tool result cannot contain an error")
        elif self.data is not None:
            raise ValueError("Failed tool result cannot contain data")
        elif self.error is None or not self.error.strip():
            raise ValueError("Failed tool result requires a nonblank error")
        return self


TOOL_ARG_MODELS = {
    "search_products": SearchProductsArgs,
    "get_product": GetProductArgs,
    "search_product_documents": SearchProductDocumentsArgs,
    "compare_products": CompareProductsArgs,
    "compare_configurations": CompareConfigurationsArgs,
    "estimate_ai_requirements": EstimateAIRequirementsArgs,
}
TOOL_DEFINITIONS = [
    ToolDefinition.model_validate(item)
    for item in json.loads(
        Path(__file__).with_name("frozen_tool_definitions.json").read_text(encoding="utf-8")
    )
]
