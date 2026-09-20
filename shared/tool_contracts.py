from shared.contracts import ToolDefinition

TOOL_DEFINITIONS = [
    ToolDefinition(
        name="search_products",
        description="Search AI server and workstation platforms.",
        parameters={
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "properties": {
                        "product_type": {
                            "type": "string",
                            "enum": ["ai_server", "ai_workstation"],
                        },
                        "min_ram_gb": {"type": "integer", "minimum": 1},
                        "min_gpu_count": {"type": "integer", "minimum": 1},
                        "max_price_vnd": {"type": "integer", "minimum": 0},
                    },
                    "additionalProperties": False,
                },
                "query": {"type": "string"},
            },
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="get_product",
        description="Get one product platform by id.",
        parameters={
            "type": "object",
            "properties": {"product_id": {"type": "string"}},
            "required": ["product_id"],
        },
    ),
    ToolDefinition(
        name="search_product_documents",
        description="Search product documents, optionally constrained by product id.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "product_id": {"type": "string"},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="compare_products",
        description="Compare catalog product platforms.",
        parameters={
            "type": "object",
            "properties": {
                "product_ids": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["product_ids"],
        },
    ),
    ToolDefinition(
        name="compare_configurations",
        description="Compare concrete AI server or workstation configurations.",
        parameters={
            "type": "object",
            "properties": {
                "configuration_ids": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["configuration_ids"],
        },
    ),
    ToolDefinition(
        name="estimate_ai_requirements",
        description="Estimate model memory, VRAM, RAM and storage requirements.",
        parameters={
            "type": "object",
            "properties": {
                "model_parameters_b": {"type": "number"},
                "usage": {"type": "string"},
            },
            "required": ["model_parameters_b", "usage"],
        },
    ),
]

TOOL_DEFINITIONS_BY_NAME = {definition.name: definition for definition in TOOL_DEFINITIONS}

__all__ = ["TOOL_DEFINITIONS", "TOOL_DEFINITIONS_BY_NAME"]
