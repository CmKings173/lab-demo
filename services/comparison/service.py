from collections.abc import Sequence

from shared.contracts import ComparisonResult, ProductConfiguration


class RuleBasedComparisonService:
    def compare(self, configurations: Sequence[ProductConfiguration]) -> ComparisonResult:
        return ComparisonResult(
            product_ids=[configuration.product.id for configuration in configurations],
            configuration_ids=[configuration.configuration_id for configuration in configurations],
            dimensions=[
                "product_type",
                "gpu_count",
                "total_vram_gb",
                "max_ram_gb",
                "configured_storage_gb",
                "estimated_price_vnd",
                "availability",
            ],
            summary="Compare exact catalog fields; document evidence is added by the RAG service.",
        )
