import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from adapters.fake.catalog import InMemoryProductRepository
from adapters.fake.configurations import InMemoryConfigurationRepository
from adapters.fake.documents import FakeDocumentSearch
from adapters.fake.services import FakeComparisonService, FakeSizingService
from lab1_finetune.data.validator import DatasetValidator
from lab2_rag_agent.openclaw.plugins.catalog_tools import CatalogTools
from shared.contracts import DocumentChunk, Product, ProductConfiguration, ProductType
from shared.tool_args import TOOL_ARG_MODELS
from shared.tool_contracts import TOOL_DEFINITIONS_BY_NAME


def _tools() -> CatalogTools:
    products = [
        Product(
            id=product_id,
            sku=product_id.upper(),
            name=f"Demo {product_id}",
            manufacturer="Demo",
            product_type=ProductType.AI_SERVER,
        )
        for product_id in ("p-1", "p-2")
    ]
    configurations = [
        ProductConfiguration(configuration_id=f"cfg-{index}", product=product)
        for index, product in enumerate(products, start=1)
    ]
    return CatalogTools(
        repository=InMemoryProductRepository(products),
        document_search=FakeDocumentSearch(
            [DocumentChunk(id="doc-1", text="GPU memory", product_id="p-1")]
        ),
        comparison_service=FakeComparisonService(),
        sizing_service=FakeSizingService(),
        configuration_repository=InMemoryConfigurationRepository(configurations),
    )


VALID_ARGUMENTS = {
    "search_products": {
        "filters": {"product_type": "ai_server"},
        "query": "Demo",
        "limit": 10,
    },
    "get_product": {"product_id": "p-1"},
    "search_product_documents": {"query": "GPU", "product_id": "p-1", "top_k": 3},
    "compare_products": {"product_ids": ["p-1", "p-2"]},
    "compare_configurations": {"configuration_ids": ["cfg-1", "cfg-2"]},
    "estimate_ai_requirements": {
        "model_parameters_b": 32,
        "usage": "inference",
        "quantization": "int8",
        "context_length": 8192,
        "concurrent_users": 5,
    },
}

INVALID_ARGUMENTS = {
    "search_products": {"limit": 0},
    "get_product": {"product_id": ""},
    "search_product_documents": {"query": "", "top_k": 5},
    "compare_products": {"product_ids": ["p-1"]},
    "compare_configurations": {"configuration_ids": ["cfg-1"]},
    "estimate_ai_requirements": {"model_parameters_b": 0, "usage": "inference"},
}


@pytest.mark.parametrize("tool_name", sorted(VALID_ARGUMENTS))
def test_tool_schema_pydantic_runtime_and_dataset_validator_share_contract(tool_name: str) -> None:
    valid = VALID_ARGUMENTS[tool_name]
    invalid = INVALID_ARGUMENTS[tool_name]
    definition = TOOL_DEFINITIONS_BY_NAME[tool_name]
    schema_validator = Draft202012Validator(definition.parameters)

    schema_validator.validate(valid)
    normalized = TOOL_ARG_MODELS[tool_name].model_validate(valid).model_dump()
    assert getattr(_tools(), tool_name)(**valid).ok is True
    assert DatasetValidator._validate_arguments("matrix", valid, definition) == []
    assert normalized

    assert list(schema_validator.iter_errors(invalid))
    with pytest.raises(ValidationError):
        TOOL_ARG_MODELS[tool_name].model_validate(invalid)
    with pytest.raises(ValidationError):
        getattr(_tools(), tool_name)(**invalid)
    assert DatasetValidator._validate_arguments("matrix", invalid, definition)
