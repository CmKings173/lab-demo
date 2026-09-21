from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from shared.contracts import DocumentHit, Product, ProductConfiguration, ResolvedProductFact


class DeterministicProductFactResolver:
    """Resolve only explicitly tagged and verified product facts."""

    _PRODUCT_FIELDS = {"max_ram_gb", "max_gpu_slots", "max_storage_gb"}

    def resolve(
        self,
        configuration: ProductConfiguration,
        unknown_fields: Sequence[str],
        hits: Sequence[DocumentHit],
    ) -> list[ResolvedProductFact]:
        candidates: dict[str, list[tuple[ResolvedProductFact, float | None]]] = {}
        wanted = set(unknown_fields)
        for hit in hits:
            chunk = hit.chunk
            metadata = chunk.metadata
            if not isinstance(metadata, dict):
                continue
            field_name = metadata.get("field_name")
            verified = metadata.get("verified")
            raw_value = metadata.get("value")
            if (
                chunk.product_id != configuration.product.id
                or field_name not in wanted
                or field_name not in self._PRODUCT_FIELDS
                or not isinstance(verified, str)
                or verified.casefold() != "true"
                or not chunk.source_url
                or not isinstance(raw_value, str)
            ):
                continue
            parsed_value = self._parse_value(raw_value)
            value = self._validated_value(configuration.product, field_name, parsed_value)
            if value is None:
                continue
            evidence_score = (
                hit.rerank_score
                if hit.rerank_score is not None
                else hit.retrieval_score
            )
            confidence = evidence_score if evidence_score is not None else 1.0
            fact = ResolvedProductFact(
                product_id=configuration.product.id,
                field_name=field_name,
                value=value,
                source_url=chunk.source_url,
                document_id=chunk.id,
                page=chunk.page,
                chunk_id=chunk.id,
                evidence_text=chunk.text,
                confidence=confidence,
                verified=True,
            )
            candidates.setdefault(field_name, []).append((fact, evidence_score))
        return [
            max(
                facts,
                key=lambda candidate: (
                    candidate[1] is not None,
                    candidate[1] if candidate[1] is not None else 0.0,
                ),
            )[0]
            for facts in candidates.values()
            if len({fact.value for fact, _ in facts}) == 1
        ]

    def apply(
        self,
        configuration: ProductConfiguration,
        facts: Sequence[ResolvedProductFact],
    ) -> ProductConfiguration:
        candidates: dict[str, set[int]] = {}
        for fact in facts:
            if (
                not fact.verified
                or fact.product_id != configuration.product.id
                or fact.field_name not in self._PRODUCT_FIELDS
            ):
                continue
            value = self._validated_value(configuration.product, fact.field_name, fact.value)
            if value is not None:
                candidates.setdefault(fact.field_name, set()).add(value)
        updates = {
            field_name: next(iter(values))
            for field_name, values in candidates.items()
            if len(values) == 1
        }
        if not updates:
            return configuration
        if not configuration.pricing_state_is_consistent():
            raise ValueError("Configuration pricing fields are inconsistent with price_breakdown")
        product_data = configuration.product.model_dump(mode="python")
        product_data.update(updates)
        validated_product = Product.model_validate(product_data)
        configuration_data = configuration.model_dump(mode="python")
        configuration_data["product"] = validated_product.model_dump(mode="python")
        return ProductConfiguration.model_validate(configuration_data)

    @staticmethod
    def _validated_value(product: Product, field_name: str, value: Any) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        product_data = product.model_dump(mode="python")
        product_data[field_name] = value
        try:
            validated_product = Product.model_validate(product_data)
        except ValidationError:
            return None
        return getattr(validated_product, field_name)

    @staticmethod
    def _parse_value(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
