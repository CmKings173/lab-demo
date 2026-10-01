"""Explicit composition root for the single-agent Lab 2 demo runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from lab2_rag_agent.catalog.document_repository import PostgresProductDocumentRepository
from lab2_rag_agent.catalog.repository import PostgresProductRepository
from lab2_rag_agent.openclaw.plugins.catalog_tools import CatalogTools
from lab2_rag_agent.retrieval.weknora import WeKnoraDocumentSearch
from lab2_rag_agent.runtime.settings import RuntimeSettings
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.sizing.service import DeterministicSizingService


@dataclass(frozen=True)
class Lab2Runtime:
    """Long-lived Lab 2 adapters and tool facade; repr omits configured secrets."""

    settings: RuntimeSettings = field(repr=False)
    products: PostgresProductRepository = field(repr=False)
    product_documents: PostgresProductDocumentRepository = field(repr=False)
    document_search: WeKnoraDocumentSearch = field(repr=False)
    tools: CatalogTools = field(repr=False)

    def close(self) -> None:
        self.document_search.close()


def build_runtime(settings: RuntimeSettings | None = None) -> Lab2Runtime:
    """Validate configuration and wire real PostgreSQL/WeKnora adapters."""
    settings = settings or RuntimeSettings.from_env()
    dsn = settings.postgres_dsn.get_secret_value()
    products = PostgresProductRepository(dsn)
    product_documents = PostgresProductDocumentRepository(dsn)
    document_search = WeKnoraDocumentSearch(
        base_url=str(settings.weknora_base_url).rstrip("/"),
        api_key=settings.weknora_api_key.get_secret_value(),
        knowledge_base_id=settings.weknora_knowledge_base_id,
        product_document_repository=product_documents,
    )
    tools = CatalogTools(
        repository=products,
        document_search=document_search,
        comparison_service=RuleBasedComparisonService(),
        sizing_service=DeterministicSizingService(),
    )
    return Lab2Runtime(
        settings=settings,
        products=products,
        product_documents=product_documents,
        document_search=document_search,
        tools=tools,
    )
