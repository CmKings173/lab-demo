"""Verified deterministic resolution for real, mapped document evidence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import ValidationError

from lab3_workflow.evidence.capacity_extractor import extract_capacity_value
from lab3_workflow.evidence.provenance import (
    EvidenceProvenance,
    EvidenceProvenanceVerifier,
)
from shared.contracts import (
    DocumentHit,
    Product,
    ProductConfiguration,
    ResolvedProductFact,
)

_PRODUCT_FIELDS = {"max_ram_gb", "max_gpu_slots", "max_storage_gb"}


class VerifiedDocumentProductFactResolver:
    """Resolve only facts with mapped WeKnora provenance and explicit rules.

    Confidence remains the contract's neutral default (1.0); it is not a
    calibrated probability and is not used to decide whether a fact is valid.
    """

    document_search_terms: ClassVar[dict[str, str]] = {
        "max_ram_gb": "maximum RAM memory capacity",
        "max_gpu_slots": "maximum GPU slots supported GPUs",
        "max_storage_gb": "maximum storage capacity",
    }

    def __init__(self, provenance_verifier: EvidenceProvenanceVerifier) -> None:
        self._provenance_verifier = provenance_verifier

    def resolve(
        self,
        configuration: ProductConfiguration,
        unknown_fields: Sequence[str],
        hits: Sequence[DocumentHit],
    ) -> list[ResolvedProductFact]:
        product = configuration.product
        wanted = {
            field
            for field in unknown_fields
            if field in _PRODUCT_FIELDS and getattr(product, field) is None
        }
        candidates: dict[str, list[tuple[tuple[int, str, str], ResolvedProductFact]]] = {}
        for hit in hits:
            provenance = self._provenance_verifier.verify(hit, product.id)
            if provenance is None:
                continue
            for field_name in wanted:
                extracted = extract_capacity_value(hit.chunk.text, field_name)
                value = self._validated_value(product, field_name, extracted)
                if value is None:
                    continue
                fact = ResolvedProductFact(
                    product_id=product.id,
                    field_name=field_name,
                    value=value,
                    source_url=provenance.source_url,
                    document_id=provenance.document_id,
                    page=hit.chunk.page,
                    chunk_id=hit.chunk.id,
                    evidence_text=hit.chunk.text,
                    verified=True,
                )
                ordering = (hit.rank, provenance.document_id, hit.chunk.id)
                candidates.setdefault(field_name, []).append((ordering, fact))

        resolved: list[ResolvedProductFact] = []
        for field_name in sorted(candidates):
            values = {fact.value for _, fact in candidates[field_name]}
            if len(values) == 1:
                resolved.append(
                    min(candidates[field_name], key=lambda candidate: candidate[0])[1]
                )
        return resolved

    def apply(
        self,
        configuration: ProductConfiguration,
        facts: Sequence[ResolvedProductFact],
    ) -> ProductConfiguration:
        product = configuration.product
        candidates: dict[str, set[int]] = {}
        for fact in facts:
            if (
                not fact.verified
                or fact.product_id != product.id
                or fact.field_name not in _PRODUCT_FIELDS
                or getattr(product, fact.field_name) is not None
                or not fact.source_url
                or not fact.document_id
                or not fact.chunk_id
                or not fact.evidence_text
            ):
                continue
            provenance = EvidenceProvenance(
                product_id=fact.product_id,
                document_id=fact.document_id,
                source_url=fact.source_url,
            )
            if not self._provenance_verifier.verify_record(provenance, product.id):
                continue
            extracted = extract_capacity_value(fact.evidence_text, fact.field_name)
            if type(fact.value) is not int or extracted != fact.value:
                continue
            validated = self._validated_value(product, fact.field_name, fact.value)
            if validated is not None:
                candidates.setdefault(fact.field_name, set()).add(validated)

        updates = {
            field_name: next(iter(values))
            for field_name, values in candidates.items()
            if len(values) == 1
        }
        if not updates:
            return configuration
        if not configuration.pricing_state_is_consistent():
            raise ValueError("Configuration pricing fields are inconsistent with price_breakdown")
        product_data = product.model_dump(mode="python")
        product_data.update(updates)
        updated_product = Product.model_validate(product_data)
        configuration_data = configuration.model_dump(mode="python")
        configuration_data["product"] = updated_product.model_dump(mode="python")
        return ProductConfiguration.model_validate(configuration_data)

    @staticmethod
    def _validated_value(product: Product, field_name: str, value: int | None) -> int | None:
        if field_name not in _PRODUCT_FIELDS or type(value) is not int:
            return None
        data = product.model_dump(mode="python")
        data[field_name] = value
        try:
            validated = Product.model_validate(data)
        except ValidationError:
            return None
        result = getattr(validated, field_name)
        return result if type(result) is int else None
