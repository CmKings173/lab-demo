from shared.contracts import (
    ComparisonResult,
    DocumentSearchResult,
    Product,
    ProductSearchResult,
    SizingResult,
    ToolResult,
)

TOOL_RESULT_MODELS = {
    "search_products": ToolResult[ProductSearchResult],
    "get_product": ToolResult[Product],
    "search_product_documents": ToolResult[DocumentSearchResult],
    "compare_products": ToolResult[ComparisonResult],
    "compare_configurations": ToolResult[ComparisonResult],
    "estimate_ai_requirements": ToolResult[SizingResult],
}


def typed_result(step: dict) -> ToolResult:
    return TOOL_RESULT_MODELS[step["name"]].model_validate(
        {key: step[key] for key in ("ok", "data", "error")}
    )
