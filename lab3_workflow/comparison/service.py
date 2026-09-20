from collections.abc import Sequence

from shared.contracts import ComparisonResult, ConfigurationComparison, ProductConfiguration


class RuleBasedComparisonService:
    def compare_configurations(
        self, configurations: Sequence[ProductConfiguration]
    ) -> ComparisonResult:
        return ComparisonResult(
            product_ids=[configuration.product.id for configuration in configurations],
            configuration_ids=[configuration.configuration_id for configuration in configurations],
            configurations=[
                ConfigurationComparison(
                    configuration_id=configuration.configuration_id,
                    product_id=configuration.product.id,
                    gpu_model=(
                        configuration.selected_gpu.name
                        if configuration.selected_gpu is not None
                        else None
                    ),
                    gpu_count=configuration.gpu_count,
                    total_vram_gb=configuration.total_vram_gb,
                    configured_ram_gb=configuration.configured_ram_gb,
                    configured_storage_gb=configuration.configured_storage_gb,
                    price_status=configuration.price_status,
                    estimated_price_vnd=configuration.estimated_price_vnd,
                    unknown_facts=self._unknown_facts(configuration),
                )
                for configuration in configurations
            ],
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

    @staticmethod
    def _unknown_facts(configuration: ProductConfiguration) -> list[str]:
        return [
            field
            for field in (
                "selected_gpu",
                "gpu_count",
                "configured_ram_gb",
                "configured_storage_gb",
                "estimated_price_vnd",
            )
            if getattr(configuration, field) is None
        ]
