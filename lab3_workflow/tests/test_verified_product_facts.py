from __future__ import annotations

import httpx
import pytest

from adapters.fake.options import ram_options, storage_options
from adapters.real.weknora_provenance import WeKnoraEvidenceProvenanceVerifier
from lab2_rag_agent.catalog.documents import ProductDocumentMapping
from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab2_rag_agent.retrieval.weknora import WeKnoraDocumentSearch
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.configuration.service import ProductConfigurationBuilder
from lab3_workflow.evidence.capacity_extractor import extract_capacity_value
from lab3_workflow.evidence.verified_product_facts import (
    VerifiedDocumentProductFactResolver,
)
from lab3_workflow.proposal.service import RuleBasedProposalService, RuleBasedProposalVerifier
from lab3_workflow.sizing.service import DeterministicSizingService
from lab3_workflow.validation.service import RuleBasedConfigurationValidator
from lab3_workflow.workflow.orchestrator import DeterministicWorkflow
from shared.contracts import (
    CustomerRequirement,
    DocumentChunk,
    DocumentHit,
    DocumentSearchRequest,
    DocumentSearchResult,
    GPUOption,
    Product,
    ProductConfiguration,
    ProductType,
    UsageType,
    ValidationStatus,
    WorkflowState,
)


@pytest.mark.parametrize(
    ("text", "field_name", "expected"),
    [
        ("maximum RAM: 512 GB", "max_ram_gb", 512),
        ("supports up to 2 TB RAM", "max_ram_gb", 2048),
        ("supports up to 4 GPUs", "max_gpu_slots", 4),
        ("maximum storage: 8 TB", "max_storage_gb", 8192),
        ("Installed with 512 GB RAM", "max_ram_gb", None),
        ("Currently installed with up to 512 GB RAM", "max_ram_gb", None),
        ("2 x RTX PRO 6000", "max_gpu_slots", None),
        ("maximum RAM: 1 PB", "max_ram_gb", None),
        ("maximum RAM: 512 GiB", "max_ram_gb", None),
        ("maximum RAM: 0.1 TB", "max_ram_gb", None),
        ("maximum RAM: -512 GB", "max_ram_gb", None),
        ("maximum RAM: 512 GB or 1 TB", "max_ram_gb", None),
        ("maximum RAM: 512 GB/s", "max_ram_gb", None),
        ("maximum RAM: 512 GB and up to 1 TB", "max_ram_gb", None),
        ("RAM tối đa: 512 GB", "max_ram_gb", 512),
        ("4 GPU slots", "max_gpu_slots", 4),
        ("storage capacity up to 8 TB", "max_storage_gb", 8192),
        ("Lưu trữ tối đa 8 TB", "max_storage_gb", 8192),
        ("Số GPU tối đa: 4", "max_gpu_slots", 4),
    ],
)
def test_extract_capacity_value_is_narrow_and_deterministic(
    text: str, field_name: str, expected: int | None
) -> None:
    assert extract_capacity_value(text, field_name) == expected


def test_extract_capacity_value_rejects_unknown_fields_and_invalid_values() -> None:
    assert extract_capacity_value("maximum RAM: 512 GB", "installed_ram_gb") is None
    assert extract_capacity_value("maximum GPU slots: true", "max_gpu_slots") is None


def _mapping(
    *,
    knowledge_id: str = "knowledge-1",
    product_id: str = "p-1",
    knowledge_base_id: str = "kb-1",
    source_url: str | None = "https://example.invalid/spec.pdf",
    provider_parse_status: str = "completed",
) -> ProductDocumentMapping:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return ProductDocumentMapping(
        id=1,
        product_id=product_id,
        knowledge_base_id=knowledge_base_id,
        knowledge_id=knowledge_id,
        filename="spec.pdf",
        source_url=source_url,
        content_sha256=None,
        provider_parse_status=provider_parse_status,
        created_at=now,
        updated_at=now,
    )


class _MappingRepository:
    def __init__(self, mappings: list[ProductDocumentMapping]) -> None:
        self._mappings = {
            (mapping.knowledge_base_id, mapping.knowledge_id): mapping
            for mapping in mappings
        }

    def get_by_knowledge_id(self, knowledge_base_id: str, knowledge_id: str):
        return self._mappings.get((knowledge_base_id, knowledge_id))

    def list_by_product_id(self, product_id: str):
        return [mapping for mapping in self._mappings.values() if mapping.product_id == product_id]

    def list_by_knowledge_base_id(self, knowledge_base_id: str):
        return [
            mapping
            for mapping in self._mappings.values()
            if mapping.knowledge_base_id == knowledge_base_id
        ]


def _hit(
    text: str = "Maximum RAM: 512 GB",
    *,
    knowledge_id: str = "knowledge-1",
    chunk_id: str = "chunk-1",
    product_id: str | None = "p-1",
    source_url: str | None = "https://example.invalid/spec.pdf",
    rank: int = 1,
    metadata: dict[str, str] | None = None,
    retrieval_score: float | None = None,
) -> DocumentHit:
    return DocumentHit(
        chunk=DocumentChunk(
            id=chunk_id,
            text=text,
            product_id=product_id,
            source_url=source_url,
            metadata=metadata or {"provider": "weknora", "knowledge_id": knowledge_id},
        ),
        rank=rank,
        retrieval_method="weknora",
        retrieval_score=retrieval_score,
    )


def _configuration() -> ProductConfiguration:
    product = Product(
        id="p-1",
        sku="P-1",
        name="Demo server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        max_ram_gb=None,
        max_gpu_slots=None,
        max_storage_gb=None,
        base_price_vnd=100_000_000,
        base_price_includes={"chassis", "cpu"},
    )
    return ProductConfiguration(configuration_id="cfg-1", product=product)


def test_real_resolver_bridges_workflow_unknown_through_revalidation() -> None:
    product = Product(
        id="p-1",
        sku="P-1",
        name="Demo server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        max_ram_gb=None,
        max_gpu_slots=4,
        max_storage_gb=8192,
        base_price_vnd=100_000_000,
        base_price_includes={"chassis", "cpu", "storage"},
        source_urls=["https://example.invalid/p-1"],
    )
    gpu = GPUOption(
        gpu_id="gpu-96",
        name="GPU 96 GB",
        memory_gb=96,
        supported_product_ids=[product.id],
        price_vnd=50_000_000,
    )
    mapping = _mapping()
    hit = _hit()
    repository = _MappingRepository([mapping])

    class OneHitSearch:
        requests: list[DocumentSearchRequest] = []

        def search(self, request: DocumentSearchRequest) -> DocumentSearchResult:
            self.requests.append(request)
            return DocumentSearchResult(hits=[hit], total=1)

    document_search = OneHitSearch()
    workflow = DeterministicWorkflow(
        repository=InMemoryProductRepository([product]),
        sizing_service=DeterministicSizingService(),
        configuration_builder=ProductConfigurationBuilder(
            [gpu], ram_options([product.id]), storage_options([product.id])
        ),
        validator=RuleBasedConfigurationValidator(),
        document_search=document_search,
        comparison_service=RuleBasedComparisonService(),
        proposal_service=RuleBasedProposalService(),
        proposal_verifier=RuleBasedProposalVerifier(),
        fact_resolver=VerifiedDocumentProductFactResolver(
            WeKnoraEvidenceProvenanceVerifier(repository, knowledge_base_id="kb-1")
        ),
    )

    context = workflow.run(
        CustomerRequirement(
            model_size_b=20,
            usage=UsageType.INFERENCE,
            budget_vnd=500_000_000,
            storage_requirement_gb=1000,
        )
    )

    assert WorkflowState.READ_DOCUMENTS in context.history
    assert WorkflowState.APPLY_VERIFIED_FACTS in context.history
    assert WorkflowState.REVALIDATE in context.history
    assert context.configurations[0].product.max_ram_gb == 512
    assert context.validation_results[context.configurations[0].configuration_id].status == (
        ValidationStatus.PASS
    )
    assert context.state != WorkflowState.INSUFFICIENT_PRODUCT_DATA
    query = document_search.requests[0].query
    assert "maximum RAM memory capacity" in query
    assert all(token not in query for token in ("max_ram_gb", "memory_gb", "capacity_gb"))


@pytest.mark.parametrize(
    "bad_hit,bad_mapping",
    [
        (_hit(product_id="p-other"), None),
        (_hit(metadata={"provider": "weknora"}), None),
        (_hit(), _mapping(knowledge_id="different-id")),
        (_hit(), _mapping(knowledge_base_id="kb-other")),
        (_hit(), _mapping(provider_parse_status="processing")),
        (_hit(), _mapping(product_id="p-other")),
        (_hit(), _mapping(source_url=None)),
        (_hit(source_url="https://example.invalid/other.pdf"), None),
        (_hit(metadata={"provider": "other", "knowledge_id": "knowledge-1"}), None),
    ],
)
def test_provenance_verifier_fails_closed_for_mapping_mismatches(
    bad_hit: DocumentHit, bad_mapping: ProductDocumentMapping | None
) -> None:
    verifier = WeKnoraEvidenceProvenanceVerifier(
        _MappingRepository([bad_mapping] if bad_mapping is not None else [_mapping()]),
        knowledge_base_id="kb-1",
    )

    assert verifier.verify(bad_hit, expected_product_id="p-1") is None


def test_provenance_verifier_accepts_only_completed_canonical_mapping() -> None:
    verifier = WeKnoraEvidenceProvenanceVerifier(
        _MappingRepository([_mapping()]), knowledge_base_id="kb-1"
    )

    provenance = verifier.verify(_hit(), expected_product_id="p-1")
    assert provenance is not None
    assert provenance.product_id == "p-1"
    assert provenance.document_id == "knowledge-1"
    assert provenance.source_url == "https://example.invalid/spec.pdf"


def test_verified_resolver_rejects_conflicts_in_both_orders() -> None:
    mappings = [
        _mapping(knowledge_id="knowledge-1", source_url="https://example.invalid/1.pdf"),
        _mapping(knowledge_id="knowledge-2", source_url="https://example.invalid/2.pdf"),
    ]
    resolver = VerifiedDocumentProductFactResolver(
        WeKnoraEvidenceProvenanceVerifier(
            _MappingRepository(mappings), knowledge_base_id="kb-1"
        )
    )
    first = _hit("Maximum RAM: 512 GB", knowledge_id="knowledge-1", source_url="https://example.invalid/1.pdf")
    second = _hit("Maximum RAM: 1 TB", knowledge_id="knowledge-2", source_url="https://example.invalid/2.pdf")

    assert resolver.resolve(_configuration(), ["max_ram_gb"], [first, second]) == []
    assert resolver.resolve(_configuration(), ["max_ram_gb"], [second, first]) == []


def test_verified_resolver_deduplicates_and_selects_by_rank_then_stable_identity() -> None:
    mappings = [
        _mapping(knowledge_id="knowledge-z", source_url="https://example.invalid/z.pdf"),
        _mapping(knowledge_id="knowledge-a", source_url="https://example.invalid/a.pdf"),
        _mapping(knowledge_id="knowledge-first", source_url="https://example.invalid/first.pdf"),
    ]
    resolver = VerifiedDocumentProductFactResolver(
        WeKnoraEvidenceProvenanceVerifier(
            _MappingRepository(mappings), knowledge_base_id="kb-1"
        )
    )
    hits = [
        _hit(
            "Maximum RAM: 512 GB",
            knowledge_id="knowledge-z",
            source_url="https://example.invalid/z.pdf",
            rank=1,
            retrieval_score=0.99,
        ),
        _hit(
            "Maximum RAM: 512 GB",
            knowledge_id="knowledge-a",
            source_url="https://example.invalid/a.pdf",
            rank=1,
            retrieval_score=0.01,
        ),
        _hit(
            "Maximum RAM: 512 GB",
            knowledge_id="knowledge-first",
            source_url="https://example.invalid/first.pdf",
            rank=2,
        ),
    ]

    first_order = resolver.resolve(_configuration(), ["max_ram_gb"], hits)
    reverse_order = resolver.resolve(_configuration(), ["max_ram_gb"], list(reversed(hits)))

    assert len(first_order) == len(reverse_order) == 1
    assert first_order[0] == reverse_order[0]
    assert first_order[0].document_id == "knowledge-a"
    assert first_order[0].value == 512
    assert first_order[0].verified is True
    assert first_order[0].confidence == 1.0


def test_verified_resolver_only_extracts_requested_unknown_fields() -> None:
    resolver = VerifiedDocumentProductFactResolver(
        WeKnoraEvidenceProvenanceVerifier(
            _MappingRepository([_mapping()]), knowledge_base_id="kb-1"
        )
    )
    hit = _hit("Maximum RAM: 512 GB; maximum GPU slots: 4")

    facts = resolver.resolve(_configuration(), ["max_ram_gb"], [hit])

    assert [fact.field_name for fact in facts] == ["max_ram_gb"]


def test_apply_rechecks_mapping_and_rejects_fact_after_status_becomes_ineligible() -> None:
    repository = _MappingRepository([_mapping()])
    resolver = VerifiedDocumentProductFactResolver(
        WeKnoraEvidenceProvenanceVerifier(repository, knowledge_base_id="kb-1")
    )
    configuration = _configuration()
    facts = resolver.resolve(configuration, ["max_ram_gb"], [_hit()])
    repository._mappings[("kb-1", "knowledge-1")] = _mapping(
        provider_parse_status="processing"
    )

    applied = resolver.apply(configuration, facts)

    assert applied.product.max_ram_gb is None


def test_mocked_weknora_http_hit_flows_through_mapping_verifier_and_resolver() -> None:
    mapping = _mapping()
    repository = _MappingRepository([mapping])
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/api/v1/knowledge-search"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {
                        "id": "chunk-17",
                        "content": "Maximum RAM: 512 GB",
                        "knowledge_id": "knowledge-1",
                        "score": 0.999,
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(respond))
    search = WeKnoraDocumentSearch(
        base_url="https://weknora.example.invalid",
        api_key="test-weknora-key",
        knowledge_base_id="kb-1",
        product_document_repository=repository,
        http_client=client,
    )
    resolver = VerifiedDocumentProductFactResolver(
        WeKnoraEvidenceProvenanceVerifier(repository, knowledge_base_id="kb-1")
    )

    try:
        result = search.search(
            DocumentSearchRequest(query="maximum RAM capacity", product_id="p-1")
        )
        hit = result.hits[0]
        facts = resolver.resolve(_configuration(), ["max_ram_gb"], result.hits)
    finally:
        client.close()

    assert len(requests) == 1
    assert "verified" not in hit.chunk.metadata
    assert hit.chunk.metadata["knowledge_id"] == "knowledge-1"
    assert hit.chunk.metadata["provider_score"] == "0.999"
    assert len(facts) == 1
    assert facts[0].value == 512
    assert facts[0].document_id == "knowledge-1"
    assert facts[0].chunk_id == "chunk-17"
    assert facts[0].verified is True
    assert facts[0].confidence == 1.0
