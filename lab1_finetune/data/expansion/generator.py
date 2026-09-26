# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from lab1_finetune.data.expansion.difficulty import infer_difficulty
from lab1_finetune.data.expansion.personas import PersonaProfile, persona_for
from lab1_finetune.data.expansion.scenarios import (
    BUDGETS,
    CONCURRENCY,
    MODEL_SIZES,
    ScenarioContext,
    context_for,
    context_for_scenario,
)
from lab1_finetune.data.expansion.semantic_specs import (
    ComparisonSpec,
    ContradictionSpec,
    MultiToolFlow,
    MultiToolFlowSpec,
    RequirementChangeSpec,
    TechnicalFactSpec,
)
from lab1_finetune.data.expansion.spec import EXPANSION_FAMILY_SPECS, EXPANSION_SEED, FamilySpec
from lab1_finetune.data.expansion.wording import (
    comparison_prompt,
    contradictory_prompt,
    failure_prompt,
    history_recipe,
    lora_prompt,
    missing_prompt,
    multi_tool_prompt,
    no_product_found_prompt,
    novice_prompt,
    out_of_scope_prompt,
    product_type_label,
    requirement_change_prompt,
    search_by_budget_prompt,
    search_server_gpu_prompt,
    search_workstation_ram_prompt,
    solution_prompt,
    technical_prompt,
    tool_failure_prompt,
    variant_index,
)
from lab1_finetune.data.fixtures.tool_results import typed_result
from lab1_finetune.data.frozen_contracts import (
    TOOL_ARG_MODELS,
    TOOL_DEFINITIONS,
    ChatMessage,
    CustomerRequirement,
    ProductFilter,
    ProductType,
    ToolCall,
    UsageType,
)
from lab1_finetune.data.schema import (
    DatasetLabels,
    ExpectedToolCall,
    FineTuneExample,
    Intent,
    ScenarioType,
)

SYSTEM_MESSAGE = (
    "Bạn là trợ lý tư vấn AI Server và AI Workstation. Chỉ dùng dữ kiện từ công cụ; "
    "nếu thiếu thông tin hoặc bằng chứng thì nói rõ phần chưa biết."
)

@dataclass(frozen=True)
class BuiltExample:
    example: FineTuneExample
    semantic_template_id: str
    wording_recipe_id: str
    semantic_spec: RequirementChangeSpec | ContradictionSpec | None = None


@dataclass(frozen=True)
class GeneratedExample:
    example: FineTuneExample
    persona: str
    semantic_template_id: str
    wording_recipe_id: str
    family_id: str
    semantic_group_id: str
    semantic_spec: RequirementChangeSpec | ContradictionSpec | None = None


@dataclass(frozen=True)
class FailureCase:
    user: str
    final: str
    steps: list[dict[str, Any]]
    template_id: str
    recipe_id: str | None = None


def _product(ordinal: int, product_type: ProductType, *, ram: int = 512) -> dict[str, Any]:
    kind = "SRV" if product_type == ProductType.AI_SERVER else "WS"
    product_id = f"SYN-{kind}-{ordinal:05d}"
    return {
        "id": product_id,
        "sku": product_id,
        "name": f"Nền tảng AI {kind} {ordinal:05d}",
        "manufacturer": "SYNTHETIC-FIXTURE",
        "product_type": product_type.value,
        "max_ram_gb": ram,
        "max_gpu_slots": 8 if product_type == ProductType.AI_SERVER else 4,
        "max_storage_gb": 8192,
        "base_price_vnd": 70_000_000 + (ordinal % 9) * 15_000_000,
    }


def _estimate_result(
    context: ScenarioContext,
    *,
    include_storage_recommendation: bool = True,
) -> dict[str, Any]:
    multiplier = 4.5 if context.usage.value == "fine_tune" else 3.0
    memory = round(context.model_size_b * multiplier, 1)
    vram = max(24, int(((memory / 24) + 0.999) // 1) * 24)
    ram = max(64, int(context.model_size_b * 6 + context.concurrent_users * 8))
    return {
        "estimated_model_memory_gb": memory,
        "recommended_total_vram_gb": vram,
        "recommended_system_ram_gb": ram,
        "recommended_storage_gb": (
            context.storage_gb if include_storage_recommendation else None
        ),
        "assumptions": ["Ước tính deterministic; cần benchmark thực tế trước khi chốt."],
        "warnings": ["Chưa có giá cấu hình đầy đủ trong bước tính tài nguyên."],
        "confidence": 0.5,
    }


def _search_step(product: dict[str, Any] | None, filters: dict[str, Any] | ProductFilter) -> dict[str, Any]:
    filter_data = filters.model_dump(exclude_none=True) if isinstance(filters, ProductFilter) else filters
    products = [product] if product is not None else []
    return {
        "name": "search_products",
        "arguments": {"filters": filter_data, "limit": 5},
        "ok": True,
        "data": {"products": products, "total": len(products)},
        "error": None,
    }


def _estimate_step(
    context: ScenarioContext,
    *,
    include_storage_recommendation: bool = True,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "model_parameters_b": context.model_size_b,
        "usage": context.usage.value,
        "context_length": context.context_length,
        "concurrent_users": context.concurrent_users,
    }
    if context.usage.value == "fine_tune":
        arguments["training_method"] = "LoRA"
    return {
        "name": "estimate_ai_requirements",
        "arguments": arguments,
        "ok": True,
        "data": _estimate_result(
            context,
            include_storage_recommendation=include_storage_recommendation,
        ),
        "error": None,
    }


def _document_step(
    product_id: str,
    field_name: str,
    value: int | None,
    *,
    failure: bool = False,
) -> dict[str, Any]:
    arguments = {
        "query": {"max_ram_gb": "RAM tối đa", "max_gpu_slots": "số khe GPU tối đa"}[field_name],
        "product_id": product_id,
        "top_k": 3,
    }
    if failure:
        return {
            "name": "search_product_documents",
            "arguments": arguments,
            "ok": False,
            "data": None,
            "error": "document_service_unavailable",
        }
    source = f"https://fixture.invalid/{product_id}/{field_name}"
    hit = {
        "chunk": {
            "id": f"chunk-{product_id}-{field_name}",
            "text": f"{product_id}: {field_name} = {value}.",
            "source_url": source,
            "product_id": product_id,
            "page": 2,
            "metadata": {"field_name": field_name, "value": str(value), "verified": "true"},
        },
        "retrieval_score": 0.82,
        "rerank_score": 0.74,
        "rank": 1,
        "retrieval_method": "synthetic_fixture",
    }
    return {
        "name": "search_product_documents",
        "arguments": arguments,
        "ok": True,
        "data": {"hits": [hit], "total": 1},
        "error": None,
    }


def _empty_document_step(product_id: str, field_name: str) -> dict[str, Any]:
    query = {"max_ram_gb": "RAM tối đa", "max_gpu_slots": "số khe GPU tối đa"}[field_name]
    return {
        "name": "search_product_documents",
        "arguments": {
            "query": query,
            "product_id": product_id,
            "top_k": 3,
        },
        "ok": True,
        "data": {"hits": [], "total": 0},
        "error": None,
    }


def _history(
    context: ScenarioContext,
    index: int,
    *,
    unavailable_fields: frozenset[str] = frozenset(),
) -> list[dict[str, str]]:
    return history_recipe(
        context,
        index,
        unavailable_fields=unavailable_fields,
    )


def _make_example(
    *,
    example_id: str,
    family: FamilySpec,
    scenario_type: Any,
    intent: Intent | None = None,
    difficulty: str | None = None,
    persona: PersonaProfile,
    user: str,
    final: str,
    context: CustomerRequirement,
    missing_fields: list[str],
    should_abstain: bool,
    steps: list[dict[str, Any]] | None = None,
    history: list[dict[str, str]] | None = None,
    template_id: str,
    recipe_id: str | None = None,
    semantic_spec: RequirementChangeSpec | ContradictionSpec | None = None,
) -> BuiltExample:
    tool_steps = steps or []
    inferred_difficulty = infer_difficulty(
        scenario_type=scenario_type,
        tool_count=len(tool_steps),
        multi_turn=bool(history),
        should_abstain=should_abstain,
        tool_failure=any(step.get("ok") is False for step in tool_steps),
        missing_field_count=len(missing_fields),
    )
    messages = [ChatMessage(role="system", content=SYSTEM_MESSAGE)]
    messages.extend(ChatMessage.model_validate(item) for item in history or [])
    messages.append(ChatMessage(role="user", content=user))
    expected_calls: list[ExpectedToolCall] = []
    for index, step in enumerate(tool_steps):
        name = step["name"]
        arguments = TOOL_ARG_MODELS[name].model_validate(step["arguments"]).model_dump()
        call = ToolCall(id=f"{example_id}-call-{index}", name=name, arguments=arguments)
        expected_calls.append(ExpectedToolCall(name=name, arguments=arguments))
        messages.append(ChatMessage(role="assistant", tool_calls=[call]))
        messages.append(
            ChatMessage(
                role="tool",
                tool_call_id=call.id,
                content=typed_result(step).model_dump_json(),
            )
        )
    messages.append(ChatMessage(role="assistant", content=final))
    example = FineTuneExample(
        example_id=example_id,
        scenario_family_id=family.family_id,
        scenario_summary=family.summary,
        task_type="tool_calling" if tool_steps else "conversation",
        difficulty=inferred_difficulty,
        language="vi",
        source_type="synthetic_expansion_unreviewed",
        messages=messages,
        tools=TOOL_DEFINITIONS if tool_steps else [],
        labels=DatasetLabels(
            intent=intent or family.intent,
            scenario_type=scenario_type,
            extracted_requirement=context,
            missing_fields=missing_fields,
            should_call_tool=bool(tool_steps),
            expected_tool=tool_steps[0]["name"] if tool_steps else None,
            expected_tool_calls=expected_calls,
            should_abstain=should_abstain,
            must_not_invent_product_fact=True,
            expected_behavior="abstain_if_evidence_missing" if should_abstain else None,
        ),
    )
    return BuiltExample(
        example=example,
        semantic_template_id=template_id,
        wording_recipe_id=recipe_id or template_id,
        semantic_spec=semantic_spec,
    )


def should_be_multi_turn(
    family_id: str,
    scenario_type: ScenarioType,
    seed: int,
    index: int,
) -> bool:
    """Select multi-turn cases from scenario semantics and a stable hash."""
    if scenario_type == ScenarioType.REQUIREMENT_CHANGED_MID_CONVERSATION:
        return True
    probabilities = {
        "expanded_solution_design": 0.24,
        "expanded_missing_information": 0.34,
        "expanded_novice_users": 0.30,
        "expanded_product_search": 0.18,
        "expanded_comparison": 0.36,
        "expanded_multi_tool": 0.42,
        "expanded_technical_questions": 0.12,
        "expanded_lora_inference": 0.24,
        "expanded_contradictory": 0.28,
        "expanded_failure_abstention": 0.22,
        "expanded_out_of_scope": 0.05,
    }
    threshold = int(probabilities.get(family_id, 0.2) * 100)
    return variant_index(seed, family_id, index, 100) < threshold


def _build_solution(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    wording_variant = variant_index(ordinal, family.family_id, index, 12)
    prompt = solution_prompt(profile, context, wording_variant)
    estimate = _estimate_step(context)
    estimate_data = estimate["data"]
    final = (
        f"Ước tính ban đầu cần khoảng {estimate_data['recommended_total_vram_gb']}GB VRAM "
        f"và {estimate_data['recommended_system_ram_gb']}GB RAM. Đây là ước tính sơ bộ, "
        "cần benchmark thực tế trước khi chốt cấu hình và giá."
    )
    abstain = scenario_type == ScenarioType.LARGE_MODEL_LOW_BUDGET
    if abstain:
        final = (
            f"Với {context.model_name}, ngân sách khoảng {context.budget_vnd // 1_000_000} triệu "
            f"và {context.concurrent_users} người dùng, tài nguyên sơ bộ là "
            f"{estimate_data['recommended_total_vram_gb']}GB VRAM và "
            f"{estimate_data['recommended_system_ram_gb']}GB RAM; mình chưa có đủ bằng chứng "
            "về giá cấu hình hoàn chỉnh để chốt máy.",
            f"Yêu cầu {context.model_name} cho {context.domain} cần khoảng "
            f"{estimate_data['recommended_total_vram_gb']}GB VRAM, trong khi ngân sách "
            f"mới ở mức {context.budget_vnd // 1_000_000} triệu. Mình giữ kết luận ở mức "
            "ước tính và cần kiểm tra giá thực tế trước khi đề xuất.",
            f"Bài toán {context.domain} với {context.model_name}, context "
            f"{context.context_length} token và {context.concurrent_users} người dùng "
            f"chưa thể chốt trong {context.budget_vnd // 1_000_000} triệu; bước tiếp theo "
            "là xác minh sản phẩm và giá cấu hình đầy đủ.",
        )[wording_variant % 3]
        estimate = _estimate_step(context)
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=final,
        context=CustomerRequirement(
            model_size_b=context.model_size_b,
            usage=context.usage,
            budget_vnd=context.budget_vnd,
            concurrent_users=context.concurrent_users,
            context_length=context.context_length,
            storage_requirement_gb=context.storage_gb,
        ),
        missing_fields=[],
        should_abstain=abstain,
        steps=[estimate] if estimate else [],
        history=_history(context, index) if multi_turn else None,
        template_id=(
            "solution_low_budget_abstain_v3"
            if abstain
            else "solution_finetune_complete_v3"
            if context.usage.value == "fine_tune"
            else "solution_inference_complete_v3"
        ),
        recipe_id=prompt.recipe_id,
    )


def _build_missing(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    missing_by_type = {
        "missing_budget": ["budget_vnd"],
        "missing_usage": ["usage"],
        "missing_model_size": ["model_size_b"],
        "missing_multiple_fields": ["model_size_b", "usage", "budget_vnd"],
    }
    missing = missing_by_type[scenario_type.value]
    prompt = missing_prompt(
        profile,
        context,
        missing,
        variant_index(ordinal, family.family_id, index, 10),
    )
    history = (
        _history(context, index, unavailable_fields=frozenset(missing))
        if multi_turn
        else None
    )
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=(
            f"Bạn cho mình biết mức ngân sách tối đa cho {context.model_name} phục vụ "
            f"{context.domain} nhé."
            if scenario_type == ScenarioType.MISSING_BUDGET
            else f"Với {context.model_name} cho {context.domain}, hệ thống chỉ chạy model "
            "để sử dụng hay còn cần huấn luyện, tinh chỉnh nữa?"
            if scenario_type == ScenarioType.MISSING_USAGE
            else f"Bạn dự kiến chạy model cỡ bao nhiêu tỷ tham số cho bài toán {context.domain}?"
            if scenario_type == ScenarioType.MISSING_MODEL_SIZE
            else f"Với mục tiêu {context.domain} cho {context.concurrent_users} người, mình cần "
            "thêm model dự kiến, cách sử dụng và mức ngân sách tối đa."
        ),
        context=CustomerRequirement(
            model_size_b=None if "model_size_b" in missing else context.model_size_b,
            usage=None if "usage" in missing else context.usage,
            budget_vnd=None if "budget_vnd" in missing else context.budget_vnd,
        ),
        missing_fields=missing,
        should_abstain=False,
        history=history,
        template_id={
            ScenarioType.MISSING_BUDGET: "clarify_missing_budget_v3",
            ScenarioType.MISSING_USAGE: "clarify_missing_usage_v3",
            ScenarioType.MISSING_MODEL_SIZE: "clarify_missing_model_size_v3",
            ScenarioType.MISSING_MULTIPLE_FIELDS: "clarify_missing_multiple_fields_v3",
        }[scenario_type],
        recipe_id=prompt.recipe_id,
    )


def _build_novice(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    wording_variant = variant_index(ordinal, family.family_id, index, 10)
    prompt = novice_prompt(profile, context, wording_variant)
    finals = (
        "Mình sẽ bắt đầu từ mục tiêu sử dụng, model dự kiến và ngân sách; có ba thông tin này rồi mới nên tính cấu hình.",
        "Trước mắt mình cần làm rõ bài toán và số người dùng, chưa cần quyết định GPU ngay.",
        "Mình sẽ hỏi từng phần bằng ngôn ngữ dễ hiểu rồi mới chuyển thành yêu cầu kỹ thuật.",
        "Khi có mục tiêu, model và ngân sách, mình mới có thể so sánh máy một cách công bằng.",
        "Bạn chưa cần biết hết thông số; chỉ cần mô tả cách dùng và giới hạn chi phí trước.",
    )
    missing_fields = ["model_size_b", "usage", "budget_vnd"]
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=finals[wording_variant % len(finals)],
        context=CustomerRequirement(),
        missing_fields=missing_fields,
        should_abstain=False,
        history=(
            _history(context, index, unavailable_fields=frozenset(missing_fields))
            if multi_turn
            else None
        ),
        template_id=(
            "novice_ambiguous_solution_v3"
            if scenario_type == ScenarioType.AMBIGUOUS_SOLUTION
            else "novice_missing_multiple_fields_v3"
        ),
        recipe_id=prompt.recipe_id,
    )


def _build_search(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    product = _product(ordinal, context.product_type, ram=256 + (ordinal % 5) * 256)
    wording_variant = variant_index(ordinal, family.family_id, index, 5)
    if scenario_type == ScenarioType.SEARCH_PRODUCT_BY_BUDGET:
        ceiling = product["base_price_vnd"] + 30_000_000
        filters = ProductFilter(product_type=context.product_type, max_base_price_vnd=ceiling)
        prompt = search_by_budget_prompt(profile, context, wording_variant, filters)
        final = (
            f"{product['id']} là {product_type_label(filters.product_type)} có giá máy cơ bản "
            f"{product['base_price_vnd'] // 1_000_000} triệu, không quá trần {ceiling // 1_000_000} triệu. "
            "Mức này chưa bao gồm đầy đủ GPU, RAM và lưu trữ của cấu hình cuối."
        )
        template_id = "search_base_price_v3"
    elif scenario_type == ScenarioType.SEARCH_WORKSTATION_BY_RAM:
        filters = ProductFilter(product_type=ProductType.AI_WORKSTATION, min_ram_gb=product["max_ram_gb"] - 128)
        prompt = search_workstation_ram_prompt(profile, context, wording_variant, filters)
        final = (
            f"Danh mục trả về {product['id']} thuộc nhóm {product_type_label(filters.product_type)}, "
            f"hỗ trợ tối đa {product['max_ram_gb']}GB RAM, đáp ứng mức tối thiểu {filters.min_ram_gb}GB RAM."
        )
        template_id = "search_workstation_ram_v3"
    else:
        filters = ProductFilter(product_type=ProductType.AI_SERVER, min_gpu_count=4 + ordinal % 5)
        prompt = search_server_gpu_prompt(profile, context, wording_variant, filters)
        final = (
            f"Danh mục trả về {product['id']} thuộc nhóm {product_type_label(filters.product_type)}, "
            f"hỗ trợ tối đa {product['max_gpu_slots']} khe GPU, đáp ứng mức tối thiểu {filters.min_gpu_count} khe GPU."
        )
        template_id = "search_server_gpu_slots_v3"
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=final,
        context=CustomerRequirement(),
        missing_fields=[],
        should_abstain=False,
        steps=[_search_step(product, filters)],
        history=_history(context, index) if multi_turn else None,
        template_id=template_id,
        recipe_id=prompt.recipe_id,
    )


def _build_comparison(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    first = _product(ordinal * 2, context.product_type)
    second = _product(ordinal * 2 + 1, context.product_type)
    if scenario_type == ScenarioType.COMPARE_PRODUCTS:
        comparison = ComparisonSpec(
            target_type="product",
            target_ids=(first["id"], second["id"]),
        )
        ids = list(comparison.target_ids)
        step = {
            "name": "compare_products",
            "arguments": {"product_ids": ids},
            "ok": True,
            "data": {
                "product_ids": ids,
                "dimensions": ["max_ram_gb", "max_gpu_slots", "base_price_vnd"],
                "summary": "Cần đối chiếu thêm dữ liệu triển khai thực tế trước khi chốt.",
            },
            "error": None,
        }
        final = (
            f"Mình đã đối chiếu sản phẩm {ids[0]} và {ids[1]}; "
            "cần xác minh thêm dữ liệu trước khi chốt."
        )
        template_id = "compare_products_v3"
    else:
        comparison = ComparisonSpec(
            target_type="configuration",
            target_ids=(f"cfg-{ordinal}-a", f"cfg-{ordinal}-b"),
        )
        ids = list(comparison.target_ids)
        step = {
            "name": "compare_configurations",
            "arguments": {"configuration_ids": ids},
            "ok": True,
            "data": {
                "product_ids": [first["id"]],
                "configuration_ids": ids,
                "configurations": [
                    {
                        "configuration_id": ids[0],
                        "product_id": first["id"],
                        "gpu_model": "SYN GPU 48",
                        "gpu_count": 2,
                        "total_vram_gb": 96,
                        "configured_ram_gb": 256,
                        "price_status": "unknown",
                        "unknown_facts": ["complete_price"],
                    },
                    {
                        "configuration_id": ids[1],
                        "product_id": first["id"],
                        "gpu_model": "SYN GPU 96",
                        "gpu_count": 1,
                        "total_vram_gb": 96,
                        "configured_ram_gb": 256,
                        "price_status": "unknown",
                        "unknown_facts": ["complete_price"],
                    },
                ],
                "summary": "Hai cấu hình cùng đạt 96GB VRAM nhưng chưa rõ giá hoàn chỉnh.",
            },
            "error": None,
        }
        final = f"Hai cấu hình {ids[0]} và {ids[1]} cần thêm dữ liệu giá trước khi kết luận."
        template_id = "compare_saved_configs_v3"
    wording_variant = variant_index(ordinal, family.family_id, index, 5)
    prompt = comparison_prompt(profile, context, wording_variant, comparison)
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=final,
        context=CustomerRequirement(),
        missing_fields=[],
        should_abstain=True,
        steps=[step],
        history=_history(context, index) if multi_turn else None,
        template_id=template_id,
        recipe_id=prompt.recipe_id,
    )


def _multi_tool_steps(
    context: ScenarioContext,
    spec: MultiToolFlowSpec,
    product: dict[str, Any],
    estimate_step: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if spec.flow == MultiToolFlow.ESTIMATE_THEN_SEARCH:
        if estimate_step is None or spec.filters is None:
            raise ValueError("Estimate-then-search requires estimate output and search filters")
        return [estimate_step, _search_step(product, spec.filters)]
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET:
        if spec.filters is None:
            raise ValueError("Search-then-get requires a product filter")
        return [
            _search_step(product, spec.filters),
            {
                "name": "get_product",
                "arguments": {"product_id": product["id"]},
                "ok": True,
                "data": product,
                "error": None,
            },
        ]
    if spec.document_field is None:
        raise ValueError("Get-then-document requires a document field")
    value = product[spec.document_field]
    return [
        {
            "name": "get_product",
            "arguments": {"product_id": spec.product_id},
            "ok": True,
            "data": product,
            "error": None,
        },
        _document_step(spec.product_id, spec.document_field, value),
    ]


def _build_multi_tool(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    flows = tuple(MultiToolFlow)
    flow = flows[variant_index(ordinal, family.family_id, index, len(flows))]
    scenario_type = {
        MultiToolFlow.ESTIMATE_THEN_SEARCH: ScenarioType.SOLUTION_COMPLETE,
        MultiToolFlow.SEARCH_THEN_GET: ScenarioType.SEARCH_WORKSTATION_BY_RAM,
        MultiToolFlow.GET_THEN_DOCUMENT: ScenarioType.TECHNICAL_MAX_RAM,
    }[flow]
    intent = {
        MultiToolFlow.ESTIMATE_THEN_SEARCH: Intent.SOLUTION_DESIGN,
        MultiToolFlow.SEARCH_THEN_GET: Intent.PRODUCT_SEARCH,
        MultiToolFlow.GET_THEN_DOCUMENT: Intent.TECHNICAL_QUESTION,
    }[flow]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    estimate_step = (
        _estimate_step(
            context,
            include_storage_recommendation=False,
        )
        if flow == MultiToolFlow.ESTIMATE_THEN_SEARCH
        else None
    )

    if flow == MultiToolFlow.ESTIMATE_THEN_SEARCH:
        recommended_ram = estimate_step["data"]["recommended_system_ram_gb"]
        product = _product(ordinal, context.product_type, ram=max(512, recommended_ram))
        product["base_price_vnd"] = min(product["base_price_vnd"], context.budget_vnd)
        filters = ProductFilter(
            product_type=context.product_type,
            min_ram_gb=recommended_ram,
            max_base_price_vnd=context.budget_vnd,
        )
        document_field = None
    elif flow == MultiToolFlow.SEARCH_THEN_GET:
        product = _product(ordinal, context.product_type, ram=512 + ordinal % 4 * 256)
        filters = ProductFilter(
            product_type=context.product_type,
            min_ram_gb=product["max_ram_gb"] - 128,
        )
        document_field = None
    else:
        product = _product(ordinal, context.product_type, ram=512 + ordinal % 4 * 256)
        filters = None
        document_field = "max_ram_gb"

    flow_spec = MultiToolFlowSpec(
        flow=flow,
        product_id=product["id"],
        product_type=context.product_type,
        filters=filters,
        document_field=document_field,
    )
    steps = _multi_tool_steps(context, flow_spec, product, estimate_step)
    prompt_variant = variant_index(ordinal, family.family_id, index, 4)
    prompt = multi_tool_prompt(profile, context, prompt_variant, flow_spec)

    if flow == MultiToolFlow.ESTIMATE_THEN_SEARCH:
        estimate = steps[0]["data"]
        listed_price = f"{product['base_price_vnd']:,}".replace(",", ".")
        budget = f"{context.budget_vnd:,}".replace(",", ".")
        final = (
            f"Ước tính ban đầu đề xuất {estimate['recommended_system_ram_gb']}GB RAM hệ thống. "
            f"Danh mục trả về {product['id']}, hỗ trợ tối đa {product['max_ram_gb']}GB RAM; "
            f"giá máy cơ bản {listed_price} VND nằm trong ngân sách tối đa "
            f"{budget} VND; đây chưa phải giá cấu hình hoàn chỉnh."
        )
    elif flow == MultiToolFlow.SEARCH_THEN_GET:
        final = (
            f"Danh mục tìm được {product['id']} thuộc nhóm {product_type_label(flow_spec.product_type)}. "
            f"Máy hỗ trợ tối đa {product['max_ram_gb']}GB RAM, đáp ứng mức tối thiểu {filters.min_ram_gb}GB; "
            "giá hoàn chỉnh cần được xác minh riêng."
        )
    else:
        final = (
            f"Tài liệu của {product['id']} xác nhận RAM tối đa là {product['max_ram_gb']}GB; "
            "đây là thông số tài liệu, không phải cấu hình RAM đang lắp."
        )

    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        intent=intent,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=final,
        context=CustomerRequirement(
            model_size_b=context.model_size_b,
            usage=context.usage,
            budget_vnd=context.budget_vnd,
            concurrent_users=context.concurrent_users,
            context_length=(
                context.context_length
                if flow == MultiToolFlow.ESTIMATE_THEN_SEARCH
                else None
            ),
        ),
        missing_fields=[],
        should_abstain=False,
        steps=steps,
        history=_history(context, index) if multi_turn else None,
        template_id=f"{flow.value}_v3",
        recipe_id=prompt.recipe_id,
    )


def _build_technical(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    wording_variant = variant_index(ordinal, family.family_id, index, 4)
    steps: list[dict[str, Any]] = []

    if scenario_type == ScenarioType.GENERAL_VRAM:
        prompt = technical_prompt(profile, context, wording_variant, scenario_type)
        if prompt.recipe_id == "context_effect":
            final = (
                "Context dài hơn làm KV cache của từng yêu cầu lớn hơn, nên nhu cầu VRAM tăng dù kích thước model không đổi."
            )
        elif prompt.recipe_id == "kv_cache_reasoning":
            final = (
                "Context dài hơn làm KV cache của mỗi phiên lớn hơn; nhiều phiên đang chạy đồng thời "
                "cần giữ các KV cache riêng, nên tổng VRAM tăng theo tải thực tế."
            )
        elif prompt.recipe_id == "memory_growth":
            final = (
                "VRAM gồm bộ nhớ cho trọng số model và KV cache của các phiên đang hoạt động. "
                "Thêm phiên đồng thời làm tổng KV cache tăng; trọng số model không nhân lên theo số người dùng."
            )
        elif prompt.recipe_id == "concurrency_context":
            final = (
                "Với context dài, KV cache mỗi phiên chiếm nhiều VRAM hơn. "
                "Nhiều phiên chạy đồng thời phải giữ các cache đó cùng lúc, nên tổng VRAM cần thiết tăng; "
                "mức cụ thể còn phụ thuộc lịch phục vụ và tải thực tế."
            )
        else:
            raise ValueError(f"Unknown general VRAM recipe: {prompt.recipe_id}")
        template_id = "general_vram_context_v3"
    elif scenario_type == ScenarioType.GENERAL_INFERENCE:
        prompt = technical_prompt(profile, context, wording_variant, scenario_type)
        final = (
            "Inference là lúc dùng model đã huấn luyện để tạo câu trả lời mà không cập nhật trọng số.",
            "Inference là giai đoạn chạy model đã huấn luyện để sinh kết quả; trọng số không được cập nhật trong bước này.",
            "Inference là lúc model phục vụ yêu cầu đầu vào, khác với huấn luyện hoặc tinh chỉnh làm thay đổi tham số.",
        )[variant_index(ordinal, family.family_id, index, 3)]
        template_id = "general_inference_definition_v3"
    else:
        product = _product(ordinal, context.product_type)
        field_name = (
            "max_ram_gb"
            if scenario_type == ScenarioType.TECHNICAL_MAX_RAM
            else "max_gpu_slots"
        )
        fact = TechnicalFactSpec(product_id=product["id"], field_name=field_name)
        prompt = technical_prompt(
            profile,
            context,
            wording_variant,
            scenario_type,
            fact=fact,
        )
        if scenario_type == ScenarioType.UNKNOWN_PRODUCT_SPEC:
            final = (
                f"Tài liệu hiện có chưa cung cấp bằng chứng xác nhận số khe GPU tối đa "
                f"của {fact.product_id}, nên mình chưa thể kết luận thông số này."
            )
            steps = [_empty_document_step(fact.product_id, fact.field_name)]
            template_id = "technical_unknown_evidence_v3"
        else:
            value = product[field_name]
            steps = [_document_step(fact.product_id, fact.field_name, value)]
            if field_name == "max_ram_gb":
                final = f"Tài liệu của {fact.product_id} ghi hỗ trợ tối đa {value}GB RAM."
                template_id = "technical_ram_document_v3"
            else:
                final = f"Tài liệu của {fact.product_id} ghi tối đa {value} khe GPU."
                template_id = "technical_gpu_document_v3"

    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=final,
        context=CustomerRequirement(),
        missing_fields=[],
        should_abstain=scenario_type == ScenarioType.UNKNOWN_PRODUCT_SPEC,
        steps=steps,
        history=_history(context, index) if multi_turn else None,
        template_id=template_id,
        recipe_id=prompt.recipe_id,
    )


def _build_lora(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    if scenario_type == ScenarioType.SOLUTION_COMPLETE:
        context = replace(context, usage=UsageType.FINE_TUNE)
    wording_variant = variant_index(ordinal, family.family_id, index, 5)
    prompt = lora_prompt(profile, context, wording_variant, scenario_type)
    if scenario_type == ScenarioType.GENERAL_LORA:
        final = (
            "LoRA chỉ huấn luyện thêm các ma trận adapter nhỏ nên thường tiết kiệm VRAM hơn, nhưng vẫn cần benchmark theo dữ liệu và batch size.",
            "LoRA giữ phần lớn model gốc và học adapter nhỏ; cách này thường nhẹ hơn full fine-tune nhưng vẫn phải đo bằng tải sử dụng thật.",
            "Với LoRA, chi phí bộ nhớ thường dễ kiểm soát hơn vì không cập nhật toàn bộ trọng số. Kết quả cuối vẫn cần kiểm tra theo batch và dữ liệu thực tế.",
        )[wording_variant % 3]
        steps = []
        template_id = "lora_explanation_v3"
    else:
        estimate = _estimate_step(context)
        result = estimate["data"]
        final = f"Ước tính cần khoảng {result['recommended_total_vram_gb']}GB VRAM và {result['recommended_system_ram_gb']}GB RAM; cần benchmark với batch size thực tế."
        steps = [estimate]
        template_id = "lora_resource_estimate_v3"
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=final,
        context=CustomerRequirement(
            model_size_b=context.model_size_b,
            usage=context.usage,
            concurrent_users=context.concurrent_users if steps else None,
            context_length=context.context_length if steps else None,
            storage_requirement_gb=context.storage_gb if steps else None,
            training_method="LoRA",
        ),
        missing_fields=[],
        should_abstain=False,
        steps=steps,
        history=_history(context, index) if multi_turn else None,
        template_id=template_id,
        recipe_id=prompt.recipe_id,
    )


def _build_requirement_change(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    wording_variant = variant_index(ordinal, family.family_id, index, 3)
    old = context_for(ordinal)
    change_kind = index % 4
    if change_kind in {0, 3}:
        next_size = MODEL_SIZES[(MODEL_SIZES.index(old.model_size_b) + 1) % len(MODEL_SIZES)]
        model_family = old.model_name.rsplit(" ", 1)[0]
        new = replace(old, model_size_b=next_size, model_name=f"{model_family} {int(next_size)}B")
    else:
        new = old
    if change_kind == 1:
        new_usage = UsageType.FINE_TUNE if old.usage == UsageType.INFERENCE else UsageType.INFERENCE
        new = replace(new, usage=new_usage)
    if change_kind == 2:
        next_budget = BUDGETS[(BUDGETS.index(old.budget_vnd) + 1) % len(BUDGETS)]
        new = replace(new, budget_vnd=next_budget)
    if change_kind == 3:
        next_users = CONCURRENCY[(CONCURRENCY.index(old.concurrent_users) + 1) % len(CONCURRENCY)]
        new = replace(new, concurrent_users=next_users)
    change = RequirementChangeSpec(old=old, new=new)
    prompt = requirement_change_prompt(profile, change, wording_variant)
    estimate = _estimate_step(change.new)
    result = estimate["data"]
    steps = [estimate]
    final = f"Mình đã tính theo yêu cầu mới: khoảng {result['recommended_total_vram_gb']}GB VRAM và {result['recommended_system_ram_gb']}GB RAM. Không dùng lại thông số của kế hoạch cũ."
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=ScenarioType.REQUIREMENT_CHANGED_MID_CONVERSATION,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=final,
        context=CustomerRequirement(
            model_size_b=change.new.model_size_b,
            usage=change.new.usage,
            budget_vnd=change.new.budget_vnd,
            concurrent_users=change.new.concurrent_users,
            context_length=change.new.context_length,
            training_method="LoRA" if change.new.usage == UsageType.FINE_TUNE else None,
        ),
        missing_fields=[],
        should_abstain=False,
        steps=steps,
        history=[
            {"role": "user", "content": (
                f"Lúc đầu định chạy {old.model_name} cho {old.domain}, "
                f"chỉ inference cho {old.concurrent_users} người, "
                f"ngân sách khoảng {old.budget_vnd // 1_000_000} triệu, "
                f"context {old.context_length} token."
            )},
            {"role": "assistant", "content": "Mình đã ghi nhận phương án ban đầu; nếu thay đổi model hoặc cách dùng thì mình sẽ tính lại."},
        ],
        template_id=change.template_id,
        recipe_id=prompt.recipe_id,
        semantic_spec=change,
    )


def _build_contradictory(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    subtype = (
        "single_gpu_vs_large_model",
        "context_vram_constraint",
        "large_model_low_budget",
    )[index % 3]
    scenario_type = (
        ScenarioType.LARGE_MODEL_LOW_BUDGET
        if subtype == "large_model_low_budget"
        else ScenarioType.CONTRADICTORY_REQUIREMENT
    )
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    if subtype != "large_model_low_budget":
        size = 70.0 if subtype == "single_gpu_vs_large_model" else 32.0
        context = replace(
            context,
            model_size_b=size,
            model_name=f"{context.model_name.rsplit(' ', 1)[0]} {int(size)}B",
            context_length=32768 if subtype == "context_vram_constraint" else context.context_length,
        )
    gpu_memory = 16 if subtype == "single_gpu_vs_large_model" else 24 if subtype == "context_vram_constraint" else None
    conflict = ContradictionSpec(subtype=subtype, context=context, gpu_memory_gb=gpu_memory)
    contradiction_variant = variant_index(ordinal, family.family_id, index, 3)
    prompt = contradictory_prompt(profile, conflict, contradiction_variant)
    if subtype == "large_model_low_budget":
        estimate = _estimate_step(context)
        estimate_data = estimate["data"]
        steps = [estimate]
        final = (
            f"{context.model_name} cần ước tính {estimate_data['recommended_total_vram_gb']}GB VRAM, "
            f"nhưng giới hạn toàn bộ cấu hình là {context.budget_vnd // 1_000_000} triệu. "
            "Chưa có giá cấu hình đầy đủ để chứng minh đáp ứng ngân sách; cần kiểm tra báo giá trước khi chốt."
        )
    else:
        steps = []
        final = (
            f"Giới hạn đúng một GPU {gpu_memory}GB xung đột với yêu cầu {context.model_name} "
            f"ở full precision{' và context ' + str(context.context_length) + ' token' if subtype == 'context_vram_constraint' else ''}. "
            "Không thể cam kết chạy được trên cấu hình này; cần nới ràng buộc hoặc benchmark theo phương án khác."
        )
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=prompt.text,
        final=final,
        context=CustomerRequirement(
            model_size_b=context.model_size_b,
            usage=context.usage,
            budget_vnd=context.budget_vnd if subtype == "large_model_low_budget" else None,
            concurrent_users=context.concurrent_users if subtype == "large_model_low_budget" else None,
            context_length=context.context_length if subtype != "single_gpu_vs_large_model" else None,
        ),
        missing_fields=[],
        should_abstain=True,
        steps=steps,
        history=_history(context, index) if multi_turn else None,
        template_id={
            "single_gpu_vs_large_model": "contradiction_single_gpu_v3",
            "context_vram_constraint": "contradiction_context_vram_v3",
            "large_model_low_budget": "contradiction_low_budget_v3",
        }[subtype],
        recipe_id=prompt.recipe_id,
        semantic_spec=conflict,
    )


def _tool_failure_case(
    family: FamilySpec, index: int, ordinal: int, profile: PersonaProfile,
    context: ScenarioContext,
) -> FailureCase:
    product_id = _product(ordinal, context.product_type)["id"]
    prompt = tool_failure_prompt(profile, product_id, index // len(family.scenario_types))
    final = (
        f"Dịch vụ đọc tài liệu của {product_id} đang lỗi nên mình chưa thể xác nhận thông số. Mình sẽ không tự điền giá trị thay thế.",
        f"Hiện dịch vụ tài liệu không phản hồi cho {product_id}, vì vậy thông số vẫn chưa được kiểm chứng; mình không đoán giá trị còn thiếu.",
        f"Không lấy được bằng chứng từ dịch vụ tài liệu của {product_id} lúc này. Mình giữ trường kỹ thuật ở trạng thái chưa biết.",
    )[variant_index(ordinal, family.family_id, index, 3)]
    return FailureCase(
        user=prompt.text,
        final=final,
        steps=[_document_step(product_id, "max_ram_gb", None, failure=True)],
        template_id="tool_failure_document_v3",
        recipe_id=prompt.recipe_id,
    )


def _no_product_found_case(
    index: int, profile: PersonaProfile, context: ScenarioContext,
) -> FailureCase:
    filters = ProductFilter(product_type=context.product_type, min_ram_gb=4096, min_gpu_count=16)
    prompt = no_product_found_prompt(profile, context, index, filters)
    product_type = product_type_label(filters.product_type)
    return FailureCase(
        user=prompt.text,
        final=(
            f"Danh mục hiện không trả về {product_type} đáp ứng đồng thời "
            f"{filters.min_ram_gb}GB RAM và {filters.min_gpu_count} khe GPU; "
            "mình chưa thể đề xuất mã máy khác."
        ),
        steps=[_search_step(None, filters)],
        template_id="no_product_found_v3",
        recipe_id=prompt.recipe_id,
    )


def _unknown_product_case(
    family: FamilySpec, index: int, ordinal: int, profile: PersonaProfile,
    context: ScenarioContext,
) -> FailureCase:
    product_id = _product(ordinal, context.product_type)["id"]
    final = (
        f"Tài liệu của {product_id} chưa có bằng chứng cho thông số đang hỏi nên mình giữ trường này ở trạng thái chưa biết.",
        f"Chưa tìm thấy tài liệu xác nhận thông số của {product_id}; mình không thể kết luận thay cho bằng chứng nguồn.",
        f"Dữ liệu hiện có chưa xác minh được thông số của {product_id}, nên kết quả phải để UNKNOWN thay vì suy đoán.",
    )[variant_index(ordinal, family.family_id, index, 3)]
    return FailureCase(
        user=failure_prompt(
            profile, context, index, ScenarioType.UNKNOWN_PRODUCT_SPEC.value, product_id
        ),
        final=final,
        steps=[_empty_document_step(product_id, "max_gpu_slots")],
        template_id="unknown_product_evidence_v3",
    )


def _build_failure(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    if scenario_type == ScenarioType.TOOL_FAILURE:
        case = _tool_failure_case(family, index, ordinal, profile, context)
    elif scenario_type == ScenarioType.NO_PRODUCT_FOUND:
        case = _no_product_found_case(index, profile, context)
    elif scenario_type == ScenarioType.UNKNOWN_PRODUCT_SPEC:
        case = _unknown_product_case(family, index, ordinal, profile, context)
    else:
        raise ValueError(f"Unsupported failure scenario: {scenario_type}")
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=case.user,
        final=case.final,
        context=CustomerRequirement(),
        missing_fields=[],
        should_abstain=True,
        steps=case.steps,
        history=_history(context, index) if multi_turn else None,
        template_id=case.template_id,
        recipe_id=case.recipe_id,
    )


def _build_out_of_scope(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    difficulty: str,
    *,
    multi_turn: bool,
) -> BuiltExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    context = context_for_scenario(
        seed=ordinal, index=index, scenario_type=scenario_type, persona_id=profile.persona_id
    )
    if scenario_type == ScenarioType.OUT_SCOPE_LAPTOP:
        final = (
            "Mình chỉ hỗ trợ tư vấn AI Server, AI Workstation và cấu hình phục vụ model; laptop gaming nằm ngoài phạm vi hiện tại.",
            "Nội dung laptop gaming không thuộc bộ tư vấn máy AI hiện tại; mình chỉ có thể hỗ trợ workstation, server và tải chạy model.",
            "Mình chưa có phạm vi dữ liệu cho laptop gaming. Phần đang hỗ trợ là nền tảng AI và cấu hình phục vụ model.",
        )[variant_index(ordinal, family.family_id, index, 3)]
    else:
        final = (
            "Yêu cầu switch mạng không thuộc phạm vi tư vấn máy AI và cấu hình model của bộ dữ liệu này.",
            "Bài toán switch mạng nằm ngoài phạm vi dữ liệu về server, workstation và model AI mà mình đang tư vấn.",
            "Mình không thể xử lý yêu cầu thiết kế switch trong bộ công cụ máy AI hiện tại; cần một nguồn chuyên về mạng.",
        )[variant_index(ordinal, family.family_id, index, 3)]
    user = out_of_scope_prompt(profile, context, index, scenario_type.value)
    return _make_example(
        example_id=f"exp-{family.family_id}-{index:04d}",
        family=family,
        scenario_type=scenario_type,
        difficulty=difficulty,
        persona=profile,
        user=user,
        final=final,
        context=CustomerRequirement(),
        missing_fields=[],
        should_abstain=True,
        history=_history(context, index) if multi_turn else None,
        template_id=(
            "out_scope_laptop_v3"
            if scenario_type == ScenarioType.OUT_SCOPE_LAPTOP
            else "out_scope_network_v3"
        ),
    )


def _build_one(
    family: FamilySpec,
    index: int,
    ordinal: int,
    profile: PersonaProfile,
    seed: int,
) -> GeneratedExample:
    scenario_type = family.scenario_types[index % len(family.scenario_types)]
    multi_turn = should_be_multi_turn(family.family_id, scenario_type, seed, index)
    builders = {
        "expanded_solution_design": _build_solution,
        "expanded_missing_information": _build_missing,
        "expanded_novice_users": _build_novice,
        "expanded_product_search": _build_search,
        "expanded_comparison": _build_comparison,
        "expanded_multi_tool": _build_multi_tool,
        "expanded_technical_questions": _build_technical,
        "expanded_lora_inference": _build_lora,
        "expanded_requirement_change": _build_requirement_change,
        "expanded_contradictory": _build_contradictory,
        "expanded_failure_abstention": _build_failure,
        "expanded_out_of_scope": _build_out_of_scope,
    }
    built = builders[family.family_id](
        family, index, ordinal, profile, "medium", multi_turn=multi_turn
    )
    template_id = built.semantic_template_id
    return GeneratedExample(
        example=built.example,
        persona=profile.persona_id,
        semantic_template_id=template_id,
        wording_recipe_id=built.wording_recipe_id,
        family_id=family.family_id,
        semantic_group_id=f"{template_id}:recipe_{built.wording_recipe_id}",
        semantic_spec=built.semantic_spec,
    )


def build_expanded_examples(seed: int = EXPANSION_SEED) -> list[GeneratedExample]:
    """Build expansion rows without reading or mutating the 60-example gold seed."""
    offset = seed % 997
    examples: list[GeneratedExample] = []
    seen_user_prompts: set[str] = set()
    ordinal = 0
    for family in EXPANSION_FAMILY_SPECS:
        for index in range(family.quota):
            profile = persona_for(ordinal + offset)
            attempt = 0
            while True:
                candidate_ordinal = ordinal + offset + attempt * 997
                built = _build_one(family, index, candidate_ordinal, profile, seed)
                prompt_key = next(
                    (
                        (message.content or "").casefold()
                        for message in reversed(built.example.messages)
                        if message.role == "user"
                    ),
                    "",
                )
                if prompt_key not in seen_user_prompts:
                    seen_user_prompts.add(prompt_key)
                    break
                attempt += 1
                if attempt > 32:
                    raise ValueError(
                        f"Unable to produce a unique recipe/context combination for {built.example.example_id}"
                    )
            examples.append(built)
            ordinal += 1
    return examples
