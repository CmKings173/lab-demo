"""PostgreSQL implementation for Lab 2 product-document mappings."""

from __future__ import annotations

from pydantic import TypeAdapter

from lab2_rag_agent.catalog.documents import (
    ProductDocumentIdentityConflict,
    ProductDocumentMapping,
    ProductDocumentUpsert,
    ProviderParseStatus,
)

_PARSE_STATUS = TypeAdapter(ProviderParseStatus)


class PostgresProductDocumentRepository:
    """Persist provider IDs and catalog provenance, not chunks or embeddings."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @staticmethod
    def _connect(dsn: str):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(dsn, row_factory=dict_row)

    @staticmethod
    def _mapping(row: dict) -> ProductDocumentMapping:
        return ProductDocumentMapping.model_validate(row)

    def list_by_product_id(self, product_id: str) -> list[ProductDocumentMapping]:
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM product_documents WHERE product_id = %s ORDER BY id ASC",
                (product_id,),
            )
            rows = cursor.fetchall()
        return [self._mapping(row) for row in rows]

    def list_by_knowledge_base_id(self, knowledge_base_id: str) -> list[ProductDocumentMapping]:
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM product_documents "
                "WHERE knowledge_base_id = %s ORDER BY id ASC",
                (knowledge_base_id,),
            )
            rows = cursor.fetchall()
        return [self._mapping(row) for row in rows]

    def get_by_knowledge_id(
        self, knowledge_base_id: str, knowledge_id: str
    ) -> ProductDocumentMapping | None:
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM product_documents "
                "WHERE knowledge_base_id = %s AND knowledge_id = %s",
                (knowledge_base_id, knowledge_id),
            )
            row = cursor.fetchone()
        return self._mapping(row) if row is not None else None

    def find_by_content_sha256(
        self, product_id: str, knowledge_base_id: str, content_sha256: str
    ) -> ProductDocumentMapping | None:
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM product_documents "
                "WHERE product_id = %s AND knowledge_base_id = %s "
                "AND content_sha256 = %s",
                (product_id, knowledge_base_id, content_sha256),
            )
            row = cursor.fetchone()
        return self._mapping(row) if row is not None else None

    def upsert(self, mapping: ProductDocumentUpsert) -> ProductDocumentMapping:
        statement = """\
            INSERT INTO product_documents (
                product_id, knowledge_base_id, knowledge_id, filename, source_url,
                content_sha256, provider_parse_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (knowledge_base_id, knowledge_id) DO UPDATE SET
                filename = EXCLUDED.filename,
                source_url = COALESCE(EXCLUDED.source_url, product_documents.source_url),
                content_sha256 = COALESCE(
                    EXCLUDED.content_sha256, product_documents.content_sha256
                ),
                provider_parse_status = EXCLUDED.provider_parse_status,
                updated_at = NOW()
            WHERE product_documents.product_id = EXCLUDED.product_id
            RETURNING *
        """
        values = (
            mapping.product_id,
            mapping.knowledge_base_id,
            mapping.knowledge_id,
            mapping.filename,
            mapping.source_url,
            mapping.content_sha256,
            mapping.provider_parse_status,
        )
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(statement, values)
            row = cursor.fetchone()
        if row is None:
            raise ProductDocumentIdentityConflict(
                "provider document identity is already mapped to a different product"
            )
        return self._mapping(row)

    def update_parse_status(
        self,
        knowledge_base_id: str,
        knowledge_id: str,
        provider_parse_status: ProviderParseStatus,
    ) -> ProductDocumentMapping | None:
        status = _PARSE_STATUS.validate_python(provider_parse_status)
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE product_documents SET provider_parse_status = %s, "
                "updated_at = NOW() WHERE knowledge_base_id = %s AND knowledge_id = %s "
                "RETURNING *",
                (status, knowledge_base_id, knowledge_id),
            )
            row = cursor.fetchone()
        return self._mapping(row) if row is not None else None
