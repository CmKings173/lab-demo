from __future__ import annotations

from lab2_rag_agent.openclaw.plugins.catalog_tools import CatalogTools
from shared.contracts import DocumentSearchResult, ProductFilter, ToolResult, UsageType


def search_products(tools: CatalogTools, filters: ProductFilter | None = None,
                    query: str | None = None, limit: int = 20):
    return tools.search_products(filters, query, limit)


def get_product(tools: CatalogTools, product_id: str):
    return tools.get_product(product_id)


def search_product_documents(
    tools: CatalogTools, query: str, product_id: str | None = None, top_k: int = 5
) -> ToolResult[DocumentSearchResult]:
    return tools.search_product_documents(query, product_id, top_k)


def compare_products(tools: CatalogTools, product_ids: list[str]):
    return tools.compare_products(product_ids)


def compare_configurations(tools: CatalogTools, configuration_ids: list[str]):
    return tools.compare_configurations(configuration_ids)


def estimate_ai_requirements(
    tools: CatalogTools, model_parameters_b: float, usage: UsageType,
    quantization: str | None = None, context_length: int | None = None,
    concurrent_users: int | None = None, training_method: str | None = None,
):
    return tools.estimate_ai_requirements(
        model_parameters_b, usage, quantization, context_length, concurrent_users, training_method,
    )
