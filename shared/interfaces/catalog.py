from typing import Protocol

from shared.contracts import Product, ProductSearchRequest, ProductSearchResult


class ProductRepository(Protocol):
    def search(self, request: ProductSearchRequest) -> ProductSearchResult: ...

    def get(self, product_id: str) -> Product | None: ...
