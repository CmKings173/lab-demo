# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lab1_finetune.data.schema import (
    DatasetLabels,
    FineTuneExample,
    Intent,
    ScenarioType,
)
from shared.contracts import ChatMessage, CustomerRequirement, ToolCall
from shared.tool_contracts import TOOL_DEFINITIONS

SEED_PATH = Path(__file__).with_name("seed") / "gold_seed_vi.jsonl"
SYSTEM_MESSAGE = (
    "Bạn là trợ lý tư vấn AI Server và AI Workstation. Chỉ dùng dữ liệu từ công cụ, "
    "không suy đoán thông số sản phẩm và hỏi lại khi thiếu dữ liệu bắt buộc."
)


def _specs() -> list[dict[str, Any]]:
    return [
        _spec("solution_complete", Intent.SOLUTION_DESIGN,
              ("Bên tôi cần máy chạy Qwen 32B nội bộ, inference cho 5 người, ngân sách 300 triệu.",
               "Công ty muốn chạy model 14B local cho 10 người, chỉ inference, ngân sách 220 triệu."),
              "estimate_ai_requirements", ({"model_size_b": 32, "usage": "inference", "concurrent_users": 5, "budget_vnd": 300_000_000}, {"model_size_b": 14, "usage": "inference", "concurrent_users": 10, "budget_vnd": 220_000_000})),
        _spec("missing_budget", Intent.SOLUTION_DESIGN,
              ("Tôi cần workstation chạy model 32B, chủ yếu inference.",
               "Bên mình muốn chạy Qwen 14B nội bộ cho 5 người, không cần fine-tune."),
              None, ({"model_size_b": 32, "usage": "inference"}, {"model_size_b": 14, "usage": "inference", "concurrent_users": 5}), ["budget_vnd"],
              "Bạn dự kiến ngân sách tối đa cho hệ thống là bao nhiêu?"),
        _spec("missing_usage", Intent.SOLUTION_DESIGN,
              ("Tôi cần máy cho model 32B, ngân sách khoảng 350 triệu.",
               "Công ty định đầu tư server cho model 70B, ngân sách tối đa 800 triệu."),
              None, ({"model_size_b": 32, "budget_vnd": 350_000_000}, {"model_size_b": 70, "budget_vnd": 800_000_000}), ["usage"],
              "Bạn cần hệ thống để chạy inference hay fine-tune model?"),
        _spec("missing_model_size", Intent.SOLUTION_DESIGN,
              ("Tôi có 250 triệu và muốn mua workstation chạy AI nội bộ, chủ yếu inference.",
               "Bên tôi cần server chạy LLM local, chỉ inference, ngân sách 600 triệu."),
              None, ({"usage": "inference", "budget_vnd": 250_000_000}, {"usage": "inference", "budget_vnd": 600_000_000}), ["model_size_b"],
              "Bạn dự kiến chạy model nào hoặc model có khoảng bao nhiêu tỷ tham số?"),
        _spec("missing_multiple_fields", Intent.SOLUTION_DESIGN,
              ("Tôi đang cần một máy AI cho công ty.", "Bên mình muốn đầu tư hệ thống chạy LLM nội bộ."),
              None, ({}, {}), ["model_size_b", "usage", "budget_vnd"],
              "Bạn cho biết model hoặc quy mô model, mục đích inference hay fine-tune và ngân sách tối đa nhé."),
        _spec("ambiguous_solution", Intent.SOLUTION_DESIGN,
              ("Tôi muốn mua máy AI mạnh nhất.", "Cấu hình cho tôi một máy thật mạnh để chạy AI."),
              None, ({}, {}), ["model_size_b", "usage", "budget_vnd"],
              "Tôi cần biết workload, quy mô model, mục đích sử dụng và ngân sách trước khi cấu hình."),
        _spec("contradictory_requirement", Intent.SOLUTION_DESIGN,
              ("Tôi muốn fine-tune model 70B trên workstation chỉ có 1 GPU 24GB, ngân sách 100 triệu.",
               "Tôi cần chạy model 70B full precision nhưng chỉ muốn dùng một GPU 16GB."),
              None, ({"model_size_b": 70, "usage": "fine_tune", "budget_vnd": 100_000_000}, {"model_size_b": 70, "usage": "inference"}), [],
              "Các ràng buộc hiện tại mâu thuẫn với nhu cầu tài nguyên; tôi chưa thể khẳng định có cấu hình phù hợp."),
        _spec("search_workstation_by_ram", Intent.PRODUCT_SEARCH,
              ("Tìm workstation hỗ trợ tối thiểu 512GB RAM.", "Có workstation AI nào nâng RAM lên ít nhất 1TB không?"),
              "search_products", ({}, {}), tool_args=({"filters": {"product_type": "ai_workstation", "min_ram_gb": 512}}, {"filters": {"product_type": "ai_workstation", "min_ram_gb": 1024}})),
        _spec("search_server_by_gpu_slots", Intent.PRODUCT_SEARCH,
              ("Tìm server AI hỗ trợ ít nhất 4 GPU.", "Có server nào lắp được 8 GPU không?"),
              "search_products", ({}, {}), tool_args=({"filters": {"product_type": "ai_server", "min_gpu_count": 4}}, {"filters": {"product_type": "ai_server", "min_gpu_count": 8}})),
        _spec("search_product_by_budget", Intent.PRODUCT_SEARCH,
              ("Tìm workstation AI giá không quá 200 triệu.", "Tìm server AI trong ngân sách tối đa 500 triệu."),
              "search_products", ({"budget_vnd": 200_000_000}, {"budget_vnd": 500_000_000}), tool_args=({"filters": {"product_type": "ai_workstation", "max_price_vnd": 200_000_000}}, {"filters": {"product_type": "ai_server", "max_price_vnd": 500_000_000}})),
        _spec("no_product_found", Intent.PRODUCT_SEARCH,
              ("Tìm server AI hỗ trợ 8 GPU nhưng giá dưới 100 triệu.", "Tìm workstation 4 GPU, RAM 2TB dưới 150 triệu."),
              "search_products", ({}, {}), final="Hiện tôi chưa tìm thấy sản phẩm nào trong danh mục đáp ứng đồng thời các điều kiện trên.", tool_result={"ok": True, "products": []}),
        _spec("compare_products", Intent.PRODUCT_COMPARISON,
              ("So sánh giúp tôi hai mã SP-001 và SP-002.", "Cho tôi xem điểm khác nhau giữa WS-101 và WS-102."),
              "compare_products", ({}, {}), tool_args=({"product_ids": ["SP-001", "SP-002"]}, {"product_ids": ["WS-101", "WS-102"]})),
        _spec("compare_configurations", Intent.PRODUCT_COMPARISON,
              ("So sánh phương án 2 GPU 48GB với 1 GPU 96GB cho cùng workstation.", "So sánh cấu hình A dùng 4 GPU với cấu hình B dùng 2 GPU dung lượng lớn hơn."),
              "compare_configurations", ({}, {}), tool_args=({"configuration_ids": ["cfg-2x48", "cfg-1x96"]}, {"configuration_ids": ["cfg-a", "cfg-b"]})),
        _spec("technical_max_ram", Intent.TECHNICAL_QUESTION,
              ("Server SP-001 hỗ trợ tối đa bao nhiêu RAM?", "Workstation WS-001 nâng RAM tối đa được bao nhiêu?"),
              "search_product_documents", ({}, {}), tool_args=({"query": "RAM tối đa", "product_id": "SP-001"}, {"query": "RAM tối đa", "product_id": "WS-001"})),
        _spec("technical_max_gpu", Intent.TECHNICAL_QUESTION,
              ("Server SP-002 lắp tối đa được bao nhiêu GPU?", "Workstation WS-003 có mấy khe GPU?"),
              "search_product_documents", ({}, {}), tool_args=({"query": "số GPU tối đa", "product_id": "SP-002"}, {"query": "khe GPU", "product_id": "WS-003"})),
        _spec("unknown_product_spec", Intent.TECHNICAL_QUESTION,
              ("Sản phẩm SP-003 hỗ trợ tối đa bao nhiêu GPU?", "Mẫu WS-004 hỗ trợ tối đa bao nhiêu RAM?"),
              "search_product_documents", ({}, {}), final="Hiện tài liệu chưa đủ thông tin để xác nhận thông số tối đa của sản phẩm này.", tool_result={"ok": True, "hits": [], "unknown": True}),
        _spec("tool_failure", Intent.PRODUCT_SEARCH,
              ("Tìm giúp tôi server AI 4 GPU.", "Kiểm tra thông số RAM tối đa của SP-005."),
              ("search_products", "search_product_documents"), ({}, {}),
              final="Hiện tôi chưa truy vấn được dữ liệu nên chưa thể xác nhận kết quả phù hợp.",
              tool_args=({"filters": {"product_type": "ai_server", "min_gpu_count": 4}}, {"query": "RAM tối đa", "product_id": "SP-005"}),
              tool_result={"ok": False, "error": "tạm thời không truy cập được"}),
        _spec("general_vram", Intent.GENERAL_AI_QUESTION,
              ("VRAM có tác dụng gì khi chạy model AI?", "Tại sao chạy LLM lại cần nhiều VRAM?"),
              None, ({}, {}), final="VRAM lưu trọng số model và dữ liệu trung gian khi GPU tính toán; model và ngữ cảnh càng lớn thì nhu cầu VRAM thường càng cao."),
        _spec("general_inference", Intent.GENERAL_AI_QUESTION,
              ("Inference là gì?", "Inference khác training ở điểm nào?"), None, ({}, {}),
              final="Inference là giai đoạn dùng model đã huấn luyện để tạo dự đoán hoặc câu trả lời; training cập nhật trọng số còn inference thì không."),
        _spec("general_lora", Intent.GENERAL_AI_QUESTION,
              ("LoRA là gì?", "Tại sao fine-tune bằng LoRA tiết kiệm tài nguyên hơn?"), None, ({}, {}),
              final="LoRA chỉ huấn luyện các ma trận hạng thấp bổ sung thay vì cập nhật toàn bộ trọng số, nên thường cần ít bộ nhớ và tính toán hơn."),
        _spec("out_scope_laptop", Intent.OUT_OF_SCOPE,
              ("Tư vấn laptop AI khoảng 30 triệu.", "Có laptop nào chạy AI tốt dưới 40 triệu không?"), None, ({}, {}),
              final="Phạm vi hiện tại chỉ hỗ trợ AI Server và AI Workstation, chưa bao gồm laptop."),
        _spec("out_scope_network_switch", Intent.OUT_OF_SCOPE,
              ("Tư vấn switch mạng 48 port.", "Tôi cần firewall cho văn phòng."), None, ({}, {}),
              final="Yêu cầu này nằm ngoài phạm vi AI Server và AI Workstation hiện tại."),
        _spec("finetune_32b_solution", Intent.SOLUTION_DESIGN,
              ("Tôi muốn fine-tune model 32B bằng LoRA, ngân sách 500 triệu.", "Bên tôi cần hệ thống fine-tune nhẹ model 32B, ngân sách 600 triệu."),
              "estimate_ai_requirements", ({"model_size_b": 32, "usage": "fine_tune", "budget_vnd": 500_000_000, "training_method": "LoRA"}, {"model_size_b": 32, "usage": "fine_tune", "budget_vnd": 600_000_000, "training_method": "LoRA"})),
        _spec("large_model_low_budget", Intent.SOLUTION_DESIGN,
              ("Tôi muốn chạy model 70B local, ngân sách chỉ 80 triệu.", "Cần inference model 70B nhưng ngân sách tối đa 100 triệu."),
              "estimate_ai_requirements", ({"model_size_b": 70, "usage": "inference", "budget_vnd": 80_000_000}, {"model_size_b": 70, "usage": "inference", "budget_vnd": 100_000_000}),
              final="Tôi sẽ tính nhu cầu tài nguyên trước; chưa thể kết luận ngân sách phù hợp nếu chưa có giá cấu hình đầy đủ."),
        _spec("requirement_changed_mid_conversation", Intent.SOLUTION_DESIGN,
              ("Tôi đổi kế hoạch: cần chạy 32B và nâng ngân sách lên 300 triệu.", "Thực ra bên tôi cần fine-tune LoRA nữa."),
              "estimate_ai_requirements", ({"model_size_b": 32, "usage": "inference", "budget_vnd": 300_000_000}, {"model_size_b": 14, "usage": "fine_tune", "budget_vnd": 200_000_000, "training_method": "LoRA"})),
    ]


def _spec(
    scenario: str,
    intent: Intent,
    users: tuple[str, str],
    tool: str | tuple[str, str] | None,
    requirements: tuple[dict[str, Any], dict[str, Any]],
    missing: list[str] | None = None,
    final: str | None = None,
    tool_args: tuple[dict[str, Any], dict[str, Any]] | None = None,
    tool_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "scenario": ScenarioType(scenario),
        "intent": intent,
        "users": users,
        "tool": tool,
        "requirements": requirements,
        "missing": missing or [],
        "final": final,
        "tool_args": tool_args,
        "tool_result": tool_result,
    }


def _default_arguments(tool: str, requirement: CustomerRequirement) -> dict[str, Any]:
    if tool == "estimate_ai_requirements":
        return {"model_parameters_b": requirement.model_size_b, "usage": requirement.usage}
    if tool == "search_products":
        return {"filters": {}}
    return {"query": "thông tin sản phẩm"}


def build_gold_seed_examples() -> list[FineTuneExample]:
    examples: list[FineTuneExample] = []
    for family_number, spec in enumerate(_specs(), start=1):
        scenario: ScenarioType = spec["scenario"]
        family_id = f"{family_number:02d}_{scenario.value}"
        for index, user_text in enumerate(spec["users"]):
            requirement = CustomerRequirement.model_validate(spec["requirements"][index])
            configured_tool = spec["tool"]
            tool = configured_tool[index] if isinstance(configured_tool, tuple) else configured_tool
            messages = [
                ChatMessage(role="system", content=SYSTEM_MESSAGE),
                ChatMessage(role="user", content=user_text),
            ]
            if scenario == ScenarioType.REQUIREMENT_CHANGED_MID_CONVERSATION:
                initial_request = (
                    "Ban đầu tôi muốn chạy model 14B để inference, ngân sách 200 triệu."
                    if index == 0
                    else "Ban đầu bên tôi chỉ cần inference model 14B với ngân sách 200 triệu."
                )
                messages = [
                    ChatMessage(role="system", content=SYSTEM_MESSAGE),
                    ChatMessage(role="user", content=initial_request),
                    ChatMessage(
                        role="assistant",
                        content="Tôi đã ghi nhận yêu cầu ban đầu. Bạn có muốn điều chỉnh gì thêm không?",
                    ),
                    ChatMessage(role="user", content=user_text),
                ]
            if tool:
                call_id = f"{family_id}-{index + 1}-call"
                arguments = (
                    spec["tool_args"][index]
                    if spec["tool_args"]
                    else _default_arguments(tool, requirement)
                )
                messages.extend(
                    [
                        ChatMessage(
                            role="assistant",
                            tool_calls=[ToolCall(id=call_id, name=tool, arguments=arguments)],
                        ),
                        ChatMessage(
                            role="tool",
                            tool_call_id=call_id,
                            content=json.dumps(
                                spec["tool_result"] or {"ok": True, "data": []},
                                ensure_ascii=False,
                            ),
                        ),
                        ChatMessage(
                            role="assistant",
                            content=spec["final"]
                            or "Tôi chỉ sử dụng dữ liệu vừa được công cụ trả về để trả lời yêu cầu.",
                        ),
                    ]
                )
            else:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=spec["final"] or "Bạn vui lòng bổ sung thông tin còn thiếu.",
                    )
                )
            examples.append(
                FineTuneExample(
                    example_id=f"{family_id}-{index + 1}",
                    scenario_family_id=family_id,
                    scenario_summary=spec["users"][0],
                    task_type="tool_calling" if tool else "conversation",
                    difficulty="medium",
                    language="vi",
                    source_type="gold_human_review",
                    messages=messages,
                    tools=TOOL_DEFINITIONS if tool else [],
                    labels=DatasetLabels(
                        intent=spec["intent"],
                        scenario_type=scenario,
                        extracted_requirement=requirement,
                        missing_fields=spec["missing"],
                        should_call_tool=tool is not None,
                        expected_tool=tool,
                        must_not_invent_product_fact=True,
                        expected_behavior="Không suy đoán dữ liệu sản phẩm.",
                    ),
                )
            )
    return examples


def write_gold_seed(path: Path = SEED_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            example.model_dump_json(exclude_none=False) + "\n"
            for example in build_gold_seed_examples()
        ),
        encoding="utf-8",
    )


def load_gold_seed(path: Path = SEED_PATH) -> list[FineTuneExample]:
    return [
        FineTuneExample.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_seed_examples() -> list[FineTuneExample]:
    return load_gold_seed()


if __name__ == "__main__":
    write_gold_seed()
