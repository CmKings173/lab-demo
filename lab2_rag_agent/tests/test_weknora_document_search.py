from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from lab2_rag_agent.catalog.documents import ProductDocumentMapping
from lab2_rag_agent.retrieval.weknora import (
    WeKnoraDocumentSearch,
    WeKnoraDocumentSearchError,
)
from shared.contracts import DocumentSearchRequest

API_KEY = "unit-test-secret-do-not-leak"
KB_ID = "configured-kb"


def mapping(
    knowledge_id: str,
    *,
    product_id: str = "product-a",
    knowledge_base_id: str = KB_ID,
    provider_parse_status: str = "completed",
    source_url: str | None = "https://example.test/datasheet.pdf",
) -> ProductDocumentMapping:
    now = datetime(2026, 9, 28, tzinfo=UTC)
    return ProductDocumentMapping(
        id=1,
        product_id=product_id,
        knowledge_base_id=knowledge_base_id,
        knowledge_id=knowledge_id,
        filename="datasheet.pdf",
        source_url=source_url,
        content_sha256=None,
        provider_parse_status=provider_parse_status,
        created_at=now,
        updated_at=now,
    )


class MappingRepository:
    def __init__(self, mappings: list[ProductDocumentMapping] = ()) -> None:
        self.mappings = list(mappings)
        self.lookups: list[tuple[str, str]] = []

    def list_by_product_id(self, product_id: str):
        return [item for item in self.mappings if item.product_id == product_id]

    def list_by_knowledge_base_id(self, knowledge_base_id: str):
        return [item for item in self.mappings if item.knowledge_base_id == knowledge_base_id]

    def get_by_knowledge_id(self, knowledge_base_id: str, knowledge_id: str):
        self.lookups.append((knowledge_base_id, knowledge_id))
        return next(
            (
                item
                for item in self.mappings
                if item.knowledge_base_id == knowledge_base_id
                and item.knowledge_id == knowledge_id
            ),
            None,
        )

    def find_by_content_sha256(self, *_args):
        raise AssertionError("not used by document search")

    def upsert(self, *_args):
        raise AssertionError("not used by document search")

    def update_parse_status(self, *_args):
        raise AssertionError("not used by document search")


@pytest.fixture
def client_factory():
    clients: list[httpx.Client] = []

    def create(handler):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    yield create
    for client in clients:
        client.close()


def provider_hit(**updates):
    return {
        "id": "chunk-1",
        "content": "Verified source evidence",
        "knowledge_id": "knowledge-1",
        "chunk_index": 0,
        "knowledge_title": "Technical Datasheet",
        "knowledge_filename": "datasheet.pdf",
        "seq": 0,
        "score": 0.91,
        "metadata": {
            "language": "vi",
            "page_hint": 2,
            "source_details": {"kind": "datasheet"},
            "echoed_secret": API_KEY,
        },
        **updates,
    }


def make_adapter(repository, client):
    return WeKnoraDocumentSearch(
        base_url="https://weknora.test/",
        api_key=API_KEY,
        knowledge_base_id=KB_ID,
        product_document_repository=repository,
        http_client=client,
    )


def test_product_search_sends_only_completed_mappings_in_configured_kb(
    client_factory,
) -> None:
    repository = MappingRepository([
        mapping("eligible-1"),
        mapping("wrong-kb", knowledge_base_id="another-kb"),
        mapping("still-processing", provider_parse_status="processing"),
        mapping("eligible-2", source_url=None),
    ])
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"success": True, "data": []})

    client = client_factory(respond)
    result = make_adapter(repository, client).search(
        DocumentSearchRequest(query=" RAM   tối đa ", product_id="product-a", top_k=3)
    )

    assert result.hits == []
    assert result.total == 0
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://weknora.test/api/v1/knowledge-search"
    assert request.headers["X-API-Key"] == API_KEY
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "query": " RAM   tối đa ",
        "knowledge_base_id": KB_ID,
        "knowledge_ids": ["eligible-1", "eligible-2"],
    }
    assert b"top_k" not in request.content


def test_product_without_eligible_mapping_returns_empty_without_http_call(
    client_factory,
) -> None:
    repository = MappingRepository([
        mapping("wrong-kb", knowledge_base_id="another-kb"),
        mapping("not-ready", provider_parse_status="processing"),
    ])
    requests = []
    client = client_factory(
        lambda request: requests.append(request) or httpx.Response(500)
    )

    result = make_adapter(repository, client).search(
        DocumentSearchRequest(query="GPU", product_id="product-a")
    )

    assert result.model_dump() == {"hits": [], "total": 0}
    assert requests == []


def test_unscoped_search_allowlists_only_completed_mappings_in_configured_kb(
    client_factory,
) -> None:
    repository = MappingRepository([
        mapping("knowledge-1", product_id="verified-product"),
        mapping("knowledge-2", product_id="another-product", source_url=None),
        mapping("processing", provider_parse_status="processing"),
        mapping("finalizing", provider_parse_status="finalizing"),
        mapping("failed", provider_parse_status="failed"),
        mapping("cancelled", provider_parse_status="cancelled"),
        mapping("wrong-kb", knowledge_base_id="another-kb"),
    ])
    request_bodies = []

    def respond(request):
        request_bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"success": True, "data": [provider_hit()]})

    result = make_adapter(repository, client_factory(respond)).search(
        DocumentSearchRequest(query="datasheet query", product_id=None, top_k=5)
    )

    assert request_bodies == [{
        "query": "datasheet query", "knowledge_base_id": KB_ID,
        "knowledge_ids": ["knowledge-1", "knowledge-2"],
    }]
    assert result.hits[0].chunk.product_id == "verified-product"
    assert result.hits[0].chunk.source_url == "https://example.test/datasheet.pdf"


@pytest.mark.parametrize("status", ["processing", "finalizing", "failed", "cancelled"])
def test_unscoped_without_eligible_mapping_returns_empty_without_http_call(
    status, client_factory,
) -> None:
    requests = []
    repository = MappingRepository([
        mapping("not-ready", provider_parse_status=status),
        mapping("wrong-kb", knowledge_base_id="another-kb"),
    ])
    client = client_factory(lambda request: requests.append(request) or httpx.Response(500))

    result = make_adapter(repository, client).search(DocumentSearchRequest(query="datasheet"))

    assert result.model_dump() == {"hits": [], "total": 0}
    assert requests == []


def test_unscoped_without_any_mapping_returns_empty_without_http_call(client_factory) -> None:
    requests = []
    client = client_factory(lambda request: requests.append(request) or httpx.Response(500))

    result = make_adapter(MappingRepository(), client).search(DocumentSearchRequest(query="GPU"))

    assert result.model_dump() == {"hits": [], "total": 0}
    assert requests == []


def test_product_hit_maps_evidence_conservatively_and_truncates_locally(
    client_factory,
) -> None:
    repository = MappingRepository([mapping("knowledge-1")])
    hits = [
        provider_hit(id=f"chunk-{index}", seq=index - 1, chunk_index=index - 1)
        for index in range(1, 4)
    ]
    result = make_adapter(
        repository,
        client_factory(
            lambda _request: httpx.Response(
                200, json={"success": True, "data": hits}
            )
        ),
    ).search(DocumentSearchRequest(query="RAM", product_id="product-a", top_k=2))

    assert result.total == 3
    assert [hit.chunk.id for hit in result.hits] == ["chunk-1", "chunk-2"]
    first = result.hits[0]
    assert first.chunk.text == "Verified source evidence"
    assert first.chunk.product_id == "product-a"
    assert first.chunk.source_url == "https://example.test/datasheet.pdf"
    assert first.chunk.page is None
    assert first.rank == 1
    assert first.retrieval_score is None
    assert first.rerank_score is None
    assert first.retrieval_method == "weknora"
    assert first.chunk.metadata == {
        "language": "vi",
        "page_hint": "2",
        "source_details": '{"kind":"datasheet"}',
        "provider": "weknora",
        "knowledge_id": "knowledge-1",
        "knowledge_title": "Technical Datasheet",
        "knowledge_filename": "datasheet.pdf",
        "chunk_index": "0",
        "seq": "0",
        "provider_score": "0.91",
    }
    assert all(isinstance(value, str) for value in first.chunk.metadata.values())


@pytest.mark.parametrize(("sequence", "expected_rank"), [(0, 1), (4, 5)])
def test_hit_rank_uses_provider_sequence_without_reordering(
    sequence, expected_rank, client_factory
) -> None:
    hits = [
        provider_hit(id="chunk-first", seq=7),
        provider_hit(id="chunk-second", seq=sequence),
    ]
    client = client_factory(
        lambda _request: httpx.Response(200, json={"success": True, "data": hits})
    )

    result = make_adapter(MappingRepository([mapping("knowledge-1")]), client).search(
        DocumentSearchRequest(query="RAM", top_k=2)
    )

    assert [hit.chunk.id for hit in result.hits] == ["chunk-first", "chunk-second"]
    assert [hit.rank for hit in result.hits] == [8, expected_rank]


def test_hit_without_provider_sequence_uses_one_based_response_order(client_factory) -> None:
    first = provider_hit(id="chunk-first", seq=4)
    second = provider_hit(id="chunk-second")
    second.pop("seq")
    client = client_factory(
        lambda _request: httpx.Response(
            200, json={"success": True, "data": [first, second]}
        )
    )

    result = make_adapter(MappingRepository([mapping("knowledge-1")]), client).search(
        DocumentSearchRequest(query="RAM", top_k=2)
    )

    assert [hit.chunk.id for hit in result.hits] == ["chunk-first", "chunk-second"]
    assert [hit.rank for hit in result.hits] == [5, 2]


def test_metadata_entry_with_api_key_in_key_is_dropped(client_factory) -> None:
    repository = MappingRepository([mapping("knowledge-1")])
    hit = provider_hit(metadata={f"credential-{API_KEY}-echo": "provider-value"})
    client = client_factory(
        lambda _request: httpx.Response(
            200, json={"success": True, "data": [hit]}
        )
    )

    result = make_adapter(repository, client).search(
        DocumentSearchRequest(query="RAM", top_k=1)
    )

    serialized_metadata = json.dumps(result.hits[0].chunk.metadata)
    assert API_KEY not in serialized_metadata
    assert f"credential-{API_KEY}-echo" not in result.hits[0].chunk.metadata


def test_missing_verified_source_url_stays_none(client_factory) -> None:
    repository = MappingRepository([mapping("knowledge-1", source_url=None)])
    result = make_adapter(
        repository,
        client_factory(
            lambda _request: httpx.Response(
                200, json={"success": True, "data": [provider_hit()]}
            )
        ),
    ).search(DocumentSearchRequest(query="RAM", product_id="product-a"))

    assert result.hits[0].chunk.source_url is None


def test_unscoped_search_truncates_locally_and_preserves_product_mapping(client_factory) -> None:
    repository = MappingRepository([
        mapping("knowledge-1", product_id="product-1"),
        mapping("knowledge-2", product_id="product-2"),
        mapping("knowledge-3", product_id="product-3"),
    ])
    hits = [
        provider_hit(id=f"chunk-{index}", knowledge_id=f"knowledge-{index}")
        for index in range(1, 4)
    ]
    result = make_adapter(
        repository,
        client_factory(
            lambda _request: httpx.Response(
                200, json={"success": True, "data": hits}
            )
        ),
    ).search(DocumentSearchRequest(query="RAM", top_k=1))

    assert result.total == 3
    assert len(result.hits) == 1
    assert result.hits[0].chunk.product_id == "product-1"
    assert repository.lookups == []


@pytest.mark.parametrize("status_code", [401, 404, 500])
def test_http_error_is_surfaced_without_secret(status_code, client_factory) -> None:
    client = client_factory(lambda _request: httpx.Response(status_code))

    with pytest.raises(WeKnoraDocumentSearchError) as error:
        make_adapter(MappingRepository([mapping("knowledge-1")]), client).search(
            DocumentSearchRequest(query="query")
        )

    assert str(status_code) in str(error.value)
    assert API_KEY not in str(error.value)


@pytest.mark.parametrize("exception_type", [httpx.ConnectError, httpx.TimeoutException])
def test_connection_and_timeout_errors_are_surfaced(exception_type, client_factory) -> None:
    def fail(request):
        raise exception_type("network unavailable", request=request)

    with pytest.raises(WeKnoraDocumentSearchError, match="request failed") as error:
        make_adapter(MappingRepository([mapping("knowledge-1")]), client_factory(fail)).search(
            DocumentSearchRequest(query="query")
        )
    assert API_KEY not in str(error.value)


def test_malformed_json_is_surfaced(client_factory) -> None:
    client = client_factory(
        lambda _request: httpx.Response(200, content=b"not-json")
    )

    with pytest.raises(WeKnoraDocumentSearchError, match="valid JSON"):
        make_adapter(MappingRepository([mapping("knowledge-1")]), client).search(
            DocumentSearchRequest(query="query")
        )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"success": False, "data": []}, "success must be true"),
        ({"success": True}, "data"),
        ({"success": True, "data": {}}, "list"),
        ([], "JSON object"),
        ({"success": True, "data": [{"id": "missing-required-fields"}]}, "hit"),
    ],
)
def test_malformed_provider_responses_are_rejected(body, message, client_factory) -> None:
    client = client_factory(lambda _request: httpx.Response(200, json=body))

    with pytest.raises(WeKnoraDocumentSearchError, match=message):
        make_adapter(MappingRepository([mapping("knowledge-1")]), client).search(
            DocumentSearchRequest(query="query")
        )


def test_product_scoped_result_rejects_unmapped_provider_document(client_factory) -> None:
    client = client_factory(
        lambda _request: httpx.Response(
            200,
            json={"success": True, "data": [provider_hit(knowledge_id="other-doc")]},
        )
    )

    with pytest.raises(WeKnoraDocumentSearchError, match="unmapped knowledge id"):
        make_adapter(MappingRepository([mapping("knowledge-1")]), client).search(
            DocumentSearchRequest(query="query", product_id="product-a")
        )


@pytest.mark.parametrize("returned_id", ["unmapped", "processing", "wrong-kb"])
def test_unscoped_result_rejects_provider_document_outside_allowlist(
    returned_id, client_factory,
) -> None:
    repository = MappingRepository([
        mapping("knowledge-1"),
        mapping("processing", provider_parse_status="processing"),
        mapping("wrong-kb", knowledge_base_id="another-kb"),
    ])
    client = client_factory(
        lambda _request: httpx.Response(
            200, json={"success": True, "data": [provider_hit(knowledge_id=returned_id)]}
        )
    )

    with pytest.raises(WeKnoraDocumentSearchError, match="unmapped knowledge id"):
        make_adapter(repository, client).search(DocumentSearchRequest(query="query"))


@pytest.mark.parametrize(
    "bad_hit",
    [
        {"id": "chunk-only"},
        provider_hit(id=" "),
        provider_hit(content=None),
        provider_hit(metadata=[]),
        provider_hit(chunk_index="0"),
        provider_hit(seq=-1),
        provider_hit(score="0.91"),
    ],
)
def test_malformed_provider_hit_fields_are_rejected(bad_hit, client_factory) -> None:
    client = client_factory(
        lambda _request: httpx.Response(
            200, json={"success": True, "data": [bad_hit]}
        )
    )

    with pytest.raises(WeKnoraDocumentSearchError):
        make_adapter(MappingRepository([mapping("knowledge-1")]), client).search(
            DocumentSearchRequest(query="query")
        )


def test_adapter_rejects_blank_configuration_without_echoing_api_key() -> None:
    with pytest.raises(ValueError, match="api_key") as error:
        WeKnoraDocumentSearch(
            base_url="https://weknora.test",
            api_key=" ",
            knowledge_base_id=KB_ID,
            product_document_repository=MappingRepository(),
        )
    assert API_KEY not in str(error.value)
