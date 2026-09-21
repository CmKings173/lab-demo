from __future__ import annotations

from shared.contracts import (
    ComparisonResult,
    DocumentSearchRequest,
    DocumentSearchResult,
    Product,
    ProductFilter,
    ProductSearchRequest,
    ProductSearchResult,
    SizingRequest,
    SizingResult,
    ToolResult,
    UsageType,
)
from shared.interfaces import (
    ComparisonService,
    DocumentSearch,
    ProductRepository,
    SizingService,
)
from shared.interfaces.configuration_repository import ConfigurationRepository
from shared.tool_args import (
    CompareConfigurationsArgs,
    CompareProductsArgs,
    EstimateAIRequirementsArgs,
    GetProductArgs,
    SearchProductDocumentsArgs,
    SearchProductsArgs,
)


class CatalogTools:
    """Allow-listed catalog operations; raw LLM-generated SQL is never accepted."""

    def __init__(
        self,
        repository: ProductRepository,
        document_search: DocumentSearch | None = None,
        comparison_service: ComparisonService | None = None,
        sizing_service: SizingService | None = None,
        configuration_repository: ConfigurationRepository | None = None,
    ) -> None:
        self.repository = repository
        self.document_search = document_search
        self.comparison_service = comparison_service
        self.sizing_service = sizing_service
        self.configuration_repository = configuration_repository

    def search_products(
        self, filters: ProductFilter | dict | None = None,
        query: str | None = None, limit: int = 20,
    ) -> ToolResult[ProductSearchResult]:
        args = SearchProductsArgs(filters=filters if filters is not None else {},
                                  query=query, limit=limit)
        return ToolResult(
            ok=True,
            data=self.repository.search(ProductSearchRequest(**args.model_dump())),
        )

    def get_product(self, product_id: str) -> ToolResult[Product]:
        product_id = GetProductArgs(product_id=product_id).product_id
        product = self.repository.get(product_id)
        return ToolResult(
            ok=product is not None,
            data=product,
            error=None if product else "unknown_product",
        )

    def search_product_documents(
        self, query: str, product_id: str | None = None, top_k: int = 5
    ) -> ToolResult[DocumentSearchResult]:
        args = SearchProductDocumentsArgs(query=query, product_id=product_id, top_k=top_k)
        if self.document_search is None:
            return ToolResult(ok=False, error="document_search_not_configured")
        result = self.document_search.search(
            DocumentSearchRequest(**args.model_dump())
        )
        return ToolResult(ok=True, data=result)

    def compare_products(self, product_ids: list[str]) -> ToolResult[ComparisonResult]:
        product_ids = CompareProductsArgs(product_ids=product_ids).product_ids
        products = [
            product
            for product_id in product_ids
            if (product := self.repository.get(product_id))
        ]
        if len(products) != len(product_ids):
            return ToolResult(ok=False, error="unknown_product")
        return ToolResult(
            ok=True,
            data=ComparisonResult(
                product_ids=product_ids,
                dimensions=[
                    "product_type",
                    "max_ram_gb",
                    "max_gpu_slots",
                    "max_storage_gb",
                    "base_price_vnd",
                ],
                summary="So sánh thông tin nền tảng sản phẩm từ catalog.",
            ),
        )

    def compare_configurations(
        self, configuration_ids: list[str]
    ) -> ToolResult[ComparisonResult]:
        args = CompareConfigurationsArgs(configuration_ids=configuration_ids)
        if self.configuration_repository is None:
            return ToolResult(ok=False, error="configuration_repository_not_configured")
        resolved = [self.configuration_repository.get(cid) for cid in args.configuration_ids]
        if any(configuration is None for configuration in resolved):
            return ToolResult(ok=False, error="unknown_configuration")
        if self.comparison_service is None:
            return ToolResult(ok=False, error="comparison_not_configured")
        configurations = [configuration for configuration in resolved if configuration is not None]
        return ToolResult(
            ok=True,
            data=self.comparison_service.compare_configurations(configurations),
        )

    def estimate_ai_requirements(
        self, model_parameters_b: float, usage: UsageType,
        quantization: str | None = None, context_length: int | None = None,
        concurrent_users: int | None = None, training_method: str | None = None,
    ) -> ToolResult[SizingResult]:
        args = EstimateAIRequirementsArgs(
            model_parameters_b=model_parameters_b, usage=usage, quantization=quantization,
            context_length=context_length, concurrent_users=concurrent_users,
            training_method=training_method,
        )
        if self.sizing_service is None:
            return ToolResult(ok=False, error="sizing_not_configured")
        result = self.sizing_service.estimate(
            SizingRequest(**args.model_dump())
        )
        return ToolResult(ok=True, data=result)
