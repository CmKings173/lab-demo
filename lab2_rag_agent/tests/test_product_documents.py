from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from lab2_rag_agent.catalog.document_repository import PostgresProductDocumentRepository
from lab2_rag_agent.catalog.documents import ProductDocumentMapping, ProductDocumentUpsert


def _mapping_row(**updates):
    return {
        "id": 7,
        "product_id": "product-1",
        "knowledge_base_id": "kb-demo",
        "knowledge_id": "knowledge-1",
        "filename": "datasheet.pdf",
        "source_url": "https://example.test/datasheet.pdf",
        "content_sha256": "a" * 64,
        "provider_parse_status": "completed",
        "created_at": datetime(2026, 9, 27, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 27, tzinfo=UTC),
        **updates,
    }


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
        self.statement = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, params):
        self.statement = (statement, params)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor


def _repository(monkeypatch, cursor):
    monkeypatch.setattr(
        PostgresProductDocumentRepository,
        "_connect",
        staticmethod(lambda _dsn: FakeConnection(cursor)),
    )
    return PostgresProductDocumentRepository("unused")


def test_mapping_contract_keeps_provider_identity_and_optional_provenance() -> None:
    row = _mapping_row(source_url=None, content_sha256=None)
    mapping = ProductDocumentMapping.model_validate(row)
    assert (mapping.knowledge_base_id, mapping.knowledge_id) == ("kb-demo", "knowledge-1")
    assert mapping.source_url is None
    assert mapping.content_sha256 is None


@pytest.mark.parametrize(
    "updates",
    [
        {"filename": " "},
        {"knowledge_id": " "},
        {"content_sha256": "not-a-sha256"},
        {"source_url": "not-a-url"},
        {"source_url": "https://example.test/has space"},
        {"provider_parse_status": " "},
    ],
)
def test_mapping_contract_rejects_invalid_identity_or_provenance(updates) -> None:
    with pytest.raises(ValueError):
        ProductDocumentUpsert.model_validate({
            key: value for key, value in _mapping_row(**updates).items()
            if key not in {"id", "created_at", "updated_at"}
        })


def test_list_by_product_uses_parameter_and_stable_order(monkeypatch) -> None:
    cursor = FakeCursor(rows=[_mapping_row()])
    repository = _repository(monkeypatch, cursor)

    result = repository.list_by_product_id("product'; DROP TABLE products; --")

    assert [row.knowledge_id for row in result] == ["knowledge-1"]
    statement, params = cursor.statement
    assert "WHERE product_id = %s ORDER BY id ASC" in statement
    assert "DROP TABLE" not in statement
    assert params == ("product'; DROP TABLE products; --",)


def test_get_by_knowledge_id_uses_complete_provider_identity(monkeypatch) -> None:
    cursor = FakeCursor(row=_mapping_row())
    repository = _repository(monkeypatch, cursor)

    result = repository.get_by_knowledge_id("kb-demo", "knowledge-1")

    assert result is not None and result.id == 7
    statement, params = cursor.statement
    assert "knowledge_base_id = %s AND knowledge_id = %s" in statement
    assert params == ("kb-demo", "knowledge-1")


def test_content_hash_lookup_is_scoped_and_parameterized(monkeypatch) -> None:
    cursor = FakeCursor(row=_mapping_row())
    repository = _repository(monkeypatch, cursor)

    result = repository.find_by_content_sha256(
        "product-1", "kb-demo", "a" * 64
    )

    assert result is not None and result.knowledge_id == "knowledge-1"
    statement, params = cursor.statement
    assert "product_id = %s AND knowledge_base_id = %s" in statement
    assert "content_sha256 = %s" in statement
    assert params == ("product-1", "kb-demo", "a" * 64)


def test_upsert_uses_parameterized_provider_identity_and_returns_mapping(monkeypatch) -> None:
    cursor = FakeCursor(row=_mapping_row())
    repository = _repository(monkeypatch, cursor)
    request = ProductDocumentUpsert(
        product_id="product-1",
        knowledge_base_id="kb-demo",
        knowledge_id="id'); SELECT pg_sleep(10); --",
        filename="datasheet.pdf",
        provider_parse_status="processing",
    )

    result = repository.upsert(request)

    assert result.id == 7
    statement, params = cursor.statement
    normalized_statement = " ".join(statement.split())
    assert "ON CONFLICT (knowledge_base_id, knowledge_id)" in normalized_statement
    assert "source_url = COALESCE(EXCLUDED.source_url, product_documents.source_url)" \
        in normalized_statement
    assert "content_sha256 = COALESCE(" in normalized_statement
    assert "EXCLUDED.content_sha256, product_documents.content_sha256" \
        in normalized_statement
    assert "DROP" not in normalized_statement and "pg_sleep" not in normalized_statement
    assert "id'); SELECT pg_sleep(10); --" in params


def test_parse_status_update_uses_parameters(monkeypatch) -> None:
    cursor = FakeCursor(row=_mapping_row())
    repository = _repository(monkeypatch, cursor)
    status = "provider-error'; UPDATE products SET name = 'changed"

    result = repository.update_parse_status("kb-demo", "knowledge-1", status)

    assert result is not None
    statement, params = cursor.statement
    assert "UPDATE product_documents SET provider_parse_status = %s" in statement
    assert status not in statement
    assert params == (status, "kb-demo", "knowledge-1")


def test_migration_defines_mapping_without_document_chunks() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "infra/postgres/migrations/003_create_product_documents.sql"
    ).read_text(encoding="utf-8")

    for column in (
        "id BIGINT GENERATED BY DEFAULT AS IDENTITY",
        "product_id VARCHAR(64) NOT NULL",
        "knowledge_base_id TEXT NOT NULL",
        "knowledge_id TEXT NOT NULL",
        "filename TEXT NOT NULL",
        "source_url TEXT",
        "content_sha256 TEXT",
        "provider_parse_status VARCHAR(64)",
        "created_at TIMESTAMPTZ",
        "updated_at TIMESTAMPTZ",
    ):
        assert column in migration
    assert "FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT" in migration
    assert "UNIQUE (knowledge_base_id, knowledge_id)" in migration
    assert "content_sha256" in migration
    assert "CREATE INDEX" in migration
    assert "chunk_content" not in migration
    assert "embedding" not in migration
