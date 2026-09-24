"""Frozen, independent evaluation benchmark for the Lab 1 dataset.

The benchmark deliberately has its own wording, values and template identifiers.
It is not produced by mutating or paraphrasing the expansion generator.
"""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any, Iterable

from lab1_finetune.data.expansion.difficulty import infer_difficulty
from lab1_finetune.data.fixtures.tool_results import typed_result
from lab1_finetune.data.schema import (
    DatasetLabels,
    ExpectedToolCall,
    FineTuneExample,
    Intent,
    ScenarioType,
)
from lab1_finetune.data.similarity import near_duplicate_pairs, near_duplicate_stats
from lab1_finetune.evaluation.schema import EvaluationCase
from lab1_finetune.evaluation.wording import render_eval_prompt
from shared.contracts import ChatMessage, CustomerRequirement, ProductType, ToolCall
from shared.tool_args import TOOL_ARG_MODELS
from shared.tool_contracts import TOOL_DEFINITIONS

EVAL_SEED = 20260923
EVAL_TARGET = 120

PERSONAS = (
    "NON_TECHNICAL_USER",
    "MANAGER",
    "PURCHASING",
    "IT_GENERALIST",
    "DEVELOPER",
    "ML_ENGINEER",
    "SOLUTION_ARCHITECT",
)


@dataclass(frozen=True)
class BenchmarkRecord:
    case: EvaluationCase
    scenario_family_id: str
    persona: str
    difficulty: str
    template_id: str


@dataclass(frozen=True)
class EvalIsolationReport:
    exact_overlap: int
    near_duplicate_pairs: int
    near_duplicate_rate: float
    scenario_counts: dict[str, int]
    persona_counts: dict[str, int]
    difficulty_counts: dict[str, int]
    tool_pattern_counts: dict[str, int]
    internal_exact_user_duplicates: int = 0
    internal_near_user_pairs: int = 0
    internal_near_user_example_ratio: float = 0.0
    template_overlap_with_training: int = 0

    @property
    def valid(self) -> bool:
        return (
            self.exact_overlap == 0
            and self.near_duplicate_pairs == 0
            and self.internal_exact_user_duplicates == 0
            and self.internal_near_user_example_ratio < 0.02
            and self.template_overlap_with_training == 0
        )


def _product(ordinal: int, product_type: ProductType) -> dict[str, Any]:
    prefix = "SRV" if product_type == ProductType.AI_SERVER else "WS"
    product_id = f"EVAL-{prefix}-{ordinal:04d}"
    return {
        "id": product_id,
        "sku": product_id,
        "name": f"Evaluation {prefix} Platform {ordinal:04d}",
        "manufacturer": "INDEPENDENT-BENCHMARK-FIXTURE",
        "product_type": product_type.value,
        "platform": "evaluation-platform",
        "max_ram_gb": 192 + (ordinal % 5) * 128,
        "max_gpu_slots": 2 + (ordinal % 4) * 2,
        "max_storage_gb": 4096 + (ordinal % 3) * 2048,
        "base_price_vnd": 85_000_000 + (ordinal % 7) * 21_000_000,
    }


def _estimate_step(model_size: float, usage: str, context_length: int, users: int) -> dict[str, Any]:
    return {
        "name": "estimate_ai_requirements",
        "arguments": {
            "model_parameters_b": model_size,
            "usage": usage,
            "context_length": context_length,
            "concurrent_users": users,
            "training_method": "LoRA" if usage == "fine_tune" else None,
        },
        "ok": True,
        "data": {
            "estimated_model_memory_gb": round(model_size * (4.2 if usage == "fine_tune" else 2.8), 1),
            "recommended_total_vram_gb": 96 if model_size <= 14 else 192,
            "recommended_system_ram_gb": 128 if users <= 8 else 256,
            "recommended_storage_gb": 2048,
            "assumptions": ["Kết quả là ước tính định hướng, cần benchmark theo workload thật."],
            "warnings": ["Chưa bao gồm mọi chi phí của cấu hình hoàn chỉnh."],
            "confidence": 0.62,
        },
        "error": None,
    }


def _search_step(product: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "search_products",
        "arguments": {"filters": filters, "query": "", "limit": 5},
        "ok": True,
        "data": {"products": [product], "total": 1},
        "error": None,
    }


def _document_step(product_id: str, field_name: str, value: int | None, *, empty: bool = False) -> dict[str, Any]:
    arguments = {
        "query": f"tài liệu kỹ thuật {field_name}",
        "product_id": product_id,
        "top_k": 4,
    }
    if empty:
        return {
            "name": "search_product_documents",
            "arguments": arguments,
            "ok": True,
            "data": {"hits": [], "total": 0},
            "error": None,
        }
    source = f"https://benchmark.invalid/{product_id}/{field_name}"
    return {
        "name": "search_product_documents",
        "arguments": arguments,
        "ok": True,
        "data": {
            "hits": [
                {
                    "chunk": {
                        "id": f"eval-chunk-{product_id}-{field_name}",
                        "text": f"{field_name}: {value}",
                        "source_url": source,
                        "product_id": product_id,
                        "page": 3,
                        "metadata": {"field_name": field_name, "value": str(value), "verified": "true"},
                    },
                    "retrieval_score": 0.79,
                    "rerank_score": 0.71,
                    "rank": 1,
                    "retrieval_method": "independent_fixture",
                }
            ],
            "total": 1,
        },
        "error": None,
    }


def _failure_step(product_id: str) -> dict[str, Any]:
    return {
        "name": "search_product_documents",
        "arguments": {"query": "thông số trong tài liệu", "product_id": product_id, "top_k": 4},
        "ok": False,
        "data": None,
        "error": "document_service_unavailable",
    }


def _comparison_step(product_ids: list[str]) -> dict[str, Any]:
    return {
        "name": "compare_products",
        "arguments": {"product_ids": product_ids},
        "ok": True,
        "data": {
            "product_ids": product_ids,
            "dimensions": ["max_ram_gb", "max_gpu_slots", "base_price_vnd"],
            "summary": "Cần đối chiếu thêm workload thực tế trước khi chốt.",
        },
        "error": None,
    }


def _make_case(
    *,
    case_id: str,
    family: str,
    persona: str,
    difficulty: str,
    template_id: str,
    scenario_type: ScenarioType,
    intent: Intent,
    user: str,
    final: str,
    requirement: CustomerRequirement | None = None,
    missing_fields: list[str] | None = None,
    should_abstain: bool = False,
    steps: list[dict[str, Any]] | None = None,
    history: list[dict[str, str]] | None = None,
) -> BenchmarkRecord:
    messages = [
        ChatMessage(
            role="system",
            content="Bạn là trợ lý đánh giá yêu cầu AI; chỉ dùng dữ liệu từ công cụ và nói rõ khi chưa đủ bằng chứng.",
        )
    ]
    messages.extend(ChatMessage.model_validate(item) for item in history or [])
    messages.append(ChatMessage(role="user", content=user))
    expected_calls: list[ExpectedToolCall] = []
    tool_steps = steps or []
    for index, step in enumerate(tool_steps):
        arguments = TOOL_ARG_MODELS[step["name"]].model_validate(step["arguments"]).model_dump()
        call = ToolCall(id=f"{case_id}-call-{index}", name=step["name"], arguments=arguments)
        expected_calls.append(ExpectedToolCall(name=step["name"], arguments=arguments))
        messages.append(ChatMessage(role="assistant", tool_calls=[call]))
        messages.append(
            ChatMessage(
                role="tool",
                tool_call_id=call.id,
                content=typed_result(step).model_dump_json(),
            )
        )
    messages.append(ChatMessage(role="assistant", content=final))
    case = EvaluationCase(
        case_id=case_id,
        messages=messages,
        tools=TOOL_DEFINITIONS if tool_steps else [],
        gold_labels=DatasetLabels(
            intent=intent,
            scenario_type=scenario_type,
            extracted_requirement=requirement or CustomerRequirement(),
            missing_fields=missing_fields or [],
            should_call_tool=bool(tool_steps),
            expected_tool=tool_steps[0]["name"] if tool_steps else None,
            expected_tool_calls=expected_calls,
            should_abstain=should_abstain,
            must_not_invent_product_fact=True,
            expected_behavior="abstain_if_evidence_missing" if should_abstain else None,
        ),
    )
    return BenchmarkRecord(case, family, persona, difficulty, template_id)


def _families() -> list[tuple[str, ScenarioType, Intent]]:
    return [
        ("eval_solution_design", ScenarioType.SOLUTION_COMPLETE, Intent.SOLUTION_DESIGN),
        ("eval_clarification", ScenarioType.MISSING_MULTIPLE_FIELDS, Intent.SOLUTION_DESIGN),
        ("eval_novice", ScenarioType.AMBIGUOUS_SOLUTION, Intent.SOLUTION_DESIGN),
        ("eval_product_search", ScenarioType.SEARCH_PRODUCT_BY_BUDGET, Intent.PRODUCT_SEARCH),
        ("eval_comparison", ScenarioType.COMPARE_PRODUCTS, Intent.PRODUCT_COMPARISON),
        ("eval_multi_tool", ScenarioType.TECHNICAL_MAX_RAM, Intent.TECHNICAL_QUESTION),
        ("eval_technical", ScenarioType.GENERAL_VRAM, Intent.GENERAL_AI_QUESTION),
        ("eval_lora", ScenarioType.GENERAL_LORA, Intent.GENERAL_AI_QUESTION),
        ("eval_requirement_change", ScenarioType.REQUIREMENT_CHANGED_MID_CONVERSATION, Intent.SOLUTION_DESIGN),
        ("eval_contradiction", ScenarioType.CONTRADICTORY_REQUIREMENT, Intent.SOLUTION_DESIGN),
        ("eval_failure", ScenarioType.TOOL_FAILURE, Intent.TECHNICAL_QUESTION),
        ("eval_out_of_scope", ScenarioType.OUT_SCOPE_NETWORK_SWITCH, Intent.OUT_OF_SCOPE),
    ]


def _record(index: int, family: str, scenario: ScenarioType, intent: Intent, persona: str, difficulty: str, seed: int) -> BenchmarkRecord:
    ordinal = seed % 31 + index * 3 + 11
    product_type = ProductType.AI_SERVER if index % 2 else ProductType.AI_WORKSTATION
    product = _product(ordinal, product_type)
    family_index = index % 10
    case_id = f"eval-{index:04d}"
    template_id = f"independent-{family}-{family_index:02d}"
    if family == "eval_solution_design":
        model = (7, 13, 20, 34, 70)[family_index % 5]
        users = 3 + (family_index * 2)
        usage = "fine_tune" if family_index % 4 == 0 else "inference"
        step = _estimate_step(model, usage, 4096 + family_index * 2048, users)
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, model=model, users=users, usage=usage, context=4096 + family_index * 2048, domain=('pháp chế' if family_index % 2 else 'chăm sóc khách hàng'), budget=180 + family_index * 17),
            final="Mình sẽ ước tính tài nguyên từ kích thước model, số người dùng và context trước; con số này cần benchmark thật rồi mới chốt máy.",
            requirement=CustomerRequirement(model_size_b=model, usage=usage, budget_vnd=180_000_000 + family_index * 17_000_000, concurrent_users=users, context_length=4096 + family_index * 2048),
            steps=[step],
        )
    if family == "eval_clarification":
        questions = (
            "Bên mình có một dự án AI cho kho tài liệu nội bộ, nhờ bạn tư vấn cấu hình.",
            "Công ty đang muốn dựng hệ thống trợ lý riêng nhưng chưa chốt model.",
            "Mình cần một máy để nhóm dùng AI trong nội bộ, bạn hỏi thêm giúp nhé.",
            "Phòng kinh doanh muốn có chatbot, còn thiếu vài thông tin về nhu cầu.",
            "Bên mình tính triển khai AI nhưng hiện mới biết là cần chạy tại chỗ.",
            "Nhóm pháp chế muốn hỏi tài liệu nội bộ, chưa rõ nên dùng model nào.",
            "Bên mình cần máy cho trợ lý bán hàng nhưng chưa chốt số người dùng.",
            "Phòng nghiên cứu muốn thử AI riêng, nhờ bạn hỏi các thông tin bắt buộc.",
            "Công ty muốn tra cứu quy trình bằng AI nhưng chưa có ngân sách dự kiến.",
            "Đội vận hành cần một phương án AI nội bộ, hiện còn thiếu yêu cầu kỹ thuật.",
        )
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent, user=questions[family_index % len(questions)],
            final="Mình cần thêm model dự kiến, cách dùng (inference hay fine-tune) và ngân sách tối đa trước khi tính cấu hình.",
            requirement=CustomerRequirement(), missing_fields=["model_size_b", "usage", "budget_vnd"],
        )
    if family == "eval_novice":
        domains = ("đào tạo nhân viên", "tìm kiếm quy trình", "soạn báo cáo", "hỗ trợ khách hàng", "tra cứu hồ sơ")
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, domain=domains[family_index % len(domains)], users=12 + family_index * 3),
            final="Mình sẽ làm rõ việc AI cần làm, model dự kiến, số người dùng và ngân sách; chưa nên chọn máy chỉ từ tên ứng dụng.",
            requirement=CustomerRequirement(), missing_fields=["model_size_b", "usage", "budget_vnd"],
        )
    if family == "eval_product_search":
        ceiling = product["base_price_vnd"] + 45_000_000
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, product_type=product_type.value.replace('_', ' '), ceiling=ceiling // 1_000_000),
            final=f"Mình đã tra danh mục; {product['id']} có giá máy cơ bản trong ngưỡng. Đây chưa phải tổng giá cấu hình đầy đủ.",
            steps=[_search_step(product, {"product_type": product_type.value, "max_base_price_vnd": ceiling})],
        )
    if family == "eval_comparison":
        other = _product(ordinal + 1, product_type)
        ids = [product["id"], other["id"]]
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, id_a=ids[0], id_b=ids[1]),
            final=f"Mình đã gọi công cụ so sánh cho {ids[0]} và {ids[1]}; quyết định cuối cùng cần đối chiếu thêm workload và giá hoàn chỉnh.",
            steps=[_comparison_step(ids)], should_abstain=True,
        )
    if family == "eval_multi_tool":
        steps = [
            _search_step(product, {"product_type": product_type.value, "min_ram_gb": product["max_ram_gb"] - 64}),
            {"name": "get_product", "arguments": {"product_id": product["id"]}, "ok": True, "data": product, "error": None},
            _document_step(product["id"], "max_ram_gb", product["max_ram_gb"]),
        ]
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, product_type=product_type.value.replace('_', ' '), min_ram=product['max_ram_gb'] - 64, product_id=product['id']),
            final=f"Sau ba bước kiểm tra, tài liệu ghi {product['id']} hỗ trợ tối đa {product['max_ram_gb']}GB RAM.", steps=steps,
        )
    if family == "eval_technical":
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, model=8 + family_index, context=16 + family_index * 2),
            final=(
                "Context dài làm KV cache của mỗi phiên lớn hơn. Khi nhiều request chạy đồng thời, "
                "các KV cache phải cùng tồn tại trong VRAM nên phần bộ nhớ còn lại giảm; "
                "mức tăng cụ thể còn phụ thuộc model, batch và cơ chế attention."
            ),
        )
    if family == "eval_lora":
        model = (8, 14, 32, 34, 72)[family_index % 5]
        step = _estimate_step(model, "fine_tune", 8192 + family_index * 1024, 2 + family_index)
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, model=model, context=8 + family_index),
            final="LoRA thường giảm phần tham số phải cập nhật, nhưng vẫn cần tính VRAM theo context, batch và cách chuẩn bị dữ liệu; hãy benchmark trước khi chốt.",
            requirement=CustomerRequirement(model_size_b=model, usage="fine_tune", budget_vnd=350_000_000 + family_index * 11_000_000, context_length=(8 + family_index) * 1024, training_method="LoRA"),
            steps=[step],
        )
    if family == "eval_requirement_change":
        new_model = 13 + family_index * 3
        history = [
            {"role": "user", "content": "Ban đầu mình định chạy model 7B cho nhóm nhỏ với ngân sách 160 triệu."},
            {"role": "assistant", "content": "Mình đã ghi nhận phương án ban đầu; nếu model hoặc cách dùng đổi thì cần tính lại."},
        ]
        step = _estimate_step(new_model, "inference", 8192, 6 + family_index)
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, model=new_model, users=6 + family_index, budget=260 + family_index * 13),
            final="Mình đã tính lại theo yêu cầu mới, không dùng thông số của phương án 7B trước đó; cần kiểm tra lại sản phẩm sau bước sizing.",
            requirement=CustomerRequirement(model_size_b=new_model, usage="inference", budget_vnd=(260 + family_index * 13) * 1_000_000, concurrent_users=6 + family_index, context_length=8192),
            steps=[step], history=history,
        )
    if family == "eval_contradiction":
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, model=48 + family_index, gpu=16 + family_index),
            final="Chưa thể khẳng định khả thi từ các ràng buộc này. Cần xác minh thêm precision, quantization và giới hạn phần cứng; mình không nên tự chọn một ràng buộc để bỏ qua.",
            requirement=CustomerRequirement(model_size_b=48 + family_index, usage="inference", context_length=65536),
            should_abstain=True,
        )
    if family == "eval_failure":
        product_id = product["id"]
        return _make_case(
            case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
            scenario_type=scenario, intent=intent,
            user=render_eval_prompt(family, family_index, product_id=product_id),
            final="Dịch vụ tài liệu đang lỗi nên mình chưa thể xác minh thông số. Mình giữ trường này ở trạng thái chưa biết thay vì đoán.",
            steps=[_failure_step(product_id)], should_abstain=True,
        )
    return _make_case(
        case_id=case_id, family=family, persona=persona, difficulty=difficulty, template_id=template_id,
        scenario_type=scenario, intent=intent,
        user=render_eval_prompt(family, family_index, desks=20 + family_index),
        final="Yêu cầu switch mạng nằm ngoài phạm vi tư vấn máy AI và cấu hình model của bộ dữ liệu này.",
        should_abstain=True,
    )


def build_independent_eval_records(seed: int = EVAL_SEED) -> list[BenchmarkRecord]:
    """Build 120 frozen benchmark records from benchmark-only recipes."""
    records: list[BenchmarkRecord] = []
    family_specs = _families()
    for index in range(EVAL_TARGET):
        family, scenario, intent = family_specs[index // 10]
        persona = PERSONAS[(index * 3 + seed) % len(PERSONAS)]
        record = _record(index, family, scenario, intent, persona, "medium", seed)
        labels = record.case.gold_labels
        difficulty = infer_difficulty(
            scenario_type=labels.scenario_type,
            tool_count=len(labels.expected_tool_calls),
            multi_turn=sum(message.role == "user" for message in record.case.messages) > 1,
            should_abstain=labels.should_abstain,
            tool_failure=family == "eval_failure",
            missing_field_count=len(labels.missing_fields),
        )
        records.append(replace(record, difficulty=difficulty))
    return records


def build_independent_eval_cases(seed: int = EVAL_SEED) -> list[EvaluationCase]:
    return [record.case for record in build_independent_eval_records(seed)]


def _current_user_text(example: FineTuneExample | EvaluationCase) -> str:
    text = next(
        (message.content or "" for message in reversed(example.messages) if message.role == "user"),
        "",
    )
    return " ".join(text.casefold().split())


def _example_from_item(item: Any) -> FineTuneExample | EvaluationCase:
    return item.example if hasattr(item, "example") else item


def audit_eval_isolation(
    cases: Iterable[EvaluationCase],
    training: Iterable[Any],
    *,
    threshold: float = 0.92,
) -> EvalIsolationReport:
    """Check exact and near overlap against training plus within the benchmark."""
    eval_cases = list(cases)
    train_texts = [_current_user_text(_example_from_item(item)) for item in training]
    eval_texts = [_current_user_text(case) for case in eval_cases]
    internal_exact = len(eval_texts) - len(set(eval_texts))
    internal_near_pairs, internal_near_ratio = near_duplicate_stats(eval_texts, threshold)
    exact = len(set(eval_texts) & set(train_texts))
    near_pairs = len(near_duplicate_pairs(eval_texts, threshold, train_texts))
    family_counts: dict[str, int] = {}
    persona_counts: dict[str, int] = {}
    difficulty_counts: dict[str, int] = {}
    tool_pattern_counts: dict[str, int] = {}
    for case in eval_cases:
        labels = case.gold_labels
        scenario = labels.scenario_type.value
        family_counts[scenario] = family_counts.get(scenario, 0) + 1
        tool_count = len(labels.expected_tool_calls)
        pattern = "no_tool" if tool_count == 0 else "single_tool" if tool_count == 1 else "multi_tool"
        tool_pattern_counts[pattern] = tool_pattern_counts.get(pattern, 0) + 1
    # Metadata is carried by records when building the manifest; these are kept
    # empty for the public case-only audit API.
    return EvalIsolationReport(
        exact_overlap=exact,
        near_duplicate_pairs=near_pairs,
        near_duplicate_rate=near_pairs / max(1, len(eval_cases) * max(1, len(train_texts))),
        scenario_counts=family_counts,
        persona_counts=persona_counts,
        difficulty_counts=difficulty_counts,
        tool_pattern_counts=tool_pattern_counts,
        internal_exact_user_duplicates=internal_exact,
        internal_near_user_pairs=internal_near_pairs,
        internal_near_user_example_ratio=internal_near_ratio,
    )


def benchmark_content_hash(records: Iterable[BenchmarkRecord]) -> str:
    payload = "\n".join(record.case.model_dump_json() for record in records).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
