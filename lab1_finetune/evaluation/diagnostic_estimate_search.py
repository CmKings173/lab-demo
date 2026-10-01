"""Independent held-out diagnostic for estimate-then-search tool arguments.

Build with ``python -m lab1_finetune.evaluation.diagnostic_estimate_search``.
Run later with ``run_model_eval --benchmark`` pointing at the generated JSONL,
then score the saved report with ``--score-report``. This set is not part of the
frozen gold benchmark or training corpus.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab1_finetune.data.frozen_contracts import (
    TOOL_DEFINITIONS,
    ChatMessage,
    CustomerRequirement,
    EstimateAIRequirementsArgs,
    Product,
    ProductFilter,
    ProductSearchResult,
    ProductType,
    SearchProductsArgs,
    SizingResult,
    ToolCall,
    ToolResult,
    UsageType,
)
from lab1_finetune.data.schema import DatasetLabels, ExpectedToolCall, Intent, ScenarioType
from lab1_finetune.evaluation.schema import EvaluationCase

OUTPUT_PATH = Path(__file__).parent / "diagnostics" / "estimate_search.jsonl"
FROZEN_BENCHMARK_PATH = Path(__file__).with_name("gold_eval.jsonl")
FROZEN_MANIFEST_PATH = Path(__file__).with_name("eval_manifest.json")


@dataclass(frozen=True)
class DiagnosticInput:
    model: str
    model_size_b: float
    context_length: int
    concurrent_users: int
    budget_vnd: int
    product_type: ProductType
    recommended_ram_gb: int
    prompt_template: str


_INPUTS = (
    DiagnosticInput(
        "Qwen",
        11,
        10752,
        18,
        1_003_000_001,
        ProductType.AI_WORKSTATION,
        136,
        "Mình đang chuẩn bị cấu hình AI nội bộ cho {domain}. Model {model} cần phục vụ "
        "{users} người dùng đồng thời, cửa sổ ngữ cảnh {context} token; ngân sách giới "
        "hạn {budget} VND. Hãy ước tính tài nguyên rồi dùng kết quả RAM đó để lọc workstation.",
    ),
    DiagnosticInput(
        "Llama",
        17,
        11776,
        20,
        1_107_000_003,
        ProductType.AI_SERVER,
        168,
        "Bài toán {domain}: nếu chạy {model} với context window {context} tokens và "
        "concurrency {users}, khoản chi không quá {budget} VND. Tính RAM hệ thống cần "
        "thiết trước, kế tiếp tra server theo mức vừa tính.",
    ),
    DiagnosticInput(
        "Mistral",
        21,
        19456,
        22,
        1_211_000_009,
        ProductType.AI_WORKSTATION,
        200,
        "Cho nhóm {users} người cùng dùng {model} trong workload {domain}, context dài "
        "{context} token. Bên mình có trần {budget} VND; hãy sizing trước rồi search "
        "máy trạm dựa trên RAM sizing trả về.",
    ),
    DiagnosticInput(
        "Qwen coder",
        23,
        21504,
        26,
        1_313_000_011,
        ProductType.AI_SERVER,
        232,
        "Cần chốt hướng triển khai {domain} bằng {model}; context length đặt {context} "
        "tokens, tải đồng thời {users} users, ngân sách {budget} VND. Ước lượng RAM, "
        "sau đó tìm AI server theo recommendation.",
    ),
    DiagnosticInput(
        "Yi",
        26,
        23552,
        28,
        1_417_000_017,
        ProductType.AI_WORKSTATION,
        264,
        "Phương án dự kiến là {model} cho {domain}, {users} phiên hoạt động cùng lúc và "
        "context {context}. Với giới hạn đầu tư {budget} VND, hãy tính RAM khuyến nghị "
        "rồi lọc workstation theo output đó.",
    ),
    DiagnosticInput(
        "Llama coder",
        27,
        29696,
        30,
        1_519_000_019,
        ProductType.AI_SERVER,
        296,
        "Mình cần đánh giá nhu cầu {domain}: model {model}, context window {context} "
        "tokens, khoảng {users} truy cập song song, vốn tối đa {budget} VND. Hãy chạy "
        "sizing rồi dùng RAM đề xuất trong bước tìm máy chủ.",
    ),
    DiagnosticInput(
        "Qwen",
        29,
        33792,
        32,
        1_621_000_021,
        ProductType.AI_WORKSTATION,
        328,
        "Hãy giúp lập sizing cho {model} phục vụ {domain}; context={context} token, "
        "concurrency={users}, ngân quỹ={budget} VND. Tiếp nối kết quả sizing, tra "
        "workstation có RAM phù hợp.",
    ),
    DiagnosticInput(
        "Llama",
        33,
        38912,
        34,
        1_727_000_023,
        ProductType.AI_SERVER,
        360,
        "Đang xây dịch vụ {domain} trên {model}. Cấu hình workload gồm {users} phiên "
        "concurrent với cửa sổ {context} tokens; ngân sách tối đa là {budget} VND. Tính "
        "hệ thống trước rồi tìm AI server theo RAM được gợi ý.",
    ),
    DiagnosticInput(
        "Mistral",
        35,
        41984,
        36,
        1_829_000_027,
        ProductType.AI_WORKSTATION,
        392,
        "Theo đầu bài {domain}, dùng {model} cho {users} người đồng thời và context "
        "length {context}. Chi phí cơ bản cần nằm dưới {budget} VND; hãy suy ra RAM cần "
        "thiết rồi tìm workstation.",
    ),
    DiagnosticInput(
        "Qwen coder",
        36,
        46080,
        38,
        1_933_000_031,
        ProductType.AI_SERVER,
        424,
        "Model {model} sẽ chạy tác vụ {domain} với {context} token mỗi ngữ cảnh và tải "
        "{users} user song song. Trần chi là {budget} VND: hãy ước lượng RAM máy trước, "
        "kế đến truy vấn server.",
    ),
    DiagnosticInput(
        "Yi",
        38,
        48128,
        40,
        2_039_000_033,
        ProductType.AI_WORKSTATION,
        456,
        "Với {domain}, bên mình chọn {model}; quy mô context {context}, số client đồng "
        "thời {users}, và hạn mức {budget} VND. Hãy estimate mức RAM cần rồi tra catalog "
        "workstation theo mức đó.",
    ),
    DiagnosticInput(
        "Llama coder",
        41,
        50176,
        42,
        2_141_000_039,
        ProductType.AI_SERVER,
        488,
        "Tư vấn cấu hình cho {domain}: {model} phải hỗ trợ {users} lượt sử dụng cùng "
        "thời điểm, context window {context} tokens, ngân sách không quá {budget} VND. "
        "Tính RAM hệ thống khuyến nghị rồi tìm AI server phù hợp.",
    ),
)

_DOMAINS = (
    "trợ lý tra cứu nội bộ",
    "dịch vụ hỏi đáp kỹ thuật",
    "nền tảng phân tích dữ liệu",
    "công cụ hỗ trợ đội phát triển",
    "trợ lý nghiên cứu doanh nghiệp",
    "hệ thống tìm kiếm tài liệu",
    "dịch vụ tóm tắt báo cáo",
    "trợ lý xử lý yêu cầu khách hàng",
    "ứng dụng phân loại hồ sơ",
    "cổng hỏi đáp quy trình",
    "nền tảng hỗ trợ vận hành",
    "dịch vụ tìm kiếm tri thức",
)


def build_diagnostic_cases() -> list[EvaluationCase]:
    """Create fixed cases with values and wording isolated from training/eval."""
    cases = []
    for index, item in enumerate(_INPUTS, start=1):
        case_id = f"diag-estimate-search-{index:02d}"
        domain = _DOMAINS[index - 1]
        prompt = item.prompt_template.format(
            domain=domain,
            model=f"{item.model} {int(item.model_size_b)}B",
            context=item.context_length,
            users=item.concurrent_users,
            budget=f"{item.budget_vnd:,}".replace(",", "."),
        )
        estimate_args = EstimateAIRequirementsArgs(
            model_parameters_b=item.model_size_b,
            usage=UsageType.INFERENCE,
            context_length=item.context_length,
            concurrent_users=item.concurrent_users,
        )
        filters = ProductFilter(
            min_ram_gb=item.recommended_ram_gb,
            max_base_price_vnd=item.budget_vnd,
            product_type=item.product_type,
        )
        search_args = SearchProductsArgs(filters=filters)
        estimate_call = ToolCall(
            id=f"{case_id}-estimate",
            name="estimate_ai_requirements",
            arguments=estimate_args.model_dump(mode="json"),
        )
        search_call = ToolCall(
            id=f"{case_id}-search",
            name="search_products",
            arguments=search_args.model_dump(mode="json"),
        )
        sizing_result = SizingResult(
            estimated_model_memory_gb=item.model_size_b * 2,
            recommended_total_vram_gb=item.model_size_b * 3,
            recommended_system_ram_gb=item.recommended_ram_gb,
            confidence=0.8,
        )
        product = Product(
            id=f"DIAG-{index:03d}",
            sku=f"DIAG-SKU-{index:03d}",
            name="Synthetic diagnostic catalog result",
            manufacturer="Diagnostic fixture",
            product_type=item.product_type,
            max_ram_gb=1024,
            base_price_vnd=900_000_000,
        )
        search_result = ProductSearchResult(products=[product], total=1)
        labels = DatasetLabels(
            intent=Intent.SOLUTION_DESIGN,
            scenario_type=ScenarioType.SOLUTION_COMPLETE,
            extracted_requirement=CustomerRequirement(
                model_size_b=item.model_size_b,
                usage=UsageType.INFERENCE,
                budget_vnd=item.budget_vnd,
                concurrent_users=item.concurrent_users,
                context_length=item.context_length,
            ),
            should_call_tool=True,
            expected_tool="estimate_ai_requirements",
            expected_tool_calls=[
                ExpectedToolCall(name=estimate_call.name, arguments=estimate_call.arguments),
                ExpectedToolCall(name=search_call.name, arguments=search_call.arguments),
            ],
            expected_behavior="Estimate first; apply returned recommended RAM to catalog search.",
        )
        messages = [
            ChatMessage(role="system", content="Use the available tools and preserve user values."),
            ChatMessage(role="user", content=prompt),
            ChatMessage(role="assistant", tool_calls=[estimate_call]),
            ChatMessage(
                role="tool",
                tool_call_id=estimate_call.id,
                content=ToolResult[SizingResult](ok=True, data=sizing_result).model_dump_json(),
            ),
            ChatMessage(role="assistant", tool_calls=[search_call]),
            ChatMessage(
                role="tool",
                tool_call_id=search_call.id,
                content=ToolResult[ProductSearchResult](
                    ok=True, data=search_result
                ).model_dump_json(),
            ),
            ChatMessage(
                role="assistant",
                content=(
                    f"Ước tính đề xuất {item.recommended_ram_gb}GB RAM; catalog có "
                    f"{product.id} trong mức giá yêu cầu."
                ),
            ),
        ]
        cases.append(
            EvaluationCase(
                case_id=case_id,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                gold_labels=labels,
            )
        )
    return cases


def _expected_ram_from_tool_result(case: EvaluationCase) -> int:
    estimate_call = next(
        call
        for message in case.messages
        for call in message.tool_calls
        if call.name == "estimate_ai_requirements"
    )
    tool_message = next(
        message
        for message in case.messages
        if message.role == "tool" and message.tool_call_id == estimate_call.id
    )
    payload = json.loads(tool_message.content or "{}")
    return int(payload["data"]["recommended_system_ram_gb"])


def score_diagnostic_report(report: dict[str, Any]) -> dict[str, Any]:
    """Score the estimate→search tool decisions and their following assistant turns."""
    result_by_id = {item.get("case_id"): item for item in report.get("cases", [])}
    cases = build_diagnostic_cases()
    step1_matches = []
    step2_matches = []
    trajectory_matches = []

    def decision_call(
        result: dict[str, Any], index: int, expected_name: str
    ) -> dict | None:
        decisions = result.get("decision_outputs")
        if result.get("error") is not None or not isinstance(decisions, list):
            return None
        if len(decisions) < 2:
            return None
        decision = decisions[index]
        message = decision.get("message") if isinstance(decision, dict) else None
        calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not isinstance(calls, list) or len(calls) != 1:
            return None
        call = calls[0]
        if not isinstance(call, dict) or call.get("name") != expected_name:
            return None
        return call

    def has_valid_tool_trajectory(result: dict[str, Any]) -> bool:
        estimate = decision_call(result, 0, "estimate_ai_requirements")
        search = decision_call(result, 1, "search_products")
        if estimate is None or search is None:
            return False
        for decision in result["decision_outputs"][2:]:
            message = decision.get("message") if isinstance(decision, dict) else None
            calls = message.get("tool_calls") if isinstance(message, dict) else None
            if not isinstance(calls, list) or calls:
                return False
        return True

    for case in cases:
        result = result_by_id.get(case.case_id, {})
        estimate = decision_call(result, 0, "estimate_ai_requirements")
        search = decision_call(result, 1, "search_products")
        trajectory_matches.append(has_valid_tool_trajectory(result))
        expected_estimate = next(
            call.arguments
            for call in case.gold_labels.expected_tool_calls
            if call.name == "estimate_ai_requirements"
        )
        expected_search = next(
            call.arguments
            for call in case.gold_labels.expected_tool_calls
            if call.name == "search_products"
        )
        try:
            actual_estimate = EstimateAIRequirementsArgs.model_validate(
                estimate.get("arguments", {}) if estimate else {}
            ).model_dump(mode="json")
            expected_estimate_model = EstimateAIRequirementsArgs.model_validate(
                expected_estimate
            ).model_dump(mode="json")
            step1_matches.append(actual_estimate == expected_estimate_model)
        except (TypeError, ValueError):
            step1_matches.append(False)
        try:
            actual_search = SearchProductsArgs.model_validate(
                search.get("arguments", {}) if search else {}
            )
            expected_search_model = SearchProductsArgs.model_validate(expected_search)
            ram_from_estimate = _expected_ram_from_tool_result(case)
            expected_budget = case.gold_labels.extracted_requirement.budget_vnd
            expected_product_type = expected_search_model.filters.product_type
            step2_matches.append(
                expected_budget is not None
                and expected_product_type is not None
                and expected_search_model.filters.min_ram_gb == ram_from_estimate
                and expected_search_model.filters.max_base_price_vnd == expected_budget
                and actual_search.filters.min_ram_gb == ram_from_estimate
                and actual_search.filters.max_base_price_vnd == expected_budget
                and actual_search.filters.product_type == expected_product_type
            )
        except (TypeError, ValueError):
            step2_matches.append(False)
    count = len(cases)
    return {
        "case_count": count,
        "tool_trajectory_matches": sum(trajectory_matches),
        "tool_trajectory_accuracy": (
            sum(trajectory_matches) / count if count else 0.0
        ),
        "step1_argument_matches": sum(step1_matches),
        "step1_argument_accuracy": sum(step1_matches) / count if count else 0.0,
        "step2_derived_min_ram_matches": sum(step2_matches),
        "step2_derived_min_ram_accuracy": sum(step2_matches) / count if count else 0.0,
    }


def write_diagnostic_cases(path: Path = OUTPUT_PATH) -> str:
    if path.resolve() in {FROZEN_BENCHMARK_PATH.resolve(), FROZEN_MANIFEST_PATH.resolve()}:
        raise ValueError("Diagnostic output cannot overwrite the frozen benchmark artifacts")
    cases = build_diagnostic_cases()
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = "".join(case.model_dump_json() + "\n" for case in cases)
    path.write_text(contents, encoding="utf-8")
    import hashlib

    return hashlib.sha256(contents.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--score-report", type=Path)
    args = parser.parse_args(argv)
    if args.score_report:
        report = json.loads(args.score_report.read_text(encoding="utf-8"))
        print(json.dumps(score_diagnostic_report(report), indent=2))
        return
    print(
        json.dumps(
            {
                "case_count": len(build_diagnostic_cases()),
                "content_hash": write_diagnostic_cases(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
