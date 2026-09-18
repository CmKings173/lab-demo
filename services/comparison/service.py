from collections.abc import Sequence

from shared.contracts import ComparisonResult, ProductCandidate


class RuleBasedComparisonService:
    def compare(self, candidates: Sequence[ProductCandidate]) -> ComparisonResult:
        return ComparisonResult(
            product_ids=[candidate.product.id for candidate in candidates],
            dimensions=[
                "product_type",
                "max_gpu_count",
                "vram_gb",
                "max_ram_gb",
                "storage_gb",
                "price_vnd",
                "availability",
            ],
            summary="Compare exact catalog fields; document evidence is added by the RAG service.",
        )
