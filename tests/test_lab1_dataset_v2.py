from lab1.data.schema import DatasetLabels, FineTuneExample
from lab1.data.seed import build_seed_examples
from lab1.data.validator import DatasetValidator
from lab1.src.pipeline import DatasetPipeline
from shared.contracts import ChatMessage, ToolCall
from shared.tool_contracts import TOOL_DEFINITIONS


def make_tool_example(example_id: str, family_id: str) -> FineTuneExample:
    return FineTuneExample(
        example_id=example_id,
        scenario_family_id=family_id,
        scenario_summary="Find products for a complete request",
        task_type="solution_request",
        difficulty="medium",
        language="vi",
        source_type="synthetic_reviewed",
        messages=[
            ChatMessage(role="system", content="Use tools and do not invent catalog facts."),
            ChatMessage(role="user", content="Tìm máy phù hợp."),
            ChatMessage(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="search_products",
                        arguments={"filters": {"product_type": "ai_server"}},
                    )
                ],
            ),
            ChatMessage(
                role="tool",
                tool_call_id="call-1",
                content='{"products": []}',
            ),
            ChatMessage(role="assistant", content="Không tìm thấy sản phẩm phù hợp."),
        ],
        tools=TOOL_DEFINITIONS,
        labels=DatasetLabels(
            intent="search_products",
            should_call_tool=True,
            expected_tool="search_products",
            must_not_invent_product_fact=True,
        ),
    )


def test_valid_tool_call_training_example_is_accepted() -> None:
    report = DatasetValidator().validate([make_tool_example("ex-1", "family-1")])

    assert report.valid is True
    assert report.errors == []


def test_tool_call_without_definition_is_rejected() -> None:
    example = make_tool_example("ex-1", "family-1").model_copy(update={"tools": []})

    report = DatasetValidator().validate([example])

    assert report.valid is False
    assert any("search_products" in error for error in report.errors)


def test_raw_record_schema_errors_are_reported_together() -> None:
    record = make_tool_example("ex-1", "family-1").model_dump(mode="json")
    record.pop("scenario_family_id")
    record["messages"] = []
    record["labels"]["unsupported_label"] = True

    report = DatasetValidator().validate_records([record])

    assert report.valid is False
    assert any("scenario_family_id" in error for error in report.errors)
    assert any("messages" in error for error in report.errors)
    assert any("unsupported_label" in error for error in report.errors)


def test_invalid_role_ordering_and_near_duplicate_families_are_rejected() -> None:
    first = make_tool_example("ex-1", "family-1")
    second = make_tool_example("ex-2", "family-2").model_copy(
        update={
            "scenario_summary": "Find products for a complete requests",
            "messages": [
                ChatMessage(role="user", content="Need a system."),
                ChatMessage(role="system", content="Too late."),
            ],
        }
    )

    report = DatasetValidator().validate([first, second])

    assert report.valid is False
    assert any("near-duplicate" in error for error in report.errors)
    assert any("invalid role ordering" in error for error in report.errors)


def test_split_is_deterministic_by_scenario_family_without_leakage() -> None:
    examples = [
        make_tool_example(f"{family}-{variant}", f"family-{family}")
        for family in range(20)
        for variant in range(2)
    ]

    first = DatasetPipeline(seed=7).split(examples)
    second = DatasetPipeline(seed=7).split(examples)

    assert first == second
    train_families = {item.scenario_family_id for item in first.train}
    validation_families = {item.scenario_family_id for item in first.validation}
    test_families = {item.scenario_family_id for item in first.test}
    assert train_families.isdisjoint(validation_families | test_families)
    assert validation_families.isdisjoint(test_families)
    assert len(train_families) == 16
    assert len(validation_families) == 2
    assert len(test_families) == 2


def test_validator_detects_split_leakage() -> None:
    example = make_tool_example("ex-1", "family-1")
    split = DatasetPipeline(seed=7).split([example])
    split.train.append(example)
    split.test.append(example.model_copy(update={"example_id": "ex-2"}))

    report = DatasetValidator().validate_split(split)

    assert report.valid is False
    assert any("leakage" in error for error in report.errors)


def test_seed_dataset_has_reviewable_families_and_required_coverage() -> None:
    examples = build_seed_examples()
    families = {example.scenario_family_id for example in examples}
    intents = {example.labels.intent for example in examples}
    languages = {example.language for example in examples}

    assert 20 <= len(families) <= 30
    assert len(examples) >= len(families) * 2
    assert {"tool_failure", "out_of_scope", "ambiguous_request"} <= intents
    assert {"vi", "mixed", "en"} <= languages
    report = DatasetValidator().validate(examples)
    assert report.valid is True
    assert report.manifest.family_count == len(families)
