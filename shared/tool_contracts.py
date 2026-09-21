from shared.contracts import ToolDefinition
from shared.tool_args import TOOL_ARG_MODELS

DESCRIPTIONS = {
    "search_products": (
        "Tìm AI Server và AI Workstation trong danh mục sản phẩm theo bộ lọc có cấu trúc."
    ),
    "get_product": "Lấy thông tin một nền tảng sản phẩm theo mã sản phẩm.",
    "search_product_documents": (
        "Tìm bằng chứng kỹ thuật trong tài liệu của sản phẩm, có thể giới hạn theo mã sản phẩm."
    ),
    "compare_products": "So sánh thông tin catalog của nhiều nền tảng sản phẩm.",
    "compare_configurations": "So sánh các cấu hình AI Server hoặc AI Workstation đã tạo.",
    "estimate_ai_requirements": (
        "Ước lượng nhu cầu VRAM, RAM và tài nguyên cho workload AI theo quy tắc deterministic."
    ),
}

TOOL_DEFINITIONS = [
    ToolDefinition(name=name, description=DESCRIPTIONS[name], parameters=model.model_json_schema())
    for name, model in TOOL_ARG_MODELS.items()
]
TOOL_DEFINITIONS_BY_NAME = {definition.name: definition for definition in TOOL_DEFINITIONS}
