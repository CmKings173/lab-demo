from adapters.catalog import InMemoryProductRepository
from adapters.documents import FakeDocumentSearch
from adapters.model import FakeModelClient
from agent.openclaw.plugins.catalog_tools import CatalogTools
from services.comparison.service import RuleBasedComparisonService
from services.sizing.service import DeterministicSizingService
from shared.contracts import (
    ChatMessage,
    ComparisonResult,
    DocumentChunk,
    Product,
    ProductType,
    UsageType,
)
from shared.tool_contracts import TOOL_DEFINITIONS


def make_tools() -> CatalogTools:
    product = Product(
        id="p-1",
        sku="P-1",
        name="Server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        source_urls=["https://example.invalid/p-1"],
    )
    return CatalogTools(
        repository=InMemoryProductRepository([product]),
        document_search=FakeDocumentSearch(
            [DocumentChunk(id="doc-1", text="GPU memory", product_id="p-1")]
        ),
        comparison_service=RuleBasedComparisonService(),
        sizing_service=DeterministicSizingService(),
    )


def test_shared_tool_names_are_stable() -> None:
    assert {definition.name for definition in TOOL_DEFINITIONS} == {
        "search_products",
        "get_product",
        "search_product_documents",
        "compare_products",
        "compare_configurations",
        "estimate_ai_requirements",
    }


def test_document_search_supports_product_id_and_compare_returns_contract() -> None:
    tools = make_tools()

    documents = tools.search_product_documents("GPU", product_id="p-1")
    comparison = tools.compare_products(["p-1"])

    assert documents.ok is True
    assert documents.data.hits[0].chunk.product_id == "p-1"
    assert comparison.ok is True
    assert isinstance(comparison.data, ComparisonResult)
    assert comparison.data.product_ids == ["p-1"]


def test_estimate_tool_uses_shared_sizing_contract() -> None:
    result = make_tools().estimate_ai_requirements(32, UsageType.INFERENCE)

    assert result.ok is True
    assert result.data.recommended_total_vram_gb > 0


def test_model_client_supports_chat_messages_and_tool_definitions() -> None:
    response = FakeModelClient("Use search_products").complete(
        [ChatMessage(role="user", content="Find a server")], TOOL_DEFINITIONS
    )

    assert response.message.role == "assistant"
    assert response.message.content == "Use search_products"
