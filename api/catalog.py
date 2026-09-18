from __future__ import annotations

from agent.openclaw.plugins.catalog_tools import CatalogTools
from shared.contracts import ProductFilter, ToolResult


def search_products(tools: CatalogTools, filters: ProductFilter | None = None):
    return tools.search_products(filters)


def get_product(tools: CatalogTools, product_id: str):
    return tools.get_product(product_id)


def search_product_documents(tools: CatalogTools, query: str) -> ToolResult[None]:
    return tools.search_product_documents(query)


def compare_products(tools: CatalogTools, product_ids: list[str]):
    return tools.compare_products(product_ids)
