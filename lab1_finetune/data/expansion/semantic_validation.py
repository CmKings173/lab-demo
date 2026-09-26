"""Semantic quality gates for locally generated Lab 1 examples."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from lab1_finetune.data.expansion.semantic_specs import ContradictionSpec, RequirementChangeSpec
from lab1_finetune.data.schema import Intent, ScenarioType

_MODEL_REFERENCE = re.compile(
    r"\b(?:qwen(?:\s+coder)?|llama(?:\s+coder)?|mistral|yi)\s+"
    r"\d+(?:[.,]\d+)?\s*b\b|\b\d+(?:[.,]\d+)?\s*b\b",
    re.IGNORECASE,
)
_BUDGET_REFERENCE = re.compile(
    r"\b\d[\d.,]*\s*(?:triệu|trieu|million|m(?:\s*vnd)?|vnd|đồng|dong)\b",
    re.IGNORECASE,
)
_USAGE_DECISIONS = (
    re.compile(
        r"\b(?:vừa|đã)\s+(?:chọn|chốt)\s+(?:hướng\s+)?(?:chạy|dùng|sử dụng)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:chốt|chọn|quyết định|dự kiến|dự định)\s+"
        r"(?:fine[- ]?tune|lora|inference|huấn luyện|tinh chỉnh)\b",
        re.IGNORECASE,
    ),
)


def _prior_conversation_text(example: Any) -> str:
    user_positions = [
        index for index, message in enumerate(example.messages) if message.role == "user"
    ]
    if len(user_positions) < 2:
        return ""
    current_user = user_positions[-1]
    return " ".join(
        message.content or ""
        for message in example.messages[:current_user]
        if message.role == "user"
    )


def _tool_records(example: Any) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    calls: dict[str, tuple[str, dict[str, Any]]] = {}
    for message in example.messages:
        for call in message.tool_calls:
            calls[call.id] = (call.name, call.arguments)
    records: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for message in example.messages:
        if message.role != "tool" or not message.tool_call_id:
            continue
        name, arguments = calls.get(message.tool_call_id, ("", {}))
        try:
            result = json.loads(message.content or "{}")
        except json.JSONDecodeError:
            result = {}
        records.append((name, arguments, result))
    return records


def _current_user_text(example: Any) -> str:
    return next(
        (message.content or "" for message in reversed(example.messages) if message.role == "user"),
        "",
    )


def _user_conversation_text(example: Any) -> str:
    """Only user-authored turns can establish provenance for user requirements."""
    return " ".join(
        message.content or "" for message in example.messages if message.role == "user"
    )


def _final_text(example: Any) -> str:
    return next(
        (
            message.content or ""
            for message in reversed(example.messages)
            if message.role == "assistant" and message.content
        ),
        "",
    )


def _labels_for(example: Any) -> Any:
    """Return labels for either generated training rows or frozen eval cases."""
    return getattr(example, "labels", getattr(example, "gold_labels", None))


def _example_id(example: Any) -> str:
    return str(getattr(example, "example_id", getattr(example, "case_id", "unknown")))


def _validate_comparison(
    example: Any,
    scenario: str,
    records: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> list[str]:
    if scenario not in {
        ScenarioType.COMPARE_PRODUCTS.value,
        ScenarioType.COMPARE_CONFIGURATIONS.value,
    }:
        return []
    example_id = _example_id(example)
    is_product = scenario == ScenarioType.COMPARE_PRODUCTS.value
    tool_name = "compare_products" if is_product else "compare_configurations"
    id_key = "product_ids" if is_product else "configuration_ids"
    record = next((entry for entry in records if entry[0] == tool_name), None)
    errors: list[str] = []
    if record is None:
        return [f"{example_id}:comparison scenario has no matching comparison tool"]
    arguments, result = record[1], record[2]
    target_ids = arguments.get(id_key, [])
    result_ids = (result.get("data") or {}).get(id_key, []) if result.get("ok") else []
    user = _current_user_text(example).casefold()
    user_provenance = _user_conversation_text(example).casefold()
    final = _final_text(example).casefold()
    if len(target_ids) != 2 or result_ids != target_ids:
        errors.append(f"{example_id}:comparison tool/result target IDs disagree")
    if any(str(target_id).casefold() not in user_provenance for target_id in target_ids):
        errors.append(f"{example_id}:comparison user targets disagree with tool arguments")
    if any(str(target_id).casefold() not in final for target_id in target_ids):
        errors.append(f"{example_id}:comparison final omits a compared target")
    # Frozen evaluation prompts have an independent wording contract; only enforce
    # the generated-dataset renderer vocabulary rules on generated examples.
    if not hasattr(example, "labels"):
        return errors
    if is_product and ("sản phẩm" not in user or "cấu hình" in user):
        errors.append(f"{example_id}:comparison wording does not describe product targets")
    if not is_product and ("cấu hình" not in user or "hai máy" in user):
        errors.append(f"{example_id}:comparison wording does not describe configuration targets")
    return errors


def _validate_multi_tool(
    example: Any,
    template_id: str,
    records: list[tuple[str, dict[str, Any], dict[str, Any]]],
    call_names: list[str],
) -> list[str]:
    labels = _labels_for(example)
    expected_scenarios = {
        "estimate_then_search_v3": ScenarioType.SOLUTION_COMPLETE,
        "search_then_get_v3": ScenarioType.SEARCH_WORKSTATION_BY_RAM,
        "get_then_document_v3": ScenarioType.TECHNICAL_MAX_RAM,
    }
    expected_intents = {
        "estimate_then_search_v3": Intent.SOLUTION_DESIGN,
        "search_then_get_v3": Intent.PRODUCT_SEARCH,
        "get_then_document_v3": Intent.TECHNICAL_QUESTION,
    }
    if template_id not in expected_scenarios:
        return []
    example_id = _example_id(example)
    expected = {
        "estimate_then_search_v3": ["estimate_ai_requirements", "search_products"],
        "search_then_get_v3": ["search_products", "get_product"],
        "get_then_document_v3": ["get_product", "search_product_documents"],
    }
    errors: list[str] = []
    if labels is None or labels.scenario_type != expected_scenarios[template_id]:
        errors.append(f"{example_id}:multi-tool semantic template has the wrong intent label")
    elif labels.intent != expected_intents[template_id]:
        errors.append(f"{example_id}:multi-tool semantic template has the wrong intent category")
    if template_id not in expected or call_names != expected.get(template_id):
        errors.append(f"{example_id}:multi-tool template and tool-call flow disagree")
        return errors
    user = _current_user_text(example).casefold()
    record_by_name = {name: (arguments, result) for name, arguments, result in records}

    if template_id == "estimate_then_search_v3":
        if not all(term in user for term in ("ước tính", "tìm", "ram")):
            errors.append(f"{example_id}:multi-tool wording does not describe estimate then search")
        estimate_arguments, estimate_result = record_by_name.get(
            "estimate_ai_requirements", ({}, {})
        )
        requirement = labels.extracted_requirement if labels is not None else None
        estimate = records[0][2].get("data") or {}
        search_arguments, search_result = record_by_name.get("search_products", ({}, {}))
        filters = search_arguments.get("filters", {})
        recommended_ram = estimate.get("recommended_system_ram_gb")
        user_provided_text = _user_conversation_text(example).casefold()
        if requirement is None:
            errors.append(f"{example_id}:multi-tool estimate has no structured requirement labels")
        else:
            for field in ("context_length", "concurrent_users", "model_size_b", "usage"):
                expected_value = getattr(requirement, field)
                argument_name = (
                    "model_parameters_b" if field == "model_size_b" else field
                )
                if (
                    expected_value is None
                    or estimate_arguments.get(argument_name) != expected_value
                ):
                    errors.append(
                        f"{example_id}:multi-tool estimate {field} "
                        "disagrees with requirement labels"
                    )
            context_value = requirement.context_length
            context_pattern = (
                rf"\b(?:context|ngữ cảnh)(?:\s+(?:length|dài))?"
                rf"\s*(?::|là)?\s*{context_value}\s+tokens?\b"
            )
            if context_value is None or not re.search(context_pattern, user_provided_text):
                errors.append(
                    f"{example_id}:multi-tool context length is absent or differs "
                    "across user/labels/tool"
                )
            concurrency_value = requirement.concurrent_users
            if concurrency_value is None or not re.search(
                rf"\b{concurrency_value}\s+(?:người dùng đồng thời|concurrent users?)\b",
                user_provided_text,
            ):
                errors.append(
                    f"{example_id}:multi-tool concurrency is absent or differs "
                    "across user/labels/tool"
                )
            if requirement.model_size_b is not None and (
                f"{int(requirement.model_size_b)}b" not in user_provided_text
            ):
                errors.append(f"{example_id}:multi-tool model size is not visible in the request")
            expected_usage_phrase = (
                "chạy inference"
                if requirement.usage is not None and requirement.usage.value == "inference"
                else "fine-tune bằng lora"
            )
            if (
                requirement.usage is not None
                and expected_usage_phrase not in user_provided_text
            ):
                errors.append(f"{example_id}:multi-tool usage is not visible in the request")
            if (
                requirement.budget_vnd is None
                or filters.get("max_base_price_vnd") != requirement.budget_vnd
            ):
                errors.append(
                    f"{example_id}:multi-tool price ceiling "
                    "disagrees with requirement labels"
                )
            elif f"{requirement.budget_vnd:,}".replace(",", ".") not in user_provided_text:
                errors.append(
                    f"{example_id}:multi-tool budget is not visible exactly in the request"
                )
        if (
            recommended_ram is None
            or filters.get("min_ram_gb") != recommended_ram
        ):
            errors.append(f"{example_id}:multi-tool search RAM filter is not derived from estimate")
        elif re.search(
            rf"(?:ít nhất|tối thiểu)\s*{recommended_ram}\s*gb\s*ram|"
            rf"ram\s+(?:ít nhất|tối thiểu)\s*{recommended_ram}\b",
            user_provided_text,
            re.IGNORECASE,
        ):
            errors.append(
                f"{example_id}:estimate-derived RAM recommendation leaks into the user request"
            )
        products = (search_result.get("data") or {}).get("products", [])
        if not products or any(
            product.get("max_ram_gb") is None
            or product["max_ram_gb"] < (recommended_ram or 0)
            or product.get("base_price_vnd") is None
            or product["base_price_vnd"] > filters.get("max_base_price_vnd", 0)
            for product in products
        ):
            errors.append(
                f"{example_id}:multi-tool estimate result is not satisfied by catalog result"
            )
        if estimate_result.get("recommended_storage_gb") is not None:
            errors.append(
                f"{example_id}:multi-tool estimate invents an unrequested storage target"
            )
    elif template_id == "search_then_get_v3":
        if "tìm" not in user or not any(term in user for term in ("chi tiết", "thông tin")):
            errors.append(f"{example_id}:multi-tool wording does not describe search then get")
        search_result = record_by_name.get("search_products", ({}, {}))[1]
        search_arguments = record_by_name.get("search_products", ({}, {}))[0]
        get_arguments, get_result = record_by_name.get("get_product", ({}, {}))
        filters = search_arguments.get("filters", {})
        requested_ram = filters.get("min_ram_gb")
        products = (search_result.get("data") or {}).get("products", [])
        result_id = products[0].get("id") if products else None
        product_ram = products[0].get("max_ram_gb") if products else None
        if (
            requested_ram is None
            or str(requested_ram) not in user
            or "ram" not in user
            or str(requested_ram) not in _final_text(example)
            or product_ram is None
            or product_ram < requested_ram
            or str(product_ram) not in _final_text(example)
        ):
            errors.append(
                f"{example_id}:search RAM constraint missing or contradictory in wording/final"
            )
        if (
            result_id is None
            or get_arguments.get("product_id") != result_id
            or (get_result.get("data") or {}).get("id") != result_id
        ):
            errors.append(f"{example_id}:multi-tool get target is not sourced from search result")
    else:
        get_arguments, get_result = record_by_name.get("get_product", ({}, {}))
        document_arguments, document_result = record_by_name.get(
            "search_product_documents", ({}, {})
        )
        product_id = get_arguments.get("product_id")
        user_provenance = _user_conversation_text(example).casefold()
        if (
            not product_id
            or str(product_id).casefold() not in user_provenance
            or "tài liệu" not in user
            or (get_result.get("data") or {}).get("id") != product_id
            or document_arguments.get("product_id") != product_id
            or "ram" not in document_arguments.get("query", "").casefold()
        ):
            errors.append(f"{example_id}:multi-tool wording/get/document targets disagree")
        hits = (document_result.get("data") or {}).get("hits", [])
        if not hits or any(
            hit.get("chunk", {}).get("product_id") != product_id
            or hit.get("chunk", {}).get("metadata", {}).get("field_name") != "max_ram_gb"
            for hit in hits
        ):
            errors.append(
                f"{example_id}:multi-tool document evidence does not match requested product field"
            )
        if product_id and str(product_id).casefold() not in _final_text(example).casefold():
            errors.append(f"{example_id}:multi-tool final omits document product ID")
    return errors


def _explains_context_memory_growth(final: str) -> bool:
    if "vram không đổi" in final or "vram không tăng" in final:
        return False
    vram_pressure = re.search(
        r"\bvram(?:\s+\w+){0,3}\s+tăng\b|chiếm nhiều vram hơn|bộ nhớ còn lại giảm",
        final,
    )
    return bool(vram_pressure) and bool(
        re.search(
            r"(?:context|ngữ cảnh)[^.]{0,120}kv cache[^.]{0,80}"
            r"(?:lớn hơn|tăng|chiếm nhiều vram hơn)",
            final,
        )
        or re.search(
            r"kv cache[^.]{0,80}(?:tăng|lớn hơn)[^.]{0,80}(?:context|ngữ cảnh)",
            final,
        )
    )


def _explains_concurrent_memory_growth(final: str) -> bool:
    if "vram không đổi" in final or "vram không tăng" in final:
        return False
    has_multiple_sessions = re.search(
        r"\b(?:nhiều|thêm|các|số)\s+(?:phiên|request|yêu cầu|người dùng)\b",
        final,
    )
    total_growth = re.search(
        r"\btổng\s+(?:nhu cầu\s+)?(?:kv cache|vram|bộ nhớ)"
        r"(?:\s+\w+){0,3}\s+tăng\b",
        final,
    )
    return bool(
        "kv cache" in final
        and has_multiple_sessions
        and (total_growth or "bộ nhớ còn lại giảm" in final)
    )


def _validate_technical(
    example: Any,
    scenario: str,
    records: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> list[str]:
    example_id = _example_id(example)
    user = _current_user_text(example).casefold()
    user_provenance = _user_conversation_text(example).casefold()
    final = _final_text(example).casefold()
    errors: list[str] = []
    if scenario == ScenarioType.GENERAL_VRAM.value:
        if "inference" in user or not any(
            term in user for term in ("vram", "context", "kv cache", "bộ nhớ")
        ):
            errors.append(f"{example_id}:general_vram wording asks another technical concept")
        if not any(term in final for term in ("vram", "kv cache", "bộ nhớ")):
            errors.append(f"{example_id}:general_vram final does not answer memory question")
        if any(term in user for term in ("context", "ngữ cảnh")) and not (
            _explains_context_memory_growth(final)
        ):
            errors.append(f"{example_id}:general_vram final omits context/KV-cache growth")
        if any(term in user for term in ("đồng thời", "cùng lúc", "số phiên")) and not (
            _explains_concurrent_memory_growth(final)
        ):
            errors.append(f"{example_id}:general_vram final omits concurrent-session memory impact")
    elif scenario == ScenarioType.GENERAL_INFERENCE.value:
        if "inference" not in user or any(term in user for term in ("vram", "kv cache", "context")):
            errors.append(f"{example_id}:general_inference wording asks another technical concept")
        if "inference" not in final:
            errors.append(f"{example_id}:general_inference final does not explain inference")

    fact_fields = {
        ScenarioType.TECHNICAL_MAX_RAM.value: "max_ram_gb",
        ScenarioType.TECHNICAL_MAX_GPU.value: "max_gpu_slots",
        ScenarioType.UNKNOWN_PRODUCT_SPEC.value: "max_gpu_slots",
    }
    if scenario not in fact_fields:
        return errors
    field_name = fact_fields[scenario]
    record = next((entry for entry in records if entry[0] == "search_product_documents"), None)
    if record is None:
        return errors + [f"{example_id}:technical product fact has no document lookup"]
    arguments, result = record[1], record[2]
    product_id = arguments.get("product_id")
    field_term = "ram" if field_name == "max_ram_gb" else "khe gpu"
    if (
        not product_id
        or str(product_id).casefold() not in user_provenance
        or str(product_id).casefold() not in final
    ):
        errors.append(f"{example_id}:technical product ID differs across user/tool/final")
    final_field_is_required = (
        scenario != ScenarioType.UNKNOWN_PRODUCT_SPEC.value
        or getattr(example, "scenario_family_id", None) == "expanded_technical_questions"
    )
    if (
        field_term not in user
        or field_term not in arguments.get("query", "").casefold()
        or (final_field_is_required and field_term not in final)
    ):
        errors.append(f"{example_id}:technical requested field differs across user/tool/final")
    hits = (result.get("data") or {}).get("hits", []) if result.get("ok") else []
    if scenario == ScenarioType.UNKNOWN_PRODUCT_SPEC.value:
        labels = _labels_for(example)
        if hits or labels is None or not labels.should_abstain:
            errors.append(f"{example_id}:unknown product fact must have no evidence and abstain")
    elif not hits or any(
        hit.get("chunk", {}).get("product_id") != product_id
        or hit.get("chunk", {}).get("metadata", {}).get("field_name") != field_name
        for hit in hits
    ):
        errors.append(
            f"{example_id}:technical document evidence does not match requested product field"
        )
    return errors


def _validate_requirement_change(
    item: Any,
    example: Any,
    template_id: str,
    records: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> list[str]:
    if getattr(item, "family_id", "") != "expanded_requirement_change":
        return []
    example_id = _example_id(example)
    spec = getattr(item, "semantic_spec", None)
    if not isinstance(spec, RequirementChangeSpec):
        return [f"{example_id}:requirement change is missing its source delta"]
    errors = []
    if template_id != spec.template_id:
        errors.append(f"{example_id}:requirement change template disagrees with actual delta")
    labels = _labels_for(example)
    new = spec.new
    req = labels.extracted_requirement
    if (
        req.model_size_b != new.model_size_b
        or req.usage != new.usage
        or req.budget_vnd != new.budget_vnd
        or req.concurrent_users != new.concurrent_users
        or req.context_length != new.context_length
        or req.training_method != ("LoRA" if new.usage.value == "fine_tune" else None)
    ):
        errors.append(f"{example_id}:requirement change labels do not describe new requirement")
    estimate = next((args for name, args, _ in records if name == "estimate_ai_requirements"), None)
    if estimate is None or (
        estimate.get("model_parameters_b") != new.model_size_b
        or estimate.get("usage") != new.usage.value
        or estimate.get("concurrent_users") != new.concurrent_users
        or estimate.get("training_method") != ("LoRA" if new.usage.value == "fine_tune" else None)
    ):
        errors.append(f"{example_id}:requirement change estimator does not use new requirement")
    user_provenance = _user_conversation_text(example).casefold()
    old = spec.old
    history = _prior_conversation_text(example).casefold()
    if (
        old.model_name.casefold() not in history
        or str(old.budget_vnd // 1_000_000) not in history
        or str(old.concurrent_users) not in history
    ):
        errors.append(f"{example_id}:requirement change prior state is not visible")
    if "model_size_b" in spec.changed_fields and (
        old.model_name.casefold() not in user_provenance
        or new.model_name.casefold() not in user_provenance
    ):
        errors.append(f"{example_id}:requirement change model delta is not visible")
    if "usage" in spec.changed_fields and not all(
        term in user_provenance for term in ("inference", "fine-tune", "lora")
    ):
        errors.append(f"{example_id}:requirement change usage delta is not visible")
    if "budget_vnd" in spec.changed_fields and not all(
        str(value // 1_000_000) in user_provenance
        for value in (old.budget_vnd, new.budget_vnd)
    ):
        errors.append(f"{example_id}:requirement change budget delta is not visible")
    if "concurrent_users" in spec.changed_fields and not all(
        str(value) in user_provenance
        for value in (old.concurrent_users, new.concurrent_users)
    ):
        errors.append(f"{example_id}:requirement change user-count delta is not visible")
    if "yêu cầu mới" not in _final_text(example).casefold():
        errors.append(f"{example_id}:requirement change final does not identify new requirement")
    return errors


def _validate_contradiction(
    item: Any,
    example: Any,
    template_id: str,
    records: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> list[str]:
    if getattr(item, "family_id", "") != "expanded_contradictory":
        return []
    example_id = _example_id(example)
    spec = getattr(item, "semantic_spec", None)
    if not isinstance(spec, ContradictionSpec):
        return [f"{example_id}:contradiction is missing its constraint spec"]
    templates = {
        "single_gpu_vs_large_model": "contradiction_single_gpu_v3",
        "context_vram_constraint": "contradiction_context_vram_v3",
        "large_model_low_budget": "contradiction_low_budget_v3",
    }
    errors = []
    labels = _labels_for(example)
    req = labels.extracted_requirement
    user = _current_user_text(example).casefold()
    user_provenance = _user_conversation_text(example).casefold()
    final = _final_text(example).casefold()
    if template_id != templates[spec.subtype] or not labels.should_abstain:
        errors.append(f"{example_id}:contradiction template/abstention disagrees with constraint")
    expected_budget = spec.context.budget_vnd if spec.subtype == "large_model_low_budget" else None
    if req.model_size_b != spec.context.model_size_b or req.budget_vnd != expected_budget:
        errors.append(f"{example_id}:contradiction labels disagree with constraint")
    if spec.subtype == "large_model_low_budget":
        if (
            req.model_size_b is None or req.model_size_b < 32
            or req.budget_vnd is None or req.budget_vnd > 240_000_000
            or str(req.budget_vnd // 1_000_000) not in user_provenance
            or "toàn bộ cấu hình" not in user
            or "giá" not in final
        ):
            errors.append(f"{example_id}:contradiction low-budget tension is not supported")
        estimate = next(
            (args for name, args, _ in records if name == "estimate_ai_requirements"),
            None,
        )
        if estimate is None or (
            estimate.get("model_parameters_b") != spec.context.model_size_b
            or estimate.get("usage") != spec.context.usage.value
            or estimate.get("concurrent_users") != spec.context.concurrent_users
            or estimate.get("context_length") != spec.context.context_length
        ):
            errors.append(f"{example_id}:contradiction estimate does not match low-budget request")
    elif (
        spec.gpu_memory_gb is None
        or spec.context.model_size_b * 2 <= spec.gpu_memory_gb
        or str(spec.gpu_memory_gb) not in user_provenance
        or str(int(spec.context.model_size_b)) not in user_provenance
        or "một gpu" not in user
        or "gpu" not in final
    ):
        errors.append(f"{example_id}:contradiction GPU constraint is absent or not conflicting")
    if spec.subtype != "large_model_low_budget" and records:
        errors.append(f"{example_id}:contradiction GPU case unexpectedly calls a tool")
    if spec.subtype == "context_vram_constraint" and (
        spec.context.context_length < 32768
        or str(spec.context.context_length) not in user_provenance
        or req.context_length != spec.context.context_length
    ):
        errors.append(f"{example_id}:contradiction context constraint is absent")
    return errors


def _validate_lora_family(
    item: Any,
    example: Any,
    records: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> list[str]:
    if getattr(item, "family_id", "") != "expanded_lora_inference":
        return []
    example_id = _example_id(example)
    labels = _labels_for(example)
    req = labels.extracted_requirement
    user_provenance = _user_conversation_text(example).casefold()
    final = _final_text(example).casefold()
    errors = []
    if (
        "lora" not in user_provenance
        or req.usage != "fine_tune"
        or req.training_method != "LoRA"
    ):
        errors.append(f"{example_id}:LoRA user/labels do not describe fine-tune")
    if labels.scenario_type == ScenarioType.GENERAL_LORA:
        if records or labels.should_call_tool or "lora" not in final:
            errors.append(f"{example_id}:LoRA concept case has tool call or wrong final")
    else:
        estimate = next(
            (args for name, args, _ in records if name == "estimate_ai_requirements"),
            None,
        )
        if estimate is None or (
            estimate.get("usage") != "fine_tune"
            or estimate.get("training_method") != "LoRA"
            or estimate.get("model_parameters_b") != req.model_size_b
            or estimate.get("concurrent_users") != req.concurrent_users
            or estimate.get("context_length") != req.context_length
        ):
            errors.append(f"{example_id}:LoRA estimate args disagree with labels")
        if (
            req.model_size_b is None
            or f"{int(req.model_size_b)}b" not in user_provenance
        ):
            errors.append(f"{example_id}:LoRA model is not visible in request")
        if labels.scenario_type == ScenarioType.FINETUNE_32B_SOLUTION and (
            req.model_size_b is None or req.model_size_b < 32
        ):
            errors.append(f"{example_id}:LoRA 32B scenario requires model >= 32B")
    return errors


def validate_generated_semantics(items: Sequence[Any]) -> list[str]:
    """Return actionable errors when visible labels and tool data disagree."""
    errors: list[str] = []
    for item in items:
        example = getattr(item, "example", item)
        template_id = getattr(item, "semantic_template_id", "")
        example_id = getattr(example, "example_id", getattr(example, "case_id", "unknown"))
        labels = getattr(example, "labels", getattr(example, "gold_labels", None))
        if labels is None:
            errors.append(f"{example_id}:missing dataset labels")
            continue
        scenario = labels.scenario_type.value
        records = _tool_records(example)
        call_names = [
            call.name for message in example.messages for call in message.tool_calls
        ]
        errors.extend(_validate_comparison(example, scenario, records))
        errors.extend(_validate_multi_tool(example, template_id, records, call_names))
        errors.extend(_validate_technical(example, scenario, records))
        errors.extend(_validate_requirement_change(item, example, template_id, records))
        errors.extend(_validate_contradiction(item, example, template_id, records))
        errors.extend(_validate_lora_family(item, example, records))
        by_name = {name: (arguments, result) for name, arguments, result in records}
        requirement = labels.extracted_requirement
        missing_fields = set(labels.missing_fields)
        prior_text = _prior_conversation_text(example)
        if "model_size_b" in missing_fields and _MODEL_REFERENCE.search(prior_text):
            errors.append(f"{example_id}:history reveals model_size_b marked missing")
        if "budget_vnd" in missing_fields and _BUDGET_REFERENCE.search(prior_text):
            errors.append(f"{example_id}:history reveals budget_vnd marked missing")
        if "usage" in missing_fields and any(
            pattern.search(prior_text) for pattern in _USAGE_DECISIONS
        ):
            errors.append(f"{example_id}:history reveals usage marked missing")

        if scenario == "large_model_low_budget":
            if requirement.model_size_b is None or requirement.model_size_b < 32:
                errors.append(f"{example_id}:large_model_low_budget requires model >= 32B")
            if requirement.budget_vnd is None or requirement.budget_vnd > 240_000_000:
                errors.append(f"{example_id}:large_model_low_budget requires budget <= 240M")

        if scenario == "finetune_32b_solution":
            if requirement.model_size_b is None or requirement.model_size_b < 32:
                errors.append(f"{example_id}:finetune_32b_solution requires model >= 32B")
            if requirement.usage != "fine_tune" or requirement.training_method != "LoRA":
                errors.append(f"{example_id}:fine-tune contract is incomplete")

        if "search_products" in by_name:
            arguments, result = by_name["search_products"]
            filters = arguments.get("filters", {})
            products = (result.get("data") or {}).get("products", []) if result.get("ok") else []
            if result.get("ok"):
                for product in products:
                    product_type = product.get("product_type")
                    if filters.get("product_type") and product_type != filters["product_type"]:
                        errors.append(f"{example_id}:product_type filter/result mismatch")
                    if filters.get("min_ram_gb") is not None and (
                        product.get("max_ram_gb") is None
                        or product["max_ram_gb"] < filters["min_ram_gb"]
                    ):
                        errors.append(f"{example_id}:RAM filter/result mismatch")
                    if filters.get("min_gpu_count") is not None and (
                        product.get("max_gpu_slots") is None
                        or product["max_gpu_slots"] < filters["min_gpu_count"]
                    ):
                        errors.append(f"{example_id}:GPU filter/result mismatch")
                    if filters.get("max_base_price_vnd") is not None and (
                        product.get("base_price_vnd") is None
                        or product["base_price_vnd"] > filters["max_base_price_vnd"]
                    ):
                        errors.append(f"{example_id}:price filter/result mismatch")
                    product_id = str(product.get("id", ""))
                    if product_id.startswith("SYN-WS-") and product_type != "ai_workstation":
                        errors.append(f"{example_id}:SYN-WS product has wrong type")
                    if product_id.startswith("SYN-SRV-") and product_type != "ai_server":
                        errors.append(f"{example_id}:SYN-SRV product has wrong type")

        if scenario == "search_workstation_by_ram":
            arguments, _ = by_name.get("search_products", ({}, {}))
            if arguments.get("filters", {}).get("product_type") != "ai_workstation":
                errors.append(f"{example_id}:workstation search has wrong product type")
        if scenario == "search_server_by_gpu_slots":
            arguments, _ = by_name.get("search_products", ({}, {}))
            if arguments.get("filters", {}).get("product_type") != "ai_server":
                errors.append(f"{example_id}:server search has wrong product type")
        if scenario == "search_product_by_budget":
            arguments, _ = by_name.get("search_products", ({}, {}))
            if arguments.get("filters", {}).get("max_base_price_vnd") is None:
                errors.append(f"{example_id}:budget search has no price ceiling")

        if scenario in {
            "search_product_by_budget",
            "search_workstation_by_ram",
            "search_server_by_gpu_slots",
        } and "search_products" not in by_name:
            errors.append(f"{example_id}:search scenario has no product search result")

        if scenario == "unknown_product_spec":
            record = by_name.get("search_product_documents")
            hits = (record[1].get("data") or {}).get("hits", []) if record else None
            if record is None or record[1].get("ok") is not True or hits:
                errors.append(f"{example_id}:unknown product spec must have empty evidence")
            if not labels.should_abstain:
                errors.append(f"{example_id}:unknown product spec must abstain")
        if scenario == "tool_failure":
            record = by_name.get("search_product_documents")
            if record is None or record[1].get("ok") is not False:
                errors.append(f"{example_id}:tool failure has no failed document lookup")
            if not labels.should_abstain:
                errors.append(f"{example_id}:tool failure must abstain")
            if record is not None and hasattr(example, "labels"):
                product_id = record[0].get("product_id")
                user = _user_conversation_text(example)
                final = _final_text(example)
                if not product_id or product_id not in user or product_id not in final:
                    errors.append(f"{example_id}:tool failure product ID is not grounded")
                if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:GB|TB)\b", final, re.IGNORECASE):
                    errors.append(f"{example_id}:tool failure final invents RAM capacity")
        if scenario == "no_product_found":
            record = by_name.get("search_products")
            products = (record[1].get("data") or {}).get("products", []) if record else None
            if products != [] or not labels.should_abstain:
                errors.append(f"{example_id}:no-product case is not empty/abstaining")

    return errors
