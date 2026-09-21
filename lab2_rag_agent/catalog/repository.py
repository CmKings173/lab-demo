from __future__ import annotations

from collections.abc import Iterable

from shared.contracts import Product, ProductSearchRequest, ProductSearchResult


class InMemoryProductRepository:
    def __init__(self, products: Iterable[Product] = ()) -> None:
        self._products = {product.id: product for product in products}

    def search(self, request: ProductSearchRequest) -> ProductSearchResult:
        filters = request.filters
        products = list(self._products.values())
        if request.query:
            query = request.query.casefold()
            products = [
                product
                for product in products
                if query in product.name.casefold()
                or query in product.sku.casefold()
                or query in product.manufacturer.casefold()
            ]
        if filters.product_type:
            products = [p for p in products if p.product_type == filters.product_type]
        if filters.min_ram_gb is not None:
            products = [
                p for p in products if p.max_ram_gb is None or p.max_ram_gb >= filters.min_ram_gb
            ]
        if filters.min_gpu_count is not None:
            products = [
                p
                for p in products
                if p.max_gpu_slots is None or p.max_gpu_slots >= filters.min_gpu_count
            ]
        if filters.max_base_price_vnd is not None:
            products = [
                p
                for p in products
                if p.base_price_vnd is None or p.base_price_vnd <= filters.max_base_price_vnd
            ]
        return ProductSearchResult(products=products[: request.limit], total=len(products))

    def get(self, product_id: str) -> Product | None:
        return self._products.get(product_id)


class PostgresProductRepository:
    """Reserved for the catalog database; no database dependency in Phase 1."""

    def search(self, request: ProductSearchRequest) -> ProductSearchResult:
        raise NotImplementedError("PostgreSQL catalog adapter is planned for a later phase")

    def get(self, product_id: str) -> Product | None:
        raise NotImplementedError("PostgreSQL catalog adapter is planned for a later phase")
