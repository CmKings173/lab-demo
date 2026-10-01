from __future__ import annotations

from fastapi.testclient import TestClient

from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab2_rag_agent.openclaw.plugins.catalog_tools import CatalogTools
from lab2_rag_agent.retrieval.documents import FakeDocumentSearch
from lab2_rag_agent.runtime.http.app import create_app
from shared.contracts import DocumentChunk, Product, ProductType
from shared.tool_args import TOOL_ARG_MODELS


class FixedSizingService:
    def estimate(self, request):
        from shared.contracts import SizingResult

        return SizingResult(
            estimated_model_memory_gb=24,
            recommended_total_vram_gb=32,
            recommended_system_ram_gb=128,
            confidence=0.5,
        )


class SpyDocumentSearch:
    def __init__(self):
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        return FakeDocumentSearch(
            [DocumentChunk(id="hit-1", text="RAM source evidence", product_id="p-1")]
        ).search(request)


def make_client(document_search=None) -> TestClient:
    products = [
        Product(
            id="p-1",
            sku="SKU-1",
            name="Server one",
            product_type=ProductType.AI_SERVER,
            max_ram_gb=512,
            source_url="https://example.test/p-1",
        ),
        Product(
            id="p-2",
            name="Workstation two",
            product_type=ProductType.AI_WORKSTATION,
        ),
    ]
    tools = CatalogTools(
        repository=InMemoryProductRepository(products),
        document_search=document_search or FakeDocumentSearch(),
        sizing_service=FixedSizingService(),
    )
    return TestClient(create_app(tools=tools))


def test_health_is_process_health_only() -> None:
    with make_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_python_api_and_openclaw_plugin_allowlists_match_shared_contracts() -> None:
    import json
    import re
    from pathlib import Path

    from lab2_rag_agent.runtime.http.app import _TOOL_BINDINGS

    plugin_source = (
        Path(__file__).resolve().parents[1] / "openclaw" / "plugin" / "src" / "index.ts"
    ).read_text(encoding="utf-8")
    match = re.search(r"export const TOOL_NAMES = \[(.*?)\] as const", plugin_source, re.S)
    assert match is not None
    plugin_names = re.findall(r'"([a-z_]+)"', match.group(1))
    assert plugin_names == list(TOOL_ARG_MODELS)

    agent_config = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "openclaw"
            / "plugin"
            / "examples"
            / "lab2-agent.json"
        ).read_text(encoding="utf-8")
    )
    agent_tools = agent_config["agents"]["entries"]["lab2"]["tools"]
    assert agent_tools["profile"] == "full"
    assert set(agent_tools) == {"profile", "allow"}
    agent_allow = agent_tools["allow"]
    assert len(agent_allow) == len(set(agent_allow))
    assert set(agent_allow) == set(TOOL_ARG_MODELS)
    assert set(_TOOL_BINDINGS) == set(TOOL_ARG_MODELS)
    assert all(
        _TOOL_BINDINGS[name][0] is model for name, model in TOOL_ARG_MODELS.items()
    )


def test_allowlisted_http_api_validates_and_dispatches_all_six_tools() -> None:
    document_search = SpyDocumentSearch()
    with make_client(document_search) as client:
        search = client.post(
            "/tools/search_products",
            json={"filters": {"product_type": "ai_server"}, "limit": 3},
        )
        get = client.post("/tools/get_product", json={"product_id": "p-1"})
        documents = client.post(
            "/tools/search_product_documents",
            json={"query": "RAM", "product_id": "p-1", "top_k": 2},
        )
        comparison = client.post(
            "/tools/compare_products", json={"product_ids": ["p-2", "p-1"]}
        )
        configuration_comparison = client.post(
            "/tools/compare_configurations",
            json={"configuration_ids": ["cfg-a", "cfg-b"]},
        )
        sizing = client.post(
            "/tools/estimate_ai_requirements",
            json={"model_parameters_b": 14, "usage": "inference"},
        )

    assert search.status_code == get.status_code == documents.status_code == 200
    assert comparison.status_code == configuration_comparison.status_code == 200
    assert sizing.status_code == 200
    assert search.json()["data"]["products"][0]["id"] == "p-1"
    assert get.json()["data"]["id"] == "p-1"
    assert documents.json()["data"]["hits"][0]["chunk"]["product_id"] == "p-1"
    assert document_search.requests[0].model_dump() == {
        "query": "RAM",
        "product_id": "p-1",
        "top_k": 2,
    }
    assert [row["product"]["id"] for row in comparison.json()["data"]["products"]] == [
        "p-2",
        "p-1",
    ]
    assert configuration_comparison.json() == {
        "ok": False,
        "data": None,
        "error": "configuration_repository_not_configured",
    }
    assert sizing.json()["data"]["recommended_system_ram_gb"] == 128


def test_api_rejects_unknown_tools_and_extra_arguments_without_dispatch() -> None:
    with make_client() as client:
        unknown = client.post("/tools/run_sql", json={"query": "DROP TABLE products"})
        invalid = client.post(
            "/tools/search_product_documents",
            json={
                "query": "RAM",
                "provider_payload": {"knowledge_base_id": "attacker-value"},
            },
        )

    assert unknown.status_code == 404
    assert invalid.status_code == 422
    assert "attacker-value" not in invalid.text


def test_api_does_not_leak_provider_exception_secrets() -> None:
    class BrokenDocumentSearch:
        def search(self, _request):
            raise RuntimeError("WEKNORA_API_KEY=secret-value")

    with make_client(BrokenDocumentSearch()) as client:
        response = client.post(
            "/tools/search_product_documents", json={"query": "RAM"}
        )

    assert response.status_code == 502
    assert response.json() == {"error": {"code": "tool_execution_failed"}}
    assert "secret-value" not in response.text
