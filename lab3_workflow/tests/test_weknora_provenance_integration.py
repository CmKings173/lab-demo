"""Opt-in isolated PostgreSQL coverage for verified WeKnora provenance."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from adapters.real.weknora_provenance import WeKnoraEvidenceProvenanceVerifier
from lab2_rag_agent.catalog.document_repository import PostgresProductDocumentRepository
from lab2_rag_agent.catalog.documents import ProductDocumentUpsert
from shared.contracts import DocumentChunk, DocumentHit


def test_real_postgres_mapping_is_required_for_weknora_fact_provenance(monkeypatch):
    dsn = os.environ.get("LAB2_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set LAB2_TEST_POSTGRES_DSN for isolated real PostgreSQL integration")
    psycopg = pytest.importorskip(
        "psycopg",
        reason="Install the optional postgres extra to run real PostgreSQL integration",
    )
    from psycopg import sql
    from psycopg.rows import dict_row

    schema = "lab3_provenance_test_" + uuid4().hex
    migration_dir = Path(__file__).resolve().parents[2] / "infra/postgres/migrations"
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            def connect(_dsn):
                connection = psycopg.connect(_dsn, row_factory=dict_row)
                connection.execute(
                    sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
                )
                return connection

            with connect(dsn) as connection:
                for migration in sorted(migration_dir.glob("*.sql")):
                    connection.execute(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO products (id, name, product_type, source_url) "
                    "VALUES (%s, %s, %s, %s)",
                    (
                        "lab3-provenance-product",
                        "Provenance integration product",
                        "ai_server",
                        "https://example.test/product",
                    ),
                )

            monkeypatch.setattr(
                PostgresProductDocumentRepository,
                "_connect",
                staticmethod(connect),
            )
            repository = PostgresProductDocumentRepository(dsn)
            repository.upsert(
                ProductDocumentUpsert(
                    product_id="lab3-provenance-product",
                    knowledge_base_id="lab3-test-kb",
                    knowledge_id="lab3-test-knowledge",
                    filename="datasheet.pdf",
                    source_url="https://example.test/datasheet.pdf",
                    provider_parse_status="completed",
                )
            )
            verifier = WeKnoraEvidenceProvenanceVerifier(
                repository,
                knowledge_base_id="lab3-test-kb",
            )
            hit = DocumentHit(
                chunk=DocumentChunk(
                    id="chunk-1",
                    text="Maximum RAM: 512 GB",
                    product_id="lab3-provenance-product",
                    source_url="https://example.test/datasheet.pdf",
                    metadata={
                        "provider": "weknora",
                        "knowledge_id": "lab3-test-knowledge",
                    },
                ),
                rank=1,
                retrieval_method="weknora",
            )

            assert verifier.verify(hit, "lab3-provenance-product") is not None
            assert repository.update_parse_status(
                "lab3-test-kb", "lab3-test-knowledge", "processing"
            ) is not None
            assert verifier.verify(hit, "lab3-provenance-product") is None
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
