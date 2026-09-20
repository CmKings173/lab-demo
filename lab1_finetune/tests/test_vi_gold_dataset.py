import json

from lab1_finetune.data.exporter import export_qwen_jsonl
from lab1_finetune.data.schema import Intent, ScenarioType
from lab1_finetune.data.seed import load_gold_seed
from lab1_finetune.data.splitter import DatasetSplitter
from lab1_finetune.data.statistics import build_manifest
from lab1_finetune.data.validator import DatasetValidator

OLD_PLACEHOLDERS = {
    "Review variant",
    "Complete configuration request",
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
    assert manifest.split_counts == {"train": 40, "validation": 4, "test": 6}
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

    assert len(examples) == 2
    assert all(
        sum(message.role == "user" for message in example.messages) == 2
        for example in examples
    )


def test_search_product_tool_has_strict_structured_filters() -> None:
    example = load_gold_seed()[0]
    search_tool = next(tool for tool in example.tools if tool.name == "search_products")
    filters = search_tool.parameters["properties"]["filters"]

    assert filters["additionalProperties"] is False
    assert set(filters["properties"]) == {
        "product_type",
        "min_ram_gb",
        "min_gpu_count",
        "max_price_vnd",
    }
