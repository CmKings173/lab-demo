from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from .enums import ProductType, UsageType, WorkflowState


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class CustomerRequirement(ContractModel):
    """Customer input; optional fields allow a controlled missing-data path."""

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


class MissingInformation(ContractModel):
    status: str = "missing_information"
    missing_fields: list[str] = Field(min_length=1)
    question: str


class Product(ContractModel):
    id: str
    sku: str
    name: str
    manufacturer: str
    product_type: ProductType
    category: str | None = None
    cpu: str | None = None
    supported_gpu: list[str] = Field(default_factory=list)
    max_gpu_count: int | None = Field(default=None, ge=0)
    vram_gb: int | None = Field(default=None, ge=0)
    default_ram_gb: int | None = Field(default=None, ge=0)
    max_ram_gb: int | None = Field(default=None, ge=0)
    storage_gb: int | None = Field(default=None, ge=0)
    storage_slots: int | None = Field(default=None, ge=0)
    power_w: int | None = Field(default=None, ge=0)
    form_factor: str | None = None
    price_vnd: int | None = Field(default=None, ge=0)
    availability: str | None = None
    product_url: str | None = None
    datasheet_url: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductFilter(ContractModel):
    min_ram_gb: int | None = Field(default=None, ge=0)
    min_gpu_count: int | None = Field(default=None, ge=0)
    min_vram_gb: int | None = Field(default=None, ge=0)
    max_price_vnd: int | None = Field(default=None, ge=0)
    product_type: ProductType | None = None


class ProductSearchRequest(ContractModel):
    filters: ProductFilter = Field(default_factory=ProductFilter)
    query: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


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


class DocumentSearchRequest(ContractModel):
    query: str = Field(min_length=1)
    product_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class DocumentSearchResult(ContractModel):
    chunks: list[DocumentChunk] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class SizingRequest(ContractModel):
    model_parameters_b: float = Field(gt=0)
    usage: UsageType
    quantization: str | None = None
    context_length: int | None = Field(default=None, ge=1)
    concurrent_users: int | None = Field(default=None, ge=1)
    training_method: str | None = None
    additional_overhead: float = Field(default=1.2, ge=1)


class SizingResult(ContractModel):
    estimated_vram_gb: float = Field(ge=0)
    recommended_vram_gb: float = Field(ge=0)
    recommended_ram_gb: int = Field(ge=0)
    minimum_gpu_count: int = Field(ge=0)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ProductCandidate(ContractModel):
    product: Product
    fit_reasons: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class ValidationFailure(ContractModel):
    field: str
    message: str
    actual: Any = None
    required: Any = None


class ValidationResult(ContractModel):
    valid: bool
    failures: list[ValidationFailure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unknown_fields: list[str] = Field(default_factory=list)


class ComparisonResult(ContractModel):
    product_ids: list[str]
    dimensions: list[str] = Field(default_factory=list)
    summary: str


class ProposalOption(ContractModel):
    name: str
    products: list[ProductCandidate] = Field(default_factory=list)
    rationale: str
    estimated_price_vnd: int | None = None
    limitations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class Proposal(ContractModel):
    customer_requirement: CustomerRequirement
    interpreted_workload: str
    sizing_result: SizingResult
    selected_products: list[ProductCandidate] = Field(default_factory=list)
    options: list[ProposalOption] = Field(default_factory=list)
    technical_reasoning: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    unknown_information: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    estimated_price_vnd: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowContext(ContractModel):
    requirement: CustomerRequirement
    state: WorkflowState = WorkflowState.RECEIVED
    missing_fields: list[str] = Field(default_factory=list)
    sizing_result: SizingResult | None = None
    candidates: list[ProductCandidate] = Field(default_factory=list)
    validation_results: dict[str, ValidationResult] = Field(default_factory=dict)
    proposal: Proposal | None = None
    errors: list[str] = Field(default_factory=list)
    history: list[WorkflowState] = Field(default_factory=list)


T = TypeVar("T")


class ToolResult(ContractModel, Generic[T]):
    ok: bool
    data: T | None = None
    error: str | None = None
