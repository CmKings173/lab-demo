from __future__ import annotations

from dataclasses import dataclass

from lab1_finetune.data.schema import Intent, ScenarioType

EXPANSION_SEED = 20260922
EVAL_SEED = 20260923
EXPANSION_TARGET = 1200
EVAL_TARGET = 120
NEAR_DUPLICATE_THRESHOLD = 0.92


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    quota: int
    intent: Intent
    scenario_types: tuple[ScenarioType, ...]
    summary: str


EXPANSION_FAMILY_SPECS = (
    FamilySpec(
        "expanded_solution_design",
        160,
        Intent.SOLUTION_DESIGN,
        (ScenarioType.SOLUTION_COMPLETE, ScenarioType.LARGE_MODEL_LOW_BUDGET),
        "Thiết kế giải pháp theo nhu cầu model, người dùng và ngân sách",
    ),
    FamilySpec(
        "expanded_missing_information",
        160,
        Intent.SOLUTION_DESIGN,
        (
            ScenarioType.MISSING_BUDGET,
            ScenarioType.MISSING_USAGE,
            ScenarioType.MISSING_MODEL_SIZE,
            ScenarioType.MISSING_MULTIPLE_FIELDS,
        ),
        "Làm rõ các thông tin bắt buộc trước khi tư vấn cấu hình",
    ),
    FamilySpec(
        "expanded_novice_users",
        120,
        Intent.SOLUTION_DESIGN,
        (ScenarioType.AMBIGUOUS_SOLUTION, ScenarioType.MISSING_MULTIPLE_FIELDS),
        "Người dùng chưa rành kỹ thuật cần được hướng dẫn từng bước",
    ),
    FamilySpec(
        "expanded_product_search",
        110,
        Intent.PRODUCT_SEARCH,
        (
            ScenarioType.SEARCH_PRODUCT_BY_BUDGET,
            ScenarioType.SEARCH_WORKSTATION_BY_RAM,
            ScenarioType.SEARCH_SERVER_BY_GPU_SLOTS,
        ),
        "Tìm sản phẩm theo loại máy và điều kiện kỹ thuật rõ ràng",
    ),
    FamilySpec(
        "expanded_comparison",
        90,
        Intent.PRODUCT_COMPARISON,
        (ScenarioType.COMPARE_PRODUCTS, ScenarioType.COMPARE_CONFIGURATIONS),
        "So sánh sản phẩm hoặc cấu hình theo các tiêu chí đã nêu",
    ),
    FamilySpec(
        "expanded_multi_tool",
        110,
        Intent.SOLUTION_DESIGN,
        (
            ScenarioType.SOLUTION_COMPLETE,
            ScenarioType.SEARCH_WORKSTATION_BY_RAM,
            ScenarioType.TECHNICAL_MAX_RAM,
        ),
        "Luồng nhiều bước kết hợp tính nhu cầu, tìm kiếm và đọc bằng chứng",
    ),
    FamilySpec(
        "expanded_technical_questions",
        90,
        Intent.TECHNICAL_QUESTION,
        (
            ScenarioType.GENERAL_VRAM,
            ScenarioType.GENERAL_INFERENCE,
            ScenarioType.TECHNICAL_MAX_RAM,
            ScenarioType.TECHNICAL_MAX_GPU,
            ScenarioType.UNKNOWN_PRODUCT_SPEC,
        ),
        "Câu hỏi kỹ thuật và tra cứu thông số có kiểm chứng",
    ),
    FamilySpec(
        "expanded_lora_inference",
        80,
        Intent.SOLUTION_DESIGN,
        (
            ScenarioType.FINETUNE_32B_SOLUTION,
            ScenarioType.GENERAL_LORA,
            ScenarioType.SOLUTION_COMPLETE,
        ),
        "Phân biệt inference, fine-tune và nhu cầu tài nguyên LoRA",
    ),
    FamilySpec(
        "expanded_requirement_change",
        80,
        Intent.SOLUTION_DESIGN,
        (ScenarioType.REQUIREMENT_CHANGED_MID_CONVERSATION,),
        "Cập nhật requirement sau khi người dùng thay đổi kế hoạch",
    ),
    FamilySpec(
        "expanded_contradictory",
        60,
        Intent.SOLUTION_DESIGN,
        (ScenarioType.CONTRADICTORY_REQUIREMENT, ScenarioType.LARGE_MODEL_LOW_BUDGET),
        "Nhận diện ràng buộc mâu thuẫn và không hứa hẹn sai",
    ),
    FamilySpec(
        "expanded_failure_abstention",
        90,
        Intent.TECHNICAL_QUESTION,
        (
            ScenarioType.TOOL_FAILURE,
            ScenarioType.NO_PRODUCT_FOUND,
            ScenarioType.UNKNOWN_PRODUCT_SPEC,
        ),
        "Tool lỗi, không có kết quả hoặc thiếu bằng chứng cần abstain",
    ),
    FamilySpec(
        "expanded_out_of_scope",
        50,
        Intent.OUT_OF_SCOPE,
        (ScenarioType.OUT_SCOPE_LAPTOP, ScenarioType.OUT_SCOPE_NETWORK_SWITCH),
        "Yêu cầu ngoài phạm vi tư vấn máy AI và cấu hình AI",
    ),
)
