from adapters.catalog import InMemoryProductRepository
from agent.openclaw.plugins.catalog_tools import CatalogTools
from shared.contracts import Product, ProductType


def test_controlled_catalog_tools_expose_domain_operations_only() -> None:
    product = Product(
        id="p-1",
        sku="P-1",
        name="Demo Workstation",
        manufacturer="Demo",
        product_type=ProductType.AI_WORKSTATION,
        max_gpu_count=2,
        vram_gb=48,
        max_ram_gb=512,
        price_vnd=100,
    )
    tools = CatalogTools(InMemoryProductRepository([product]))

    result = tools.search_products()

    assert result.ok is True
    assert result.data.products[0].id == "p-1"
