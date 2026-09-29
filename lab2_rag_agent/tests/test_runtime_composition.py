from __future__ import annotations

from lab2_rag_agent.openclaw.plugins.catalog_tools import CatalogTools
from lab2_rag_agent.runtime import composition
from lab2_rag_agent.runtime.settings import RuntimeSettings
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.sizing.service import DeterministicSizingService


def runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        postgres_dsn="postgresql://lab2:secret@localhost/catalog",
        weknora_base_url="http://127.0.0.1:8080",
        weknora_api_key="provider-secret",
        weknora_knowledge_base_id="demo-kb",
    )


def test_composition_uses_postgres_weknora_and_deterministic_services(monkeypatch) -> None:
    created = {}

    class FakeProductRepository:
        def __init__(self, dsn):
            created["product_dsn"] = dsn

    class FakeDocumentRepository:
        def __init__(self, dsn):
            created["document_dsn"] = dsn

    class FakeDocumentSearch:
        def __init__(self, **kwargs):
            created["document_search"] = kwargs

        def close(self):
            created["closed"] = True

    monkeypatch.setattr(composition, "PostgresProductRepository", FakeProductRepository)
    monkeypatch.setattr(
        composition, "PostgresProductDocumentRepository", FakeDocumentRepository
    )
    monkeypatch.setattr(composition, "WeKnoraDocumentSearch", FakeDocumentSearch)

    runtime = composition.build_runtime(runtime_settings())

    assert isinstance(runtime.tools, CatalogTools)
    assert isinstance(runtime.tools.sizing_service, DeterministicSizingService)
    assert isinstance(runtime.tools.comparison_service, RuleBasedComparisonService)
    assert runtime.tools.repository is runtime.products
    assert runtime.tools.document_search is runtime.document_search
    assert runtime.tools.configuration_repository is None
    assert created["product_dsn"] == created["document_dsn"] == (
        "postgresql://lab2:secret@localhost/catalog"
    )
    assert created["document_search"]["api_key"] == "provider-secret"
    assert "secret" not in repr(runtime)
    runtime.close()
    assert created["closed"] is True
