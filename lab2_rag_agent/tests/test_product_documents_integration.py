"""Isolated real PostgreSQL tests for the product-document mapping migration."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from lab2_rag_agent.catalog.document_repository import PostgresProductDocumentRepository
from lab2_rag_agent.catalog.documents import (
    ProductDocumentIdentityConflict,
    ProductDocumentUpsert,
)


def test_real_postgres_product_document_mapping(monkeypatch) -> None:
    dsn = os.environ.get("LAB2_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set LAB2_TEST_POSTGRES_DSN for isolated real PostgreSQL integration")
    psycopg = pytest.importorskip(
        "psycopg",
        reason="Install the optional postgres extra to run real PostgreSQL integration",
    )
    from psycopg import sql
    from psycopg.rows import dict_row

    schema = "lab2_documents_test_" + uuid4().hex
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
                migrations = sorted(migration_dir.glob("*.sql"))
                for _ in range(2):
                    for migration in migrations:
                        connection.execute(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO products (id, name, product_type, source_url) "
                    "VALUES (%s, %s, %s, %s)",
                    ("doc-product-a", "Document Test A", "ai_workstation", "https://example.test/a"),
                )
                connection.execute(
                    "INSERT INTO products (id, name, product_type, source_url) "
                    "VALUES (%s, %s, %s, %s)",
                    ("doc-product-b", "Document Test B", "ai_server", "https://example.test/b"),
                )
                fk = connection.execute(
                    "SELECT pg_get_constraintdef(oid) AS definition "
                    "FROM pg_constraint WHERE conrelid = 'product_documents'::regclass "
                    "AND contype = 'f'"
                ).fetchone()["definition"]
                indexes = connection.execute(
                    "SELECT indexdef FROM pg_indexes WHERE schemaname = %s "
                    "AND tablename = 'product_documents'",
                    (schema,),
                ).fetchall()
                assert "ON DELETE RESTRICT" in fk
                assert any("idx_product_documents_product_id" in row["indexdef"] for row in indexes)

            monkeypatch.setattr(
                PostgresProductDocumentRepository, "_connect", staticmethod(connect)
            )
            repository = PostgresProductDocumentRepository(dsn)
            first_input = ProductDocumentUpsert(
                product_id="doc-product-a",
                knowledge_base_id="kb-one",
                knowledge_id="provider-doc-1",
                filename="datasheet-a.pdf",
                source_url="https://example.test/a/datasheet.pdf",
                content_sha256="a" * 64,
                provider_parse_status="processing",
            )
            first = repository.upsert(first_input)
            reconciled = repository.upsert(
                first_input.model_copy(update={
                    "filename": "datasheet-a-reconciled.pdf",
                    "source_url": None,
                    "content_sha256": None,
                    "provider_parse_status": "completed",
                })
            )
            assert reconciled.id == first.id
            assert reconciled.filename == "datasheet-a-reconciled.pdf"
            assert reconciled.source_url == first_input.source_url
            assert reconciled.content_sha256 == first_input.content_sha256
            assert reconciled.provider_parse_status == "completed"

            second = repository.upsert(ProductDocumentUpsert(
                product_id="doc-product-a",
                knowledge_base_id="kb-one",
                knowledge_id="provider-doc-2",
                filename="manual-a.pdf",
                content_sha256="b" * 64,
            ))
            assert second.id != first.id
            assert [item.id for item in repository.list_by_product_id("doc-product-a")] == [
                first.id, second.id,
            ]
            assert [item.id for item in repository.list_by_knowledge_base_id("kb-one")] == [
                first.id, second.id,
            ]
            assert repository.get_by_knowledge_id("kb-one", "provider-doc-1").id == first.id
            assert repository.find_by_content_sha256(
                "doc-product-a", "kb-one", "b" * 64
            ).id == second.id
            assert repository.update_parse_status(
                "kb-one", "provider-doc-1", "parsed_with_warnings"
            ).provider_parse_status == "parsed_with_warnings"
            assert repository.update_parse_status(
                "kb-one", "missing", "completed"
            ) is None

            with pytest.raises(psycopg.errors.UniqueViolation):
                repository.upsert(ProductDocumentUpsert(
                    product_id="doc-product-a",
                    knowledge_base_id="kb-one",
                    knowledge_id="provider-doc-duplicate-content",
                    filename="duplicate.pdf",
                    content_sha256="a" * 64,
                ))
            with pytest.raises(ProductDocumentIdentityConflict):
                repository.upsert(first_input.model_copy(update={"product_id": "doc-product-b"}))
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                repository.upsert(first_input.model_copy(update={
                    "product_id": "missing-product",
                    "knowledge_id": "provider-doc-orphan",
                }))
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                with connect(dsn) as connection:
                    connection.execute(
                        "DELETE FROM products WHERE id = %s", ("doc-product-a",)
                    )
            assert len(repository.list_by_product_id("doc-product-a")) == 2
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
