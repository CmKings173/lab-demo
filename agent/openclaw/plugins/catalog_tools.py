from __future__ import annotations

from shared.contracts import (
    ComparisonResult,
    DocumentSearchRequest,
    DocumentSearchResult,
    Product,
    ProductConfiguration,
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


class CatalogTools:
    """Allow-listed catalog operations; raw LLM-generated SQL is never accepted."""

    def __init__(
        self,
        repository: ProductRepository,
        document_search: DocumentSearch | None = None,
        comparison_service: ComparisonService | None = None,
        sizing_service: SizingService | None = None,
    ) -> None:
        self.repository = repository
        self.document_search = document_search
        self.comparison_service = comparison_service
        self.sizing_service = sizing_service

    def search_products(
        self, filters: ProductFilter | None = None
    ) -> ToolResult[ProductSearchResult]:
        return ToolResult(
            ok=True,
            data=self.repository.search(ProductSearchRequest(filters=filters or ProductFilter())),
        )

    def get_product(self, product_id: str) -> ToolResult[Product]:
        product = self.repository.get(product_id)
        return ToolResult(
            ok=product is not None,
            data=product,
            error=None if product else "unknown_product",
        )

    def search_product_documents(
        self, query: str, product_id: str | None = None
    ) -> ToolResult[DocumentSearchResult]:
        if self.document_search is None:
            return ToolResult(ok=False, error="document_search_not_configured")
        result = self.document_search.search(
            DocumentSearchRequest(query=query, product_id=product_id)
        )
        return ToolResult(ok=True, data=result)

    def compare_products(self, product_ids: list[str]) -> ToolResult[ComparisonResult]:
        products = [
            product
            for product_id in product_ids
            if (product := self.repository.get(product_id))
        ]
        if len(products) != len(product_ids):
            return ToolResult(ok=False, error="unknown_product")
        if self.comparison_service is None:
            return ToolResult(ok=False, error="comparison_not_configured")
        configurations = [
            ProductConfiguration(configuration_id=f"{product.id}:unspecified", product=product)
            for product in products
        ]
        return ToolResult(ok=True, data=self.comparison_service.compare(configurations))

    def estimate_ai_requirements(
        self, model_parameters_b: float, usage: UsageType
    ) -> ToolResult[SizingResult]:
        if self.sizing_service is None:
            return ToolResult(ok=False, error="sizing_not_configured")
        result = self.sizing_service.estimate(
            SizingRequest(model_parameters_b=model_parameters_b, usage=usage)
        )
        return ToolResult(ok=True, data=result)
