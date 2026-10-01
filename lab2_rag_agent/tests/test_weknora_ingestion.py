from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lab2_rag_agent.catalog.documents import ProductDocumentMapping, ProductDocumentUpsert
from lab2_rag_agent.ingestion.weknora import (
    WeKnoraDocumentIngestion,
    WeKnoraIngestionError,
)

API_KEY = "ingestion-test-secret"
KB_ID = "configured-kb"


def make_mapping(
    *,
    product_id: str = "product-1",
    knowledge_id: str = "knowledge-1",
    content_sha256: str | None = None,
    provider_parse_status: str = "completed",
) -> ProductDocumentMapping:
    now = datetime(2026, 9, 29, tzinfo=UTC)
    return ProductDocumentMapping(
        id=1,
        product_id=product_id,
        knowledge_base_id=KB_ID,
        knowledge_id=knowledge_id,
        filename="datasheet.pdf",
        source_url=None,
        content_sha256=content_sha256,
        provider_parse_status=provider_parse_status,
        created_at=now,
        updated_at=now,
    )


class FakeProducts:
    def __init__(self, product_ids: set[str] | None = None) -> None:
        self.product_ids = product_ids or {"product-1"}
        self.lookups: list[str] = []

    def get(self, product_id: str):
        self.lookups.append(product_id)
        return object() if product_id in self.product_ids else None


class FakeDocumentMappings:
    def __init__(self, mappings: list[ProductDocumentMapping] | None = None) -> None:
        self.mappings = list(mappings or [])
        self.hash_lookups: list[tuple[str, str, str]] = []
        self.upserts: list[ProductDocumentUpsert] = []
        self.status_updates: list[tuple[str, str, str]] = []

    def find_by_content_sha256(self, product_id: str, knowledge_base_id: str, digest: str):
        self.hash_lookups.append((product_id, knowledge_base_id, digest))
        return next(
            (
                item
                for item in self.mappings
                if item.product_id == product_id
                and item.knowledge_base_id == knowledge_base_id
                and item.content_sha256 == digest
            ),
            None,
        )

    def get_by_knowledge_id(self, knowledge_base_id: str, knowledge_id: str):
        return next(
            (
                item
                for item in self.mappings
                if item.knowledge_base_id == knowledge_base_id
                and item.knowledge_id == knowledge_id
            ),
            None,
        )

    def upsert(self, mapping: ProductDocumentUpsert) -> ProductDocumentMapping:
        self.upserts.append(mapping)
        saved = make_mapping(
            product_id=mapping.product_id,
            knowledge_id=mapping.knowledge_id,
            content_sha256=mapping.content_sha256,
            provider_parse_status=mapping.provider_parse_status,
        )
        self.mappings = [
            row
            for row in self.mappings
            if (row.knowledge_base_id, row.knowledge_id)
            != (saved.knowledge_base_id, saved.knowledge_id)
        ] + [saved]
        return saved

    def update_parse_status(
        self, knowledge_base_id: str, knowledge_id: str, provider_parse_status: str
    ) -> ProductDocumentMapping | None:
        self.status_updates.append((knowledge_base_id, knowledge_id, provider_parse_status))
        current = self.get_by_knowledge_id(knowledge_base_id, knowledge_id)
        if current is None:
            return None
        updated = current.model_copy(update={"provider_parse_status": provider_parse_status})
        self.mappings = [
            updated if row.id == current.id else row for row in self.mappings
        ]
        return updated


def provider_knowledge(status: str) -> dict:
    return {
        "success": True,
        "data": {
            "id": "knowledge-1",
            "knowledge_base_id": KB_ID,
            "parse_status": status,
        },
    }


def make_ingestion(handler, *, products=None, mappings=None, sleeps=None, **options):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    ingestion = WeKnoraDocumentIngestion(
        base_url="http://weknora.test",
        api_key=API_KEY,
        knowledge_base_id=KB_ID,
        product_repository=products or FakeProducts(),
        product_document_repository=mappings or FakeDocumentMappings(),
        http_client=client,
        sleep=(sleeps.append if sleeps is not None else lambda _seconds: None),
        **options,
    )
    return ingestion, client


def test_new_file_upload_persists_sha256_and_waits_until_completed(tmp_path: Path) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"actual document bytes\x00")
    requests: list[httpx.Request] = []
    poll_statuses = iter(["finalizing", "completed"])

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json=provider_knowledge("processing"))
        return httpx.Response(200, json=provider_knowledge(next(poll_statuses)))

    mappings = FakeDocumentMappings()
    sleeps: list[float] = []
    ingestion, client = make_ingestion(respond, mappings=mappings, sleeps=sleeps)
    try:
        result = ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert result.knowledge_id == "knowledge-1"
    assert result.product_id == "product-1"
    assert result.content_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result.provider_parse_status == "completed"
    assert mappings.hash_lookups == [
        ("product-1", KB_ID, hashlib.sha256(source.read_bytes()).hexdigest())
    ]
    assert mappings.status_updates[-1] == (KB_ID, "knowledge-1", "completed")
    assert [request.method for request in requests] == ["POST", "GET", "GET"]
    assert str(requests[0].url) == (
        "http://weknora.test/api/v1/knowledge-bases/configured-kb/knowledge/file"
    )
    assert requests[0].headers["X-API-Key"] == API_KEY
    assert b'name="file"' in requests[0].content
    assert b"actual document bytes\x00" in requests[0].content


def test_existing_completed_checksum_mapping_skips_provider_upload(tmp_path: Path) -> None:
    source = tmp_path / "local-name-does-not-set-product.pdf"
    source.write_bytes(b"known bytes")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    existing = make_mapping(content_sha256=digest)
    mappings = FakeDocumentMappings([existing])
    requests: list[httpx.Request] = []
    ingestion, client = make_ingestion(
        lambda request: requests.append(request) or httpx.Response(500), mappings=mappings
    )
    try:
        result = ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert result.knowledge_id == existing.knowledge_id
    assert requests == []
    assert mappings.upserts == []


def test_unknown_product_is_rejected_before_any_provider_request(tmp_path: Path) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"document")
    requests: list[httpx.Request] = []
    products = FakeProducts(product_ids=set())
    ingestion, client = make_ingestion(
        lambda request: requests.append(request) or httpx.Response(200), products=products
    )
    try:
        with pytest.raises(WeKnoraIngestionError, match="unknown_product"):
            ingestion.ingest_file("missing-product", source)
    finally:
        client.close()

    assert products.lookups == ["missing-product"]
    assert requests == []


def test_existing_processing_mapping_is_polled_without_reupload(tmp_path: Path) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"already uploaded")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    existing = make_mapping(content_sha256=digest, provider_parse_status="processing")
    requests: list[httpx.Request] = []
    ingestion, client = make_ingestion(
        lambda request: requests.append(request)
        or httpx.Response(200, json=provider_knowledge("completed")),
        mappings=FakeDocumentMappings([existing]),
    )
    try:
        result = ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert result.provider_parse_status == "completed"
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_terminal_parse_status_is_persisted_and_reported_without_provider_details(
    tmp_path: Path, terminal_status: str
) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"terminal")
    mappings = FakeDocumentMappings()
    ingestion, client = make_ingestion(
        lambda request: httpx.Response(
            200,
            json=(
                provider_knowledge("processing")
                if request.method == "POST"
                else {
                    **provider_knowledge(terminal_status),
                    "message": f"provider echoed {API_KEY}",
                }
            ),
        ),
        mappings=mappings,
    )
    try:
        with pytest.raises(WeKnoraIngestionError, match=terminal_status) as error:
            ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert API_KEY not in str(error.value)
    assert mappings.mappings[0].provider_parse_status == terminal_status


def test_duplicate_409_reconciles_verified_provider_identity(tmp_path: Path) -> None:
    source = tmp_path / "same-content.pdf"
    source.write_bytes(b"same bytes already in WeKnora")
    requests: list[httpx.Request] = []
    mappings = FakeDocumentMappings()

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(
                409,
                json={
                    "success": False,
                    "message": "duplicate file",
                    "data": {
                        "id": "knowledge-1",
                        "knowledge_base_id": KB_ID,
                        "parse_status": "processing",
                    },
                    "code": "duplicate_file",
                },
            )
        return httpx.Response(200, json=provider_knowledge("completed"))

    ingestion, client = make_ingestion(respond, mappings=mappings)
    try:
        result = ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert result.knowledge_id == "knowledge-1"
    assert result.content_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result.provider_parse_status == "completed"
    assert len(mappings.upserts) == 1
    assert [request.method for request in requests] == ["POST", "GET"]


@pytest.mark.parametrize("http_status", [200, 409])
@pytest.mark.parametrize("parse_status", [None, "provider-invented-status"])
def test_new_provider_response_requires_a_known_parse_status(
    tmp_path: Path, http_status: int, parse_status: str | None
) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"document")
    data = {"id": "knowledge-1", "knowledge_base_id": KB_ID}
    if parse_status is not None:
        data["parse_status"] = parse_status
    body = (
        {"success": True, "data": data}
        if http_status == 200
        else {
            "success": False,
            "code": "duplicate_file",
            "data": data,
        }
    )
    mappings = FakeDocumentMappings()
    ingestion, client = make_ingestion(
        lambda _request: httpx.Response(http_status, json=body), mappings=mappings
    )
    try:
        with pytest.raises(WeKnoraIngestionError, match="parse status"):
            ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert mappings.upserts == []


@pytest.mark.parametrize(
    "duplicate_data",
    [
        None,
        {"knowledge_base_id": KB_ID, "parse_status": "processing"},
        {"id": "knowledge-1", "knowledge_base_id": "other-kb", "parse_status": "processing"},
    ],
)
def test_duplicate_409_without_verified_identity_fails_without_mapping(
    tmp_path: Path, duplicate_data
) -> None:
    source = tmp_path / "same-content.pdf"
    source.write_bytes(b"duplicate")
    mappings = FakeDocumentMappings()
    ingestion, client = make_ingestion(
        lambda _request: httpx.Response(
            409,
            json={"success": False, "code": "duplicate_file", "data": duplicate_data},
        ),
        mappings=mappings,
    )
    try:
        with pytest.raises(WeKnoraIngestionError):
            ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert mappings.upserts == []


def test_duplicate_409_cannot_reassign_an_identity_owned_by_another_product(
    tmp_path: Path,
) -> None:
    source = tmp_path / "same-content.pdf"
    source.write_bytes(b"duplicate")
    mappings = FakeDocumentMappings([make_mapping(product_id="another-product")])
    ingestion, client = make_ingestion(
        lambda _request: httpx.Response(
            409,
            json={
                "success": False,
                "code": "duplicate_file",
                "data": {
                    "id": "knowledge-1",
                    "knowledge_base_id": KB_ID,
                    "parse_status": "completed",
                },
            },
        ),
        mappings=mappings,
    )
    try:
        with pytest.raises(WeKnoraIngestionError, match="conflicts"):
            ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert mappings.upserts == []


def test_provider_http_failure_does_not_echo_response_or_api_key(tmp_path: Path) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"document")
    mappings = FakeDocumentMappings()
    ingestion, client = make_ingestion(
        lambda _request: httpx.Response(500, text=f"internal error {API_KEY}"),
        mappings=mappings,
    )
    try:
        with pytest.raises(WeKnoraIngestionError) as error:
            ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert "500" in str(error.value)
    assert API_KEY not in str(error.value)
    assert mappings.upserts == []


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"success": True, "data": []},
        {"success": True, "data": {"id": "knowledge-1", "parse_status": "processing"}},
        {
            "success": True,
            "data": {
                "id": "../other-endpoint",
                "knowledge_base_id": KB_ID,
                "parse_status": "processing",
            },
        },
        {
            "success": True,
            "data": {
                "id": API_KEY,
                "knowledge_base_id": KB_ID,
                "parse_status": "processing",
            },
        },
    ],
)
def test_malformed_upload_response_is_rejected_without_mapping(tmp_path: Path, body) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"document")
    mappings = FakeDocumentMappings()
    ingestion, client = make_ingestion(
        lambda _request: httpx.Response(200, json=body), mappings=mappings
    )
    try:
        with pytest.raises(WeKnoraIngestionError):
            ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert mappings.upserts == []


def test_status_poll_rejects_mismatched_identity(tmp_path: Path) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"document")
    mappings = FakeDocumentMappings()

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=provider_knowledge("processing"))
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "id": "different-knowledge",
                    "knowledge_base_id": KB_ID,
                    "parse_status": "completed",
                },
            },
        )

    ingestion, client = make_ingestion(respond, mappings=mappings)
    try:
        with pytest.raises(WeKnoraIngestionError, match="identity"):
            ingestion.ingest_file("product-1", source)
    finally:
        client.close()


def test_polling_stops_at_configured_attempt_limit(tmp_path: Path) -> None:
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"document")
    polls: list[httpx.Request] = []
    sleeps: list[float] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=provider_knowledge("pending"))
        polls.append(request)
        return httpx.Response(200, json=provider_knowledge("processing"))

    ingestion, client = make_ingestion(
        respond,
        sleeps=sleeps,
        max_poll_attempts=2,
        poll_interval_seconds=0.25,
    )
    try:
        with pytest.raises(WeKnoraIngestionError, match="configured limit"):
            ingestion.ingest_file("product-1", source)
    finally:
        client.close()

    assert len(polls) == 2
    assert sleeps == [0.25]


def test_directory_and_missing_product_id_are_rejected(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    ingestion, client = make_ingestion(
        lambda request: requests.append(request) or httpx.Response(200)
    )
    try:
        with pytest.raises(WeKnoraIngestionError, match="product_id_required"):
            ingestion.ingest_file(" ", tmp_path / "datasheet.pdf")
        with pytest.raises(WeKnoraIngestionError, match="regular_file"):
            ingestion.ingest_file("product-1", tmp_path)
    finally:
        client.close()

    assert requests == []
