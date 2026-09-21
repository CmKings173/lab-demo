from shared.contracts import ProductFilter, ProductSearchRequest, ProductSearchResult, SizingResult
from shared.interfaces import ProductRepository


class CatalogService:
    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    def search_for_sizing(self, sizing: SizingResult, budget_vnd: int) -> ProductSearchResult:
        return self.repository.search(
            ProductSearchRequest(
                filters=ProductFilter(
                    min_ram_gb=sizing.recommended_system_ram_gb,
                    max_base_price_vnd=budget_vnd,
                )
            )
        )
