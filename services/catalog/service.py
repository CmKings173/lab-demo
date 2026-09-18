from shared.contracts import ProductFilter, ProductSearchRequest, ProductSearchResult, SizingResult
from shared.interfaces import ProductRepository


class CatalogService:
    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    def search_for_sizing(self, sizing: SizingResult, budget_vnd: int) -> ProductSearchResult:
        return self.repository.search(
            ProductSearchRequest(
                filters=ProductFilter(
                    min_ram_gb=sizing.recommended_ram_gb,
                    min_gpu_count=sizing.minimum_gpu_count,
                    max_price_vnd=budget_vnd,
                )
            )
        )
