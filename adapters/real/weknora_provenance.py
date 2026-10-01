"""WeKnora hit provenance verification against the catalog-owned mapping."""

from __future__ import annotations

from lab2_rag_agent.catalog.documents import (
    ProductDocumentMapping,
    ProductDocumentRepository,
)
from lab3_workflow.evidence.provenance import EvidenceProvenance
from shared.contracts import DocumentHit


class WeKnoraEvidenceProvenanceVerifier:
    """Fail closed unless the hit exactly matches a completed persisted mapping."""

    def __init__(
        self,
        product_document_repository: ProductDocumentRepository,
        *,
        knowledge_base_id: str,
    ) -> None:
        if not isinstance(knowledge_base_id, str) or not knowledge_base_id.strip():
            raise ValueError("knowledge_base_id must be a non-empty string")
        self._documents = product_document_repository
        self._knowledge_base_id = knowledge_base_id

    def verify(
        self, hit: DocumentHit, expected_product_id: str
    ) -> EvidenceProvenance | None:
        metadata = hit.chunk.metadata
        if (
            not isinstance(metadata, dict)
            or metadata.get("provider") != "weknora"
            or not isinstance(metadata.get("knowledge_id"), str)
            or not metadata["knowledge_id"].strip()
            or not isinstance(expected_product_id, str)
            or not expected_product_id.strip()
            or hit.chunk.product_id != expected_product_id
        ):
            return None

        mapping = self._documents.get_by_knowledge_id(
            self._knowledge_base_id,
            metadata["knowledge_id"],
        )
        if not self._mapping_matches(mapping, expected_product_id):
            return None
        if hit.chunk.source_url != mapping.source_url:
            return None
        return EvidenceProvenance(
            product_id=mapping.product_id,
            document_id=mapping.knowledge_id,
            source_url=mapping.source_url,
        )

    def verify_record(
        self, provenance: EvidenceProvenance, expected_product_id: str
    ) -> bool:
        if (
            provenance.product_id != expected_product_id
            or not provenance.document_id.strip()
            or not provenance.source_url.strip()
        ):
            return False
        mapping = self._documents.get_by_knowledge_id(
            self._knowledge_base_id,
            provenance.document_id,
        )
        return bool(
            self._mapping_matches(mapping, expected_product_id)
            and mapping.knowledge_id == provenance.document_id
            and mapping.source_url == provenance.source_url
        )

    def _mapping_matches(
        self,
        mapping: ProductDocumentMapping | None,
        expected_product_id: str,
    ) -> bool:
        return bool(
            mapping is not None
            and mapping.knowledge_base_id == self._knowledge_base_id
            and mapping.provider_parse_status == "completed"
            and mapping.product_id == expected_product_id
            and isinstance(mapping.source_url, str)
            and mapping.source_url.strip()
            and mapping.knowledge_id.strip()
        )
