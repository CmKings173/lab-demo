import json
import re

from lab1_finetune.data.exporter import export_qwen_jsonl
from lab1_finetune.data.fixtures.tool_results import TOOL_RESULT_MODELS
from lab1_finetune.data.schema import Intent, ScenarioType
from lab1_finetune.data.seed import load_gold_seed
from lab1_finetune.data.splitter import DatasetSplitter
from lab1_finetune.data.statistics import build_manifest
from lab1_finetune.data.validator import DatasetValidator

OLD_PLACEHOLDERS = {
    "Review " + "variant",
    "Complete configuration " + "request",
    "I will clarify",
    "I will only report",
}


def test_gold_seed_has_exactly_25_families_and_at_least_50_vietnamese_examples() -> None:
    examples = load_gold_seed()

    assert len({example.scenario_family_id for example in examples}) == 25
    assert len(examples) >= 50
    assert {example.language for example in examples} == {"vi"}
    assert {example.labels.intent for example in examples} <= set(Intent)
    assert {example.labels.scenario_type for example in examples} == set(ScenarioType)
    assert DatasetValidator().validate(examples).valid is True


def test_gold_seed_does_not_claim_manual_review_without_review_gate() -> None:
    examples = load_gold_seed()

    assert {example.source_type for example in examples} == {
        "synthetic_curated_unreviewed"
    }
    assert not any("human_review" in example.source_type for example in examples)


def test_gold_seed_has_no_old_english_placeholders() -> None:
    serialized = "\n".join(
        message.content or ""
        for example in load_gold_seed()
        for message in example.messages
    )

    assert not any(placeholder in serialized for placeholder in OLD_PLACEHOLDERS)


def test_negative_examples_do_not_invent_tools_or_products() -> None:
    examples = load_gold_seed()
    by_type = {}
    for example in examples:
        by_type.setdefault(example.labels.scenario_type, []).append(example)

    assert all(
        not example.labels.should_call_tool
        and all(not message.tool_calls for message in example.messages)
        for example in by_type[ScenarioType.MISSING_BUDGET]
    )
    for scenario in (
        ScenarioType.GENERAL_VRAM,
        ScenarioType.GENERAL_INFERENCE,
        ScenarioType.GENERAL_LORA,
    ):
        assert all(not example.labels.should_call_tool for example in by_type[scenario])
    for scenario in (
        ScenarioType.NO_PRODUCT_FOUND,
        ScenarioType.UNKNOWN_PRODUCT_SPEC,
        ScenarioType.TOOL_FAILURE,
    ):
        text = " ".join(
            message.content or ""
            for example in by_type[scenario]
            for message in example.messages
            if message.role == "assistant"
        ).casefold()
        assert "chưa" in text or "không" in text


def test_split_export_and_manifest_are_deterministic(tmp_path) -> None:
    examples = load_gold_seed()
    split = DatasetSplitter(seed=42).split(examples)
    report = DatasetValidator().validate_split(split)
    manifest = build_manifest(examples, split=split, seed=42)
    output = tmp_path / "qwen.jsonl"

    export_qwen_jsonl(examples, output)
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert report.valid is True
    assert manifest.example_count == len(examples)
    assert manifest.family_count == 25
    assert manifest.language_counts == {"vi": len(examples)}
    assert manifest.split_counts == {
        "train": len(split.train), "validation": len(split.validation), "test": len(split.test),
    }
    assert [len({item.scenario_family_id for item in part})
            for part in (split.train, split.validation, split.test)] == [20, 2, 3]
    assert len(manifest.content_hash) == 64
    assert len(records) == len(examples)
    assert set(records[0]) == {"messages", "tools"}
    assert manifest == build_manifest(examples, split=split, seed=42)
    assert manifest.created_at.isoformat() == "2026-09-20T00:00:00+00:00"


def test_validator_rejects_label_and_tool_flow_mismatches() -> None:
    example = load_gold_seed()[0]
    no_tool_label = example.model_copy(
        update={"labels": example.labels.model_copy(update={"should_call_tool": False})}
    )
    wrong_tool = example.model_copy(
        update={
            "labels": example.labels.model_copy(update={"expected_tool": "get_product"})
        }
    )

    first = DatasetValidator().validate([no_tool_label])
    second = DatasetValidator().validate([wrong_tool])

    assert any("should_call_tool=false" in error for error in first.errors)
    assert any("expected_tool" in error for error in second.errors)


def test_requirement_change_examples_are_multi_turn() -> None:
    examples = [
        example
        for example in load_gold_seed()
        if example.labels.scenario_type
        == ScenarioType.REQUIREMENT_CHANGED_MID_CONVERSATION
    ]

    assert len(examples) == 4
    assert all(
        sum(message.role == "user" for message in example.messages) == 2
        for example in examples
    )


def test_search_product_tool_has_strict_structured_filters() -> None:
    example = load_gold_seed()[0]
    search_tool = next(tool for tool in example.tools if tool.name == "search_products")
    filters = search_tool.parameters["$defs"]["ProductFilter"]

    assert filters["additionalProperties"] is False
    assert set(filters["properties"]) == {
        "product_type",
        "min_ram_gb",
        "min_gpu_count",
        "max_base_price_vnd",
    }


def _calls_for(scenario: ScenarioType):
    return [
        (example, call)
        for example in load_gold_seed()
        if example.labels.scenario_type == scenario
        for message in example.messages
        for call in message.tool_calls
    ]


def test_no_product_found_examples_preserve_all_user_constraints() -> None:
    calls = _calls_for(ScenarioType.NO_PRODUCT_FOUND)
    server = next(
        call
        for _, call in calls
        if call.arguments["filters"]["product_type"] == "ai_server"
    )
    workstation = next(
        call for _, call in calls if call.arguments["filters"]["product_type"] == "ai_workstation"
    )

    assert server.arguments["filters"] == {
        "product_type": "ai_server",
        "min_gpu_count": 8,
        "max_base_price_vnd": 100_000_000,
    }
    assert workstation.arguments["filters"] == {
        "product_type": "ai_workstation",
        "min_gpu_count": 4,
        "min_ram_gb": 2048,
        "max_base_price_vnd": 150_000_000,
    }


def test_unknown_product_questions_use_exact_product_and_missing_field_query() -> None:
    calls = _calls_for(ScenarioType.UNKNOWN_PRODUCT_SPEC)
    by_product = {call.arguments["product_id"]: call for _, call in calls}

    assert "GPU" in by_product["DEMO-SRV-203"].arguments["query"]
    assert "RAM" in by_product["DEMO-WS-104"].arguments["query"]


def test_tool_failure_intent_is_labeled_per_example() -> None:
    examples = [
        example
        for example in load_gold_seed()
        if example.labels.scenario_type == ScenarioType.TOOL_FAILURE
    ]
    document_failure = next(
        example
        for example in examples
        if example.labels.expected_tool == "search_product_documents"
    )

    assert document_failure.labels.intent == Intent.TECHNICAL_QUESTION
    assert any(
        "DEMO-SRV-205" in (message.content or "") and message.role == "user"
        for message in document_failure.messages
    )


def test_solution_for_five_users_keeps_concurrency_in_sizing_args() -> None:
    matching = [
        call
        for example, call in _calls_for(ScenarioType.SOLUTION_COMPLETE)
        if "5 người dùng" in " ".join(message.content or "" for message in example.messages)
    ]

    assert any(
        call.name == "estimate_ai_requirements"
        and call.arguments.get("concurrent_users") == 5
        for call in matching
    )


def test_gold_has_no_generic_final_or_generic_tool_result() -> None:
    forbidden_final = "Tôi chỉ sử dụng dữ liệu vừa được " + (
        "công cụ trả về để trả lời yêu cầu."
    )
    examples = load_gold_seed()

    for example in examples:
        for message in example.messages:
            assert message.content != forbidden_final
            if message.role == "tool":
                assert json.loads(message.content or "null") != {"ok": True, "data": []}


def test_all_gold_tool_results_parse_with_runtime_result_contract() -> None:
    for example in load_gold_seed():
        calls = {
            call.id: call
            for message in example.messages
            for call in message.tool_calls
        }
        for message in example.messages:
            if message.role == "tool":
                call = calls[message.tool_call_id]
                TOOL_RESULT_MODELS[call.name].model_validate_json(message.content)


def test_dataset_validator_inherits_tool_result_state_invariant() -> None:
    example = next(
        item for item in load_gold_seed()
        if any(message.role == "tool" for message in item.messages)
    )
    messages = list(example.messages)
    tool_index = next(i for i, message in enumerate(messages) if message.role == "tool")
    payload = json.loads(messages[tool_index].content)
    payload["ok"] = True
    payload["error"] = "service_unavailable"
    messages[tool_index] = messages[tool_index].model_copy(
        update={"content": json.dumps(payload)}
    )
    result = DatasetValidator().validate([example.model_copy(update={"messages": messages})])

    assert result.valid is False
    assert any("invalid tool result" in error for error in result.errors)


def test_gold_has_ten_multi_tool_trajectories() -> None:
    examples = load_gold_seed()
    multi_tool = [
        example
        for example in examples
        if sum(len(message.tool_calls) for message in example.messages) > 1
    ]

    assert len(examples) == 60
    assert len(multi_tool) == 10


def test_demo_entity_ids_types_and_user_tool_references_are_consistent() -> None:
    for example in load_gold_seed():
        user_ids = set(
            re.findall(
                r"DEMO-(?:SRV|WS)-\d+",
                " ".join(
                    message.content or ""
                    for message in example.messages
                    if message.role == "user"
                ),
            )
        )
        call_ids = {
            value
            for message in example.messages
            for call in message.tool_calls
            for value in (
                [call.arguments.get("product_id")]
                + call.arguments.get("product_ids", [])
            )
            if isinstance(value, str)
        }
        assert user_ids <= call_ids or not example.labels.should_call_tool

        calls = {
            call.id: call
            for message in example.messages
            for call in message.tool_calls
        }
        for message in example.messages:
            if message.role != "tool":
                continue
            call = calls[message.tool_call_id]
            result = TOOL_RESULT_MODELS[call.name].model_validate_json(message.content)
            products = []
            if call.name == "get_product" and result.data:
                products = [result.data]
            elif call.name == "search_products" and result.data:
                products = result.data.products
            for product in products:
                expected_type = "ai_server" if "-SRV-" in product.id else "ai_workstation"
                assert product.product_type.value == expected_type

    serialized = json.dumps(
        [example.model_dump(mode="json") for example in load_gold_seed()],
        ensure_ascii=False,
    )
    assert "DEMO-" + "DEMO-" not in serialized


def test_base_price_search_is_not_labeled_as_full_solution_budget() -> None:
    examples = [
        example
        for example in load_gold_seed()
        if example.labels.scenario_type == ScenarioType.SEARCH_PRODUCT_BY_BUDGET
    ]

    assert all(
        not example.labels.extracted_requirement.model_dump(exclude_none=True)
        for example in examples
    )


def test_contradictory_solution_still_labels_missing_budget() -> None:
    example = next(
        example
        for example in load_gold_seed()
        if example.example_id == "07_contradictory_requirement-2"
    )

    assert example.labels.missing_fields == ["budget_vnd"]
