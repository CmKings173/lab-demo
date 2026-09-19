from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from shared.contracts import DocumentHit, ProductConfiguration, ResolvedProductFact


class DeterministicProductFactResolver:
    """Resolve only explicitly tagged and verified product facts."""

    _PRODUCT_FIELDS = {"max_ram_gb", "max_gpu_slots", "max_storage_gb", "base_price_vnd"}

    def resolve(
        self,
        configuration: ProductConfiguration,
        unknown_fields: Sequence[str],
        hits: Sequence[DocumentHit],
    ) -> list[ResolvedProductFact]:
        facts: list[ResolvedProductFact] = []
        wanted = set(unknown_fields)
        for hit in hits:
            chunk = hit.chunk
            field_name = chunk.metadata.get("field_name")
            if (
                chunk.product_id != configuration.product.id
                or field_name not in wanted
                or field_name not in self._PRODUCT_FIELDS
                or chunk.metadata.get("verified", "").casefold() != "true"
                or not chunk.source_url
                or "value" not in chunk.metadata
            ):
                continue
            facts.append(
                ResolvedProductFact(
                    product_id=configuration.product.id,
                    field_name=field_name,
                    value=self._parse_value(chunk.metadata["value"]),
                    source_url=chunk.source_url,
                    document_id=chunk.id,
                    page=chunk.page,
                    chunk_id=chunk.id,
                    evidence_text=chunk.text,
                    confidence=hit.rerank_score or hit.retrieval_score or 1.0,
                    verified=True,
                )
            )
        return facts

    def apply(
        self,
        configuration: ProductConfiguration,
        facts: Sequence[ResolvedProductFact],
    ) -> ProductConfiguration:
        updates: dict[str, Any] = {
            fact.field_name: fact.value
            for fact in facts
            if fact.verified and fact.product_id == configuration.product.id
        }
        if not updates:
            return configuration
        return configuration.model_copy(
            update={"product": configuration.product.model_copy(update=updates)}
        )

    @staticmethod
    def _parse_value(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
