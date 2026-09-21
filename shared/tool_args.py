"""Argument contracts shared by tool schemas, runtime and dataset validation."""
from pydantic import Field

from shared.contracts import ProductFilter, UsageType
from shared.contracts.models import ContractModel


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


TOOL_ARG_MODELS = {
    "search_products": SearchProductsArgs,
    "get_product": GetProductArgs,
    "search_product_documents": SearchProductDocumentsArgs,
    "compare_products": CompareProductsArgs,
    "compare_configurations": CompareConfigurationsArgs,
    "estimate_ai_requirements": EstimateAIRequirementsArgs,
}
