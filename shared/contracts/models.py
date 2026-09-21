from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import PriceStatus, ProductType, UsageType, ValidationStatus, WorkflowState


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


class GPUOption(ContractModel):
    gpu_id: str
    name: str
    memory_gb: int = Field(gt=0)
    supported_product_ids: list[str] = Field(default_factory=list)
    supported_product_types: list[ProductType] = Field(default_factory=list)
    price_vnd: int | None = Field(default=None, ge=0)
    source_urls: list[str] = Field(default_factory=list)

    def supports(self, product: Product) -> bool:
        return (
            product.id in self.supported_product_ids
            or product.product_type in self.supported_product_types
        )


class RAMOption(ContractModel):
    option_id: str
    capacity_gb: int = Field(gt=0)
    supported_product_ids: list[str] = Field(default_factory=list)
    price_vnd: int | None = Field(default=None, ge=0)
    source_urls: list[str] = Field(default_factory=list)

    def supports(self, product: Product) -> bool:
        return product.id in self.supported_product_ids


class StorageOption(RAMOption):
    storage_type: str | None = None


class PriceBreakdown(ContractModel):
    base_chassis_vnd: int | None = Field(default=None, ge=0)
    gpu_vnd: int | None = Field(default=None, ge=0)
    ram_vnd: int | None = Field(default=None, ge=0)
    storage_vnd: int | None = Field(default=None, ge=0)
    cpu_vnd: int | None = Field(default=None, ge=0)
    total_vnd: int | None = Field(default=None, ge=0)
    missing_components: list[str] = Field(
        default_factory=lambda: ["base_chassis", "gpu", "ram", "storage", "cpu"]
    )
    status: PriceStatus = PriceStatus.UNKNOWN

    @model_validator(mode="after")
    def check_complete(self) -> "PriceBreakdown":
        components = {
            "base_chassis": self.base_chassis_vnd,
            "gpu": self.gpu_vnd,
            "ram": self.ram_vnd,
            "storage": self.storage_vnd,
            "cpu": self.cpu_vnd,
        }
        values = list(components.values())
        missing = [name for name, value in components.items() if value is None]
        total = sum(value for value in values if value is not None)
        if self.total_vnd is not None and self.total_vnd != total:
            raise ValueError("Price total must equal its component sum")
        if self.status == PriceStatus.COMPLETE and missing:
            raise ValueError("COMPLETE price requires all components")
        expected_status = (
            PriceStatus.COMPLETE
            if not missing
            else PriceStatus.UNKNOWN
            if len(missing) == len(components)
            else PriceStatus.PARTIAL
        )
        if self.status != expected_status:
            raise ValueError("Price status must match actual component completeness")
        if sorted(self.missing_components) != sorted(missing):
            raise ValueError("missing_components must match actual missing price components")
        if self.status == PriceStatus.COMPLETE and self.total_vnd is None:
            raise ValueError("Complete price must have a total")
        return self


class ProductConfiguration(ContractModel):
    configuration_id: str
    product: Product
    selected_gpu: GPUOption | None = None
    gpu_count: int | None = Field(default=None, ge=1)
    configured_ram_gb: int | None = Field(default=None, ge=1)
    configured_storage_gb: int | None = Field(default=None, ge=1)
    selected_cpu: str | None = None
    selected_ram: RAMOption | None = None
    selected_storage: StorageOption | None = None
    price_breakdown: PriceBreakdown | None = None
    estimated_price_vnd: int | None = Field(default=None, ge=0)
    price_status: PriceStatus = PriceStatus.UNKNOWN
    priced_components: list[str] = Field(default_factory=list)
    missing_price_components: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)

    @property
    def total_vram_gb(self) -> int | None:
        if self.selected_gpu is None or self.gpu_count is None:
            return None
        return self.selected_gpu.memory_gb * self.gpu_count

    def pricing_state_is_consistent(self) -> bool:
        """Check mutable pricing mirrors against the validated canonical breakdown."""
        if (
            not isinstance(self.price_status, PriceStatus)
            or (
                self.estimated_price_vnd is not None
                and (type(self.estimated_price_vnd) is not int or self.estimated_price_vnd < 0)
            )
            or not isinstance(self.priced_components, list)
            or not all(isinstance(name, str) for name in self.priced_components)
            or not isinstance(self.missing_price_components, list)
            or not all(isinstance(name, str) for name in self.missing_price_components)
        ):
            return False
        if self.price_breakdown is None:
            return (
                self.price_status == PriceStatus.UNKNOWN
                and self.estimated_price_vnd is None
                and self.priced_components == []
                and self.missing_price_components == []
            )
        if not isinstance(self.price_breakdown, PriceBreakdown):
            return False
        try:
            breakdown = PriceBreakdown.model_validate(
                self.price_breakdown.model_dump(mode="python")
            )
        except ValueError:
            return False
        components = {
            "base_chassis": breakdown.base_chassis_vnd,
            "gpu": breakdown.gpu_vnd,
            "ram": breakdown.ram_vnd,
            "storage": breakdown.storage_vnd,
            "cpu": breakdown.cpu_vnd,
        }
        expected_priced = [name for name, value in components.items() if value is not None]
        return (
            self.price_status == breakdown.status
            and self.estimated_price_vnd == breakdown.total_vnd
            and len(self.priced_components) == len(set(self.priced_components))
            and sorted(self.priced_components) == sorted(expected_priced)
            and len(self.missing_price_components) == len(set(self.missing_price_components))
            and sorted(self.missing_price_components) == sorted(breakdown.missing_components)
        )

    @model_validator(mode="after")
    def sync_options(self) -> "ProductConfiguration":
        for option_name, capacity_name in (
            ("selected_ram", "configured_ram_gb"),
            ("selected_storage", "configured_storage_gb"),
        ):
            option = getattr(self, option_name)
            if option is not None:
                capacity = getattr(self, capacity_name)
                if capacity is not None and capacity != option.capacity_gb:
                    raise ValueError(f"{capacity_name} must match selected option")
                setattr(self, capacity_name, option.capacity_gb)
        if self.price_breakdown is None:
            if (
                self.price_status != PriceStatus.UNKNOWN
                or self.estimated_price_vnd is not None
                or self.priced_components
                or self.missing_price_components
            ):
                raise ValueError("Pricing fields require price_breakdown")
            return self
        self.price_status = self.price_breakdown.status
        self.estimated_price_vnd = self.price_breakdown.total_vnd
        self.priced_components = [
            name
            for name, value in {
                "base_chassis": self.price_breakdown.base_chassis_vnd,
                "gpu": self.price_breakdown.gpu_vnd,
                "ram": self.price_breakdown.ram_vnd,
                "storage": self.price_breakdown.storage_vnd,
                "cpu": self.price_breakdown.cpu_vnd,
            }.items()
            if value is not None
        ]
        self.missing_price_components = list(self.price_breakdown.missing_components)
        if self.price_status == PriceStatus.COMPLETE and self.missing_price_components:
            raise ValueError("Complete price cannot have missing components")
        return self


class ProductFilter(ContractModel):
    min_ram_gb: int | None = Field(default=None, ge=0)
    min_gpu_count: int | None = Field(default=None, ge=0)
    max_base_price_vnd: int | None = Field(default=None, ge=0)
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


class DocumentHit(ContractModel):
    chunk: DocumentChunk
    retrieval_score: float | None = None
    rerank_score: float | None = None
    rank: int = Field(ge=1)
    retrieval_method: str


class DocumentSearchRequest(ContractModel):
    query: str = Field(min_length=1)
    product_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class DocumentSearchResult(ContractModel):
    hits: list[DocumentHit] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class EmbeddingVector(ContractModel):
    dense: list[float] = Field(default_factory=list)
    sparse_indices: list[int] = Field(default_factory=list)
    sparse_values: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sparse_shape(self) -> "EmbeddingVector":
        if len(self.sparse_indices) != len(self.sparse_values):
            raise ValueError("sparse_indices and sparse_values must have equal length")
        if any(index < 0 for index in self.sparse_indices):
            raise ValueError("sparse indices must be non-negative")
        return self


class SizingRequest(ContractModel):
    model_parameters_b: float = Field(gt=0)
    usage: UsageType
    quantization: str | None = None
    context_length: int | None = Field(default=None, ge=1)
    concurrent_users: int | None = Field(default=None, ge=1)
    training_method: str | None = None
    additional_overhead: float = Field(default=1.2, ge=1)


class SizingResult(ContractModel):
    estimated_model_memory_gb: float = Field(ge=0)
    recommended_total_vram_gb: float = Field(ge=0)
    recommended_system_ram_gb: int = Field(ge=0)
    recommended_storage_gb: int | None = Field(default=None, ge=0)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ProductCandidate(ContractModel):
    configuration: ProductConfiguration
    fit_reasons: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)

    @property
    def product(self) -> Product:
        return self.configuration.product


class ValidationFailure(ContractModel):
    field: str
    message: str
    actual: Any = None
    required: Any = None


class ValidationResult(ContractModel):
    status: ValidationStatus
    failures: list[ValidationFailure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unknown_fields: list[str] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.status == ValidationStatus.PASS


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


class ResolvedProductFact(ContractModel):
    product_id: str
    field_name: str
    value: Any
    source_url: str
    document_id: str
    page: int | None = Field(default=None, ge=1)
    chunk_id: str
    evidence_text: str
    confidence: float = Field(default=1.0, ge=0, le=1)
    verified: bool = False


class EvidenceKind(StrEnum):
    DIRECT = "direct"
    DERIVED = "derived"


class Evidence(ContractModel):
    claim: str
    value: Any
    source_url: str | None = None
    product_id: str
    kind: EvidenceKind = EvidenceKind.DIRECT
    derivation_rule: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    document_id: str | None = None
    chunk_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    verified: bool = False


class ProposalOption(ContractModel):
    name: str
    configuration: ProductConfiguration
    rationale: str
    estimated_price_vnd: int | None = None
    limitations: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class Proposal(ContractModel):
    customer_requirement: CustomerRequirement
    interpreted_workload: str
    sizing_result: SizingResult
    selected_configurations: list[ProductConfiguration] = Field(default_factory=list)
    options: list[ProposalOption] = Field(default_factory=list)
    comparison: ComparisonResult | None = None
    technical_claims: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    technical_reasoning: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    unknown_information: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    estimated_price_vnd: int | None = None
    created_at: datetime | None = None


class ProposalVerificationResult(ContractModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class WorkflowContext(ContractModel):
    requirement: CustomerRequirement
    state: WorkflowState = WorkflowState.RECEIVED
    missing_fields: list[str] = Field(default_factory=list)
    missing_information: MissingInformation | None = None
    sizing_result: SizingResult | None = None
    configurations: list[ProductConfiguration] = Field(default_factory=list)
    candidates: list[ProductCandidate] = Field(default_factory=list)
    validation_results: dict[str, ValidationResult] = Field(default_factory=dict)
    document_hits: list[DocumentHit] = Field(default_factory=list)
    resolved_facts: list[ResolvedProductFact] = Field(default_factory=list)
    comparison: ComparisonResult | None = None
    proposal: Proposal | None = None
    errors: list[str] = Field(default_factory=list)
    history: list[WorkflowState] = Field(default_factory=list)


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
        else:
            if self.data is not None:
                raise ValueError("Failed tool result cannot contain data")
            if self.error is None or not self.error.strip():
                raise ValueError("Failed tool result requires a nonblank error")
        return self
