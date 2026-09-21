from collections.abc import Sequence

from shared.contracts import (
    ComparisonResult,
    ConfigurationComparison,
    ProductConfiguration,
    SizingRequest,
    SizingResult,
)


class FakeComparisonService:
    def compare_configurations(
        self, configurations: Sequence[ProductConfiguration]
    ) -> ComparisonResult:
        return ComparisonResult(
            product_ids=[item.product.id for item in configurations],
            configuration_ids=[item.configuration_id for item in configurations],
            configurations=[
                ConfigurationComparison(
                    configuration_id=item.configuration_id,
                    product_id=item.product.id,
                    gpu_model=item.selected_gpu.name if item.selected_gpu else None,
                    gpu_count=item.gpu_count,
                    total_vram_gb=item.total_vram_gb,
                    configured_ram_gb=item.configured_ram_gb,
                    configured_storage_gb=item.configured_storage_gb,
                    price_status=item.price_status,
                    estimated_price_vnd=item.estimated_price_vnd,
                )
                for item in configurations
            ],
            dimensions=["gpu_count", "total_vram_gb", "configured_ram_gb"],
            summary="So sánh cấu hình giả lập dùng cho unit test.",
        )


class FakeSizingService:
    def estimate(self, request: SizingRequest) -> SizingResult:
        return SizingResult(
            estimated_model_memory_gb=request.model_parameters_b * 2,
            recommended_total_vram_gb=request.model_parameters_b * 3,
            recommended_system_ram_gb=128,
            assumptions=[],
            warnings=[],
            confidence=0.5,
        )
