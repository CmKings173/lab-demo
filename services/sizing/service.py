from __future__ import annotations

import math

from shared.contracts import SizingRequest, SizingResult, UsageType


class DeterministicSizingService:
    """Transparent placeholder rules, intentionally not a production estimator."""

    def estimate(self, request: SizingRequest) -> SizingResult:
        memory_bytes_per_parameter = 2.0
        if request.quantization in {"int8", "8bit"}:
            memory_bytes_per_parameter = 1.0
        elif request.quantization in {"int4", "4bit", "q4"}:
            memory_bytes_per_parameter = 0.5
        if request.usage == UsageType.FINE_TUNE:
            memory_bytes_per_parameter *= 1.5

        context_factor = min((request.context_length or 4096) / 4096 * 0.10, 0.50)
        concurrency_factor = min((request.concurrent_users or 1) * 0.03, 0.30)
        estimated = (
            request.model_parameters_b
            * memory_bytes_per_parameter
            * (1 + context_factor + concurrency_factor)
            * request.additional_overhead
        )
        recommended = math.ceil(estimated * 1.25)
        recommended_ram = math.ceil(
            max(64.0, request.model_parameters_b * 8 + (request.concurrent_users or 1) * 16)
        )
        assumptions = [
            "The result is a deterministic Phase 1 rule, not a benchmark-backed sizing promise.",
            (
                f"Model memory uses {memory_bytes_per_parameter:g} bytes per parameter "
                "before overhead."
            ),
            "GPU count is selected later from the memory capacity of an actual GPU option.",
        ]
        warnings = [
            (
                "Validate with an actual model, context, batch and concurrency benchmark "
                "before purchase."
            ),
        ]
        if request.usage == UsageType.FINE_TUNE:
            warnings.append(
                "Fine-tuning memory depends strongly on batch size, optimizer and sequence length."
            )

        return SizingResult(
            estimated_model_memory_gb=round(estimated, 2),
            recommended_total_vram_gb=float(recommended),
            recommended_system_ram_gb=recommended_ram,
            recommended_storage_gb=None,
            assumptions=assumptions,
            warnings=warnings,
            confidence=0.40,
        )


def estimate_ai_requirements(request: SizingRequest) -> SizingResult:
    return DeterministicSizingService().estimate(request)
