"""Provider-neutral provenance boundary for document-backed product facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from shared.contracts import DocumentHit


@dataclass(frozen=True)
class EvidenceProvenance:
    """Provider-neutral canonical identity returned only after verification."""

    product_id: str
    document_id: str
    source_url: str


class EvidenceProvenanceVerifier(Protocol):
    """Verify that a hit has persisted authority for one expected product."""

    def verify(
        self, hit: DocumentHit, expected_product_id: str
    ) -> EvidenceProvenance | None: ...

    def verify_record(
        self, provenance: EvidenceProvenance, expected_product_id: str
    ) -> bool: ...
