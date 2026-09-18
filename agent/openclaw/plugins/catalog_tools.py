from __future__ import annotations

from shared.contracts import (
    Product,
    ProductFilter,
    ProductSearchRequest,
    ProductSearchResult,
    ToolResult,
)
from shared.interfaces import ProductRepository


class CatalogTools:
    """Allow-listed catalog operations; raw LLM-generated SQL is never accepted."""

    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    def search_products(self, filters: ProductFilter | None = None) -> ToolResult[ProductSearchResult]:
        return ToolResult(
            ok=True,
            data=self.repository.search(ProductSearchRequest(filters=filters or ProductFilter())),
        )

    def get_product(self, product_id: str) -> ToolResult[Product]:
        product = self.repository.get(product_id)
        return ToolResult(ok=product is not None, data=product, error=None if product else "unknown_product")

    def search_product_documents(self, query: str) -> ToolResult[None]:
        return ToolResult(ok=False, error="document_search_not_configured_in_phase_1")

    def compare_products(self, product_ids: list[str]) -> ToolResult[list[Product]]:
        products = [product for product_id in product_ids if (product := self.repository.get(product_id))]
        return ToolResult(ok=len(products) == len(product_ids), data=products)
