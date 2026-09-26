# ruff: noqa: E501

import ast
import inspect
import json
import re
from collections import Counter
from dataclasses import replace

import pytest

from lab1_finetune.data.build_expanded import (
    _checked_split_overlap_counts,
    _lexical_components,
    _semantic_group_leakage,
    _split_overlap_counts,
    _validation_groups,
    build_expanded_artifacts,
)
from lab1_finetune.data.expansion import semantic_validation
from lab1_finetune.data.expansion.difficulty import infer_difficulty
from lab1_finetune.data.expansion.diversity import (
    DiversityReport,
    _near_duplicate_stats_v2,
    audit_examples,
)
from lab1_finetune.data.expansion.generator import (
    _build_failure,
    _estimate_step,
    _search_step,
    build_expanded_examples,
    should_be_multi_turn,
)
from lab1_finetune.data.expansion.personas import PERSONA_PROFILES
from lab1_finetune.data.expansion.review import (
    build_review_sample,
    review_manifest,
    write_review_artifacts,
)
from lab1_finetune.data.expansion.scenarios import (
    CONCURRENCY,
    CONTEXT_LENGTHS,
    context_for,
)
from lab1_finetune.data.expansion.semantic_specs import (
    ComparisonSpec,
    MultiToolFlow,
    MultiToolFlowSpec,
    TechnicalFactSpec,
)
from lab1_finetune.data.expansion.semantic_validation import validate_generated_semantics
from lab1_finetune.data.expansion.spec import EXPANSION_FAMILY_SPECS
from lab1_finetune.data.expansion.wording import (
    comparison_prompt,
    missing_prompt,
    multi_tool_prompt,
    no_product_found_prompt,
    novice_prompt,
    search_by_budget_prompt,
    search_server_gpu_prompt,
    search_workstation_ram_prompt,
    solution_prompt,
    technical_prompt,
)
from lab1_finetune.data.frozen_contracts import (
    TOOL_ARG_MODELS,
    ProductFilter,
    ProductType,
)
from lab1_finetune.data.schema import Intent, ScenarioType
from lab1_finetune.data.similarity import near_duplicate_pairs, normalize_for_similarity
from lab1_finetune.evaluation.benchmark import (
    audit_eval_isolation,
    build_independent_eval_cases,
    build_independent_eval_records,
)
from lab1_finetune.evaluation.build_benchmark import EvalManifest, build_eval_artifacts
from lab1_finetune.evaluation.schema import EvaluationCase


def _read_jsonl(path):
    import json

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_expansion_spec_has_twelve_families_and_target_total() -> None:
    assert len(EXPANSION_FAMILY_SPECS) == 12
    assert sum(item.quota for item in EXPANSION_FAMILY_SPECS) == 1200


def test_persona_catalog_contains_all_required_personas() -> None:
    assert set(PERSONA_PROFILES) == {
        "NON_TECHNICAL_USER",
        "MANAGER",
        "PURCHASING",
        "IT_GENERALIST",
        "DEVELOPER",
        "ML_ENGINEER",
        "SOLUTION_ARCHITECT",
    }


def test_expansion_is_deterministic_and_has_target_size() -> None:
    first = build_expanded_examples(seed=20260922)
    second = build_expanded_examples(seed=20260922)

    assert first == second
    assert len(first) == 1200
    assert len({item.example.example_id for item in first}) == 1200


def test_expansion_has_contract_safe_diverse_rows() -> None:
    report = audit_examples(build_expanded_examples(seed=20260922))

    assert report.valid is True, report
    assert set(report.persona_counts) == set(PERSONA_PROFILES)
    assert set(report.difficulty_counts) == {"easy", "medium", "hard"}
    assert 0.20 <= report.turn_counts["multi_turn"] / report.example_count <= 0.30
    assert report.tool_pattern_counts["multi_tool"] > 0
    assert report.tool_pattern_counts["failure"] > 0
    assert report.tool_pattern_counts["no_tool"] > 0
    assert report.label_text_errors == []


def test_internal_near_duplicates_are_reported_but_exact_duplicates_still_block() -> None:
    report = DiversityReport(
        example_count=2, family_counts={}, persona_counts={}, difficulty_counts={},
        turn_counts={}, tool_pattern_counts={}, exact_duplicates=0,
        near_duplicate_pairs=1, near_duplicate_rate=1.0,
        near_user_duplicate_pairs=1, near_user_duplicate_example_ratio=1.0,
        near_conversation_duplicate_pairs=1,
        near_conversation_duplicate_example_ratio=1.0,
    )
    assert report.valid
    assert not replace(report, exact_user_duplicates=1).valid
    assert not replace(report, exact_conversation_duplicates=1).valid
    assert not replace(report, semantic_errors=["contradiction"]).valid
    assert not replace(report, encoding_errors=["replacement_character"]).valid


def test_semantic_templates_and_groups_are_reused_without_exact_user_duplicates() -> None:
    generated = build_expanded_examples(seed=20260922)
    template_counts = Counter(item.semantic_template_id for item in generated)

    assert 20 < len(template_counts) < 100
    assert max(template_counts.values()) > 5
    assert all(item.semantic_group_id for item in generated)
    assert len({item.example.example_id for item in generated}) == 1200

    report = audit_examples(generated)
    assert report.exact_user_duplicates == 0
    assert report.exact_conversation_duplicates == 0
    assert report.near_user_duplicate_pairs > 0
    assert report.near_user_duplicate_example_ratio > 0


def test_difficulty_is_derived_from_complexity() -> None:
    assert infer_difficulty(
        scenario_type="solution_complete",
        tool_count=0,
        multi_turn=False,
        should_abstain=False,
        tool_failure=False,
        missing_field_count=0,
    ) == "easy"
    assert infer_difficulty(
        scenario_type="tool_failure",
        tool_count=1,
        multi_turn=True,
        should_abstain=True,
        tool_failure=True,
        missing_field_count=0,
    ) == "hard"


def test_review_sample_covers_families_and_personas() -> None:
    sample = build_review_sample(build_expanded_examples(seed=20260922), target=84)

    assert 70 <= len(sample) <= 100
    assert {item.family_id for item in sample} == {
        item.family_id for item in EXPANSION_FAMILY_SPECS
    }
    assert len({item.persona for item in sample}) == 7
    manifest = review_manifest(sample)
    assert set(manifest.difficulty_counts) == {"easy", "medium", "hard"}
    assert set(manifest.turn_counts) == {"single_turn", "multi_turn"}
    assert set(manifest.tool_pattern_counts) == {
        "no_tool", "single_tool", "multi_tool", "failure"
    }
    assert 0 < manifest.abstention_count < manifest.total


def test_semantic_group_leakage_is_detected_even_with_distinct_rows() -> None:
    generated = build_expanded_examples(seed=20260922)
    groups = {}
    for item in generated:
        groups.setdefault(item.semantic_group_id, []).append(item.example.example_id)
    group_id, ids = next((group, ids) for group, ids in groups.items() if len(ids) >= 2)
    assert _semantic_group_leakage(generated, {ids[0]}, {ids[1]}) == [group_id]


def test_validation_group_selection_is_deterministic_and_family_complete() -> None:
    generated = build_expanded_examples(seed=20260922)
    selected = _validation_groups(generated)
    assert selected == _validation_groups(generated)
    train_families = {item.family_id for item in generated if item.semantic_group_id not in selected}
    validation_families = {item.family_id for item in generated if item.semantic_group_id in selected}
    assert len(train_families) == len(validation_families) == 12


def test_near_linked_semantic_groups_form_one_split_component() -> None:
    groups = ["recipe-a", "recipe-b", "recipe-c", "unrelated"]
    components = _lexical_components(groups, {(0, 1), (1, 2)})
    assert components["recipe-a"] == components["recipe-b"] == components["recipe-c"]
    assert components["unrelated"] != components["recipe-a"]


def test_cross_split_numeric_variant_is_rejected() -> None:
    first, second = build_expanded_examples(seed=20260922)[:2]

    def with_user(item, text):
        messages = list(item.example.messages)
        user_index = max(index for index, message in enumerate(messages) if message.role == "user")
        messages[user_index] = messages[user_index].model_copy(update={"content": text})
        return replace(item, example=item.example.model_copy(update={"messages": messages}))

    first = with_user(first, "Tim may it nhat 512GB RAM")
    second = with_user(second, "Tim may it nhat 1024GB RAM")
    overlap = _split_overlap_counts(
        [first, second], {first.example.example_id}, {second.example.example_id}
    )
    assert overlap["user"] == 1
    with pytest.raises(ValueError, match="near-user leakage"):
        _checked_split_overlap_counts(
            [first, second], {first.example.example_id}, {second.example.example_id}
        )


def test_review_rows_include_all_requested_audit_dimensions(tmp_path) -> None:
    generated = build_expanded_examples(seed=20260922)
    write_review_artifacts(
        generated,
        sample_path=tmp_path / "review_sample.jsonl",
        manifest_path=tmp_path / "review_manifest.json",
    )
    rows = _read_jsonl(tmp_path / "review_sample.jsonl")
    assert len(rows) == 84
    for row in rows:
        assert {
            "example_id", "family_id", "persona", "difficulty", "scenario_type",
            "semantic_template_id", "wording_recipe_id", "turn_type",
            "tool_pattern", "should_abstain",
        } <= row.keys()


def test_expanded_artifacts_have_grouped_split_and_qwen_exports(tmp_path) -> None:
    manifest = build_expanded_artifacts(output_root=tmp_path / "generated")

    assert manifest.total_examples == 1200
    assert manifest.split_counts["train"] + manifest.split_counts["validation"] == 1200
    assert manifest.family_leakage == []
    assert set(manifest.train_family_counts) == set(manifest.validation_family_counts)
    assert len(manifest.train_family_counts) == 12
    assert manifest.semantic_group_leakage == []
    assert manifest.exact_user_duplicates == 0
    assert manifest.near_user_duplicate_pairs > 0
    assert manifest.train_validation_near_user_pairs == 0
    assert manifest.train_validation_near_conversation_pairs == 0
    assert set(manifest.validation_tool_pattern_counts) == {
        "no_tool", "single_tool", "multi_tool", "failure"
    }
    assert manifest.train_tool_pattern_counts.get("failure", 0) > 0
    assert manifest.validation_tool_pattern_counts.get("failure", 0) > 0
    assert 0.15 <= manifest.split_counts["validation"] / manifest.total_examples <= 0.25
    for family, count in manifest.validation_family_counts.items():
        if family not in {"expanded_failure_abstention", "expanded_out_of_scope"}:
            assert count / manifest.family_counts[family] <= 0.35
    assert manifest.encoding_errors == []
    assert len(_read_jsonl(tmp_path / "generated" / "exports" / "train_qwen.jsonl")) == manifest.split_counts["train"]
    assert len(_read_jsonl(tmp_path / "generated" / "exports" / "validation_qwen.jsonl")) == manifest.split_counts["validation"]
    assert len(_read_jsonl(tmp_path / "generated" / "review_sample.jsonl")) == 84
    assert (tmp_path / "generated" / "review_manifest.json").exists()
    duplicate_report = json.loads(
        (tmp_path / "generated" / "near_duplicate_report.json").read_text(encoding="utf-8")
    )
    assert duplicate_report["max_cluster_size"] < manifest.total_examples * 0.1
    assert {"size", "example_ids", "families", "semantic_template_ids",
            "wording_recipe_ids", "normalized_representative"} <= (
        duplicate_report["top_clusters"][0].keys()
    )


def test_independent_eval_is_frozen_and_isolated() -> None:
    training = build_expanded_examples(seed=20260922)
    cases = build_independent_eval_cases(seed=20260923)
    report = audit_eval_isolation(cases, training)

    assert len(cases) == 120
    assert report.exact_overlap == 0
    assert report.near_duplicate_pairs == 0
    assert report.internal_exact_user_duplicates == 0
    assert report.internal_near_user_pairs == 0


def test_eval_recipes_cover_twelve_families_and_keep_ids_grounded() -> None:
    records = build_independent_eval_records(seed=20260923)
    assert len({record.scenario_family_id for record in records}) == 12
    for record in records:
        user = next(message.content or "" for message in reversed(record.case.messages) if message.role == "user")
        calls = record.case.gold_labels.expected_tool_calls
        if record.scenario_family_id == "eval_comparison":
            assert all(product_id in user for product_id in calls[0].arguments["product_ids"])
        if record.scenario_family_id in {"eval_multi_tool", "eval_failure"}:
            document_call = next(call for call in calls if call.name == "search_product_documents")
            assert document_call.arguments["product_id"] in user


def test_eval_internal_numeric_clone_remains_a_hard_failure() -> None:
    original = build_independent_eval_cases(seed=20260923)[0]

    def with_user(case, text, case_id):
        messages = list(case.messages)
        user_index = max(index for index, message in enumerate(messages) if message.role == "user")
        messages[user_index] = messages[user_index].model_copy(update={"content": text})
        return case.model_copy(update={"case_id": case_id, "messages": messages})

    first = with_user(original, "Tim may it nhat 512GB RAM", "eval-mutation-a")
    second = with_user(original, "Tim may it nhat 1024GB RAM", "eval-mutation-b")
    report = audit_eval_isolation([first, second], [])
    assert report.internal_near_user_pairs == 1
    assert not report.valid


def test_eval_audit_counts_actual_scenarios_and_does_not_claim_personas() -> None:
    cases = build_independent_eval_cases(seed=20260923)
    report = audit_eval_isolation(cases, [])
    assert sum(report.scenario_counts.values()) == 120
    assert set(report.scenario_counts) == {
        case.gold_labels.scenario_type.value for case in cases
    }
    assert "persona_counts" not in EvalManifest.__dataclass_fields__
    assert "persona_robustness_assessed" in EvalManifest.__dataclass_fields__


def test_independent_eval_artifacts_are_written_separately(tmp_path) -> None:
    manifest = build_eval_artifacts(output_root=tmp_path / "evaluation")

    assert manifest.total_examples == 120
    assert manifest.exact_overlap_with_training == 0
    assert manifest.near_duplicate_pairs_with_training == 0
    assert manifest.internal_exact_user_duplicates == 0
    assert manifest.internal_near_user_pairs == 0
    assert manifest.semantic_template_overlap_with_training == 0
    assert len(_read_jsonl(tmp_path / "evaluation" / "gold_eval.jsonl")) == 120


def _tool_payloads(item):
    return [
        json.loads(message.content or "{}")
        for message in item.example.messages
        if message.role == "tool"
    ]


def _tool_calls(item):
    return [
        call
        for message in item.example.messages
        for call in message.tool_calls
    ]


def test_generated_prompts_have_no_python_repr_or_fake_zero_price() -> None:
    for item in build_expanded_examples(seed=20260922):
        for message in item.example.messages:
            if message.role != "user":
                continue
            text = message.content or ""
            assert not re.search(r"\('[^\n]*',\)|\[[^\n]*\]|\{[^\n]*\}", text)
            assert not re.search(r"(?<!\d)0\s+triệu\b", text.casefold())


def test_generated_user_and_assistant_text_has_no_replacement_character() -> None:
    for item in build_expanded_examples(seed=20260922):
        for message in item.example.messages:
            if message.role in {"user", "assistant"}:
                assert "\ufffd" not in (message.content or ""), item.example.example_id


def _prior_conversation_text(example) -> str:
    user_positions = [
        index for index, message in enumerate(example.messages) if message.role == "user"
    ]
    if len(user_positions) < 2:
        return ""
    current_user = user_positions[-1]
    return " ".join(
        message.content or ""
        for message in example.messages[:current_user]
        if message.role in {"user", "assistant"}
    )


def test_missing_and_novice_history_hide_unavailable_requirement_values() -> None:
    model_pattern = re.compile(
        r"\b(?:Qwen(?:\s+coder)?|Llama(?:\s+coder)?|Mistral|Yi)\s+"
        r"\d+(?:\.\d+)?\s*B\b|\b\d+(?:\.\d+)?\s*B\b",
        re.IGNORECASE,
    )
    budget_pattern = re.compile(r"\b\d[\d.,]*\s*(?:triệu|trieu)\b", re.IGNORECASE)
    usage_decision_pattern = re.compile(
        r"\b(?:vừa\s+chọn|đã\s+chọn|đã\s+chốt|vừa\s+chốt)\s+"
        r"(?:hướng\s+)?(?:chạy|dùng|sử dụng|fine[- ]?tune|inference|LoRA)\b",
        re.IGNORECASE,
    )
    rows = build_expanded_examples(seed=20260922)
    checked = Counter()

    for row in rows:
        if row.family_id not in {
            "expanded_missing_information",
            "expanded_novice_users",
        }:
            continue
        index = int(row.example.example_id.rsplit("-", 1)[1])
        assert bool(_prior_conversation_text(row.example)) == should_be_multi_turn(
            row.family_id,
            row.example.labels.scenario_type,
            20260922,
            index,
        )
        text = _prior_conversation_text(row.example)
        if not text:
            continue
        missing = set(row.example.labels.missing_fields)
        if "model_size_b" in missing:
            checked["model_size_b"] += 1
            assert not model_pattern.search(text), row.example.example_id
        if "budget_vnd" in missing:
            checked["budget_vnd"] += 1
            assert not budget_pattern.search(text), row.example.example_id
        if "usage" in missing:
            checked["usage"] += 1
            assert not usage_decision_pattern.search(text), row.example.example_id

    assert all(checked[field] > 0 for field in ("model_size_b", "budget_vnd", "usage"))


def test_semantic_gate_rejects_mutated_history_that_leaks_missing_fields() -> None:
    rows = build_expanded_examples(seed=20260922)
    cases = (
        ("missing_model_size", "Team đã chọn Qwen 32B.", "model_size_b"),
        ("missing_budget", "Lúc trước ngân sách dự kiến khoảng 240 triệu.", "budget_vnd"),
        (
            "missing_usage",
            "Team đã chốt fine-tune bằng LoRA.",
            "usage",
        ),
    )

    for scenario, leaked_text, field in cases:
        row = next(
            item
            for item in rows
            if item.family_id == "expanded_missing_information"
            and item.example.labels.scenario_type.value == scenario
            and _prior_conversation_text(item.example)
        )
        messages = list(row.example.messages)
        history_user = next(
            index
            for index, message in enumerate(messages)
            if message.role == "user"
        )
        messages[history_user] = messages[history_user].model_copy(
            update={"content": leaked_text}
        )
        corrupted = row.example.model_copy(update={"messages": messages})

        errors = validate_generated_semantics([corrupted])
        assert any(field in error and "history" in error for error in errors), errors


def test_quality_audit_rejects_corrupted_user_or_assistant_text() -> None:
    example = build_expanded_examples(seed=20260922)[0].example
    for role in ("user", "assistant"):
        index = next(
            index for index, message in enumerate(example.messages)
            if message.role == role and message.content
        )
        messages = list(example.messages)
        messages[index] = messages[index].model_copy(update={"content": "B\ufffdn m\ufffdnh"})
        corrupted = example.model_copy(update={"messages": messages})
        report = audit_examples([corrupted])
        assert report.valid is False
        assert report.encoding_errors == [f"{example.example_id}:{role}:replacement_character"]


def test_all_solution_prompt_variations_are_utf8_clean() -> None:
    context = context_for(17)
    profile = PERSONA_PROFILES["MANAGER"]
    for variant in range(12):
        assert "\ufffd" not in solution_prompt(profile, context, variant).text


def test_solution_prompt_uses_named_recipes_and_keeps_context_values_once() -> None:
    context = context_for(17)
    profile = PERSONA_PROFILES["MANAGER"]
    rendered = [solution_prompt(profile, context, variant) for variant in range(12)]

    assert len({item.recipe_id for item in rendered}) >= 4
    assert all(item.recipe_id != "default" for item in rendered)
    for item in rendered:
        assert context.domain in item.text
        assert context.model_name in item.text
        assert str(context.concurrent_users) in item.text
        assert f"{context.budget_vnd // 1_000_000} triệu" in item.text
        assert item.text.count(f"{context.budget_vnd // 1_000_000} triệu") == 1
        assert str(context.context_length) in item.text
        assert str(context.storage_gb) in item.text
        assert "\ufffd" not in item.text


def test_missing_prompt_recipes_do_not_leak_missing_requirement_values() -> None:
    context = context_for(17)
    profile = PERSONA_PROFILES["MANAGER"]
    scenarios = (
        (["budget_vnd"], ("ngân sách",)),
        (["usage"], ("cách dùng",)),
        (["model_size_b"], ("model",)),
        (["model_size_b", "usage", "budget_vnd"], ("model", "cách dùng", "ngân sách")),
    )

    for missing, required_fragments in scenarios:
        rendered = [missing_prompt(profile, context, missing, variant) for variant in range(10)]
        assert len({item.recipe_id for item in rendered}) >= 4
        for item in rendered:
            assert isinstance(item.text, str)
            assert all(fragment in item.text.casefold() for fragment in required_fragments)
            if "budget_vnd" in missing:
                assert f"{context.budget_vnd // 1_000_000} triệu" not in item.text
            if "model_size_b" in missing:
                assert context.model_name not in item.text
            if "usage" in missing:
                assert "nhu cầu là chạy model" not in item.text.casefold()
                assert "nhu cầu là tinh chỉnh model" not in item.text.casefold()
            assert "\ufffd" not in item.text


def test_novice_prompt_recipes_keep_discovery_without_inventing_specs() -> None:
    context = context_for(17)
    profile = PERSONA_PROFILES["NON_TECHNICAL_USER"]
    rendered = [novice_prompt(profile, context, variant) for variant in range(10)]

    assert len({item.recipe_id for item in rendered}) >= 4
    for item in rendered:
        assert context.domain in item.text
        assert context.model_name not in item.text
        assert f"{context.budget_vnd // 1_000_000} triệu" not in item.text
        assert not any(term in item.text.casefold() for term in ("vram", "kv cache", "batch size"))
        assert "\ufffd" not in item.text


def test_migrated_generator_families_store_real_wording_recipe_ids() -> None:
    generated = build_expanded_examples(seed=20260922)
    expected_families = {
        "expanded_solution_design",
        "expanded_missing_information",
        "expanded_novice_users",
    }
    expected_recipes = {
        "expanded_solution_design": {"goal_first", "model_first", "budget_first", "capacity_first", "context_first", "resource_first"},
        "expanded_missing_information": {"status_first", "missing_first", "clarification_first", "known_values_first", "procurement_first"},
        "expanded_novice_users": {"goal_only", "how_to_start", "hardware_uncertain", "requirements_discovery", "nontechnical_guidance"},
    }

    for family_id in expected_families:
        rows = [item for item in generated if item.family_id == family_id]
        assert rows
        assert len({item.wording_recipe_id for item in rows}) >= 4
        assert all(item.wording_recipe_id in expected_recipes[family_id] for item in rows)
        assert all(item.wording_recipe_id != item.semantic_template_id for item in rows)


def test_migrated_prompt_composition_has_no_repeated_phrase_artifacts() -> None:
    migrated = {
        "expanded_solution_design",
        "expanded_missing_information",
        "expanded_novice_users",
    }
    for item in build_expanded_examples(seed=20260922):
        if item.family_id not in migrated:
            continue
        user = next(
            message.content or ""
            for message in reversed(item.example.messages)
            if message.role == "user"
        )
        assert not re.search(r"\b(có|với|cho|mình)\s+\1\b", user, re.IGNORECASE)
        assert user.casefold().count("benchmark") <= 1


def test_large_model_low_budget_rows_match_label() -> None:
    rows = [
        item
        for item in build_expanded_examples(seed=20260922)
        if item.example.labels.scenario_type == ScenarioType.LARGE_MODEL_LOW_BUDGET
    ]

    assert rows
    for item in rows:
        requirement = item.example.labels.extracted_requirement
        assert requirement.model_size_b is not None and requirement.model_size_b >= 32
        assert requirement.budget_vnd is not None and requirement.budget_vnd <= 240_000_000
        assert item.example.labels.should_abstain is True


def test_product_search_filters_match_returned_products() -> None:
    rows = [
        item
        for item in build_expanded_examples(seed=20260922)
        if item.example.labels.intent.value == "product_search"
    ]

    assert rows
    assert validate_generated_semantics(rows) == []
    for item in rows:
        for call, payload in zip(_tool_calls(item), _tool_payloads(item), strict=False):
            if call.name != "search_products" or not payload.get("data"):
                continue
            filters = call.arguments.get("filters", {})
            for product in payload["data"].get("products", []):
                if filters.get("product_type") is not None:
                    assert product["product_type"] == filters["product_type"]
                if filters.get("min_ram_gb") is not None:
                    assert product["max_ram_gb"] >= filters["min_ram_gb"]
                if filters.get("min_gpu_count") is not None:
                    assert product["max_gpu_slots"] >= filters["min_gpu_count"]
                if filters.get("max_base_price_vnd") is not None:
                    assert product["base_price_vnd"] <= filters["max_base_price_vnd"]


def test_unknown_product_spec_has_no_evidence_and_abstains() -> None:
    rows = [
        item
        for item in build_expanded_examples(seed=20260922)
        if item.example.labels.scenario_type == ScenarioType.UNKNOWN_PRODUCT_SPEC
    ]

    assert rows
    for item in rows:
        assert item.example.labels.should_abstain is True
        assert any(call.name == "search_product_documents" for call in _tool_calls(item))
        assert any(payload.get("data", {}).get("hits") == [] for payload in _tool_payloads(item))


def test_semantic_groups_are_recipe_based_and_never_leak(tmp_path) -> None:
    generated = build_expanded_examples(seed=20260922)
    for item in generated:
        assert item.semantic_group_id == (
            f"{item.semantic_template_id}:recipe_{item.wording_recipe_id}"
        )
        assert ":group_" not in item.semantic_group_id
    manifest = build_expanded_artifacts(output_root=tmp_path / "generated")
    assert manifest.semantic_group_leakage == []
    assert manifest.semantic_group_count > 81


def test_persona_changes_user_wording() -> None:
    context = context_for(17)
    texts = {
        solution_prompt(profile, context, 0).text
        for profile in PERSONA_PROFILES.values()
    }
    assert len(texts) == len(PERSONA_PROFILES)


def test_contradiction_and_tool_failure_are_hard() -> None:
    generated = build_expanded_examples(seed=20260922)
    for item in generated:
        scenario = item.example.labels.scenario_type
        if scenario in {ScenarioType.CONTRADICTORY_REQUIREMENT, ScenarioType.TOOL_FAILURE}:
            assert item.example.difficulty == "hard"


def test_tool_failure_rows_have_distinct_wording_groups_and_grounded_targets() -> None:
    rows = [
        item for item in build_expanded_examples(seed=20260922)
        if item.example.labels.scenario_type == ScenarioType.TOOL_FAILURE
    ]
    assert len(rows) == 30
    assert len({item.wording_recipe_id for item in rows}) >= 3
    assert len({item.semantic_group_id for item in rows}) >= 3
    assert all(item.wording_recipe_id != item.semantic_template_id for item in rows)
    for item in rows:
        call = _tool_calls(item)[0]
        result = _tool_payloads(item)[0]
        user = next(message.content or "" for message in reversed(item.example.messages) if message.role == "user")
        final = next(message.content or "" for message in reversed(item.example.messages) if message.role == "assistant" and message.content)
        product_id = call.arguments["product_id"]
        assert call.name == "search_product_documents"
        assert product_id in user and product_id in final
        assert result["ok"] is False
        assert item.example.labels.should_abstain


def test_tool_failure_gate_rejects_invented_ram_after_failed_document_search() -> None:
    row = next(
        item for item in build_expanded_examples(seed=20260922)
        if item.example.labels.scenario_type == ScenarioType.TOOL_FAILURE
    )
    messages = list(row.example.messages)
    final_index = max(index for index, message in enumerate(messages) if message.role == "assistant" and message.content)
    product_id = _tool_calls(row)[0].arguments["product_id"]
    messages[final_index] = messages[final_index].model_copy(
        update={"content": f"{product_id} có RAM tối đa là 512GB."}
    )
    mutated = replace(row, example=row.example.model_copy(update={"messages": messages}))
    assert any("tool failure final invents" in error for error in validate_generated_semantics([mutated]))


def test_numeric_variants_are_detectable_near_templates() -> None:
    left = "Tìm workstation hỗ trợ ít nhất 512GB RAM dưới 200 triệu."
    right = "Tìm workstation hỗ trợ ít nhất 768GB RAM dưới 300 triệu."
    assert normalize_for_similarity(left) == normalize_for_similarity(right)
    pairs, ratio = _near_duplicate_stats_v2([left, right], 0.92)
    assert pairs == 1
    assert ratio == 1.0


def test_same_intent_numeric_variants_are_not_skipped() -> None:
    left = "Tìm máy ít nhất 512GB RAM cho nhóm nội bộ."
    right = "Tìm máy ít nhất 1024GB RAM cho nhóm nội bộ."
    pairs, ratio = _near_duplicate_stats_v2([left, right], 0.92, ["same", "same"])
    assert (pairs, ratio) == (1, 1.0)


def test_product_and_configuration_ids_share_canonical_form() -> None:
    assert normalize_for_similarity("So sánh SYN-WS-001 và cfg-alpha-01") == (
        normalize_for_similarity("So sánh EVAL-WS-101 và cfg-beta-99")
    )


def test_short_numeric_variants_are_candidates_after_normalization() -> None:
    texts = ["Tim may 512GB RAM", "Tim may 1024GB RAM"]
    assert near_duplicate_pairs(texts, 0.92) == {(0, 1)}


def test_eval_overlap_detects_id_and_number_only_variants() -> None:
    training = build_expanded_examples()[0].example
    train_user = "So sánh SYN-WS-001 và SYN-WS-002 trong tầm 200 triệu."
    eval_user = "So sánh EVAL-WS-101 và EVAL-WS-102 trong tầm 300 triệu."
    train_case = training.model_copy(update={
        "messages": [training.messages[0], training.messages[-1].model_copy(update={"role": "user", "content": train_user})],
    })
    eval_case = EvaluationCase(
        case_id="eval-overlap-mutation",
        messages=[training.messages[0], training.messages[-1].model_copy(update={"role": "user", "content": eval_user})],
        gold_labels=training.labels,
    )
    report = audit_eval_isolation([eval_case], [train_case])
    assert report.exact_overlap == 0
    assert report.near_duplicate_pairs >= 1


def test_stratified_smoke_covers_eighty_generated_examples() -> None:
    generated = build_expanded_examples(seed=20260922)
    target_families = {
        "expanded_solution_design",
        "expanded_missing_information",
        "expanded_product_search",
        "expanded_multi_tool",
        "expanded_technical_questions",
        "expanded_contradictory",
        "expanded_failure_abstention",
        "expanded_requirement_change",
    }
    # Select exactly ten rows per family without relying on generated ordering.
    selected = [
        item
        for family_id in sorted(target_families)
        for item in [
            row
            for row in generated
            if row.example.scenario_family_id == family_id
        ][:10]
    ]
    assert len(selected) == 80
    assert validate_generated_semantics(selected) == []
    for item in selected:
        assert not any(
            re.search(r"\('[^\n]*',\)", message.content or "")
            for message in item.example.messages
            if message.role == "user"
        )


def test_search_prompt_renderers_use_only_supplied_constraints() -> None:
    context = context_for(17)
    profile = PERSONA_PROFILES["MANAGER"]
    cases = (
        (search_by_budget_prompt, ProductFilter(product_type=ProductType.AI_SERVER, max_base_price_vnd=180_000_000), ("AI Server", "180 triệu")),
        (search_workstation_ram_prompt, ProductFilter(product_type=ProductType.AI_WORKSTATION, min_ram_gb=768), ("AI Workstation", "768GB RAM")),
        (search_server_gpu_prompt, ProductFilter(product_type=ProductType.AI_SERVER, min_gpu_count=6), ("AI Server", "6 khe GPU")),
        (no_product_found_prompt, ProductFilter(product_type=ProductType.AI_WORKSTATION, min_ram_gb=4096, min_gpu_count=16), ("AI Workstation", "4096GB RAM", "16 khe GPU")),
    )
    for render, constraints, required in cases:
        rendered = render(profile, context, 2, constraints)
        assert all(fragment in rendered.text for fragment in required)
        assert rendered.recipe_id and rendered.recipe_id != "default"


def test_search_rows_share_visible_tool_and_result_constraints() -> None:
    scenarios = {
        ScenarioType.SEARCH_PRODUCT_BY_BUDGET,
        ScenarioType.SEARCH_WORKSTATION_BY_RAM,
        ScenarioType.SEARCH_SERVER_BY_GPU_SLOTS,
        ScenarioType.NO_PRODUCT_FOUND,
    }
    rows = [item for item in build_expanded_examples(seed=20260922) if item.example.labels.scenario_type in scenarios]
    assert {item.example.labels.scenario_type for item in rows} == scenarios
    assert validate_generated_semantics(rows) == []
    for item in rows:
        call = next(call for call in _tool_calls(item) if call.name == "search_products")
        payload = next(payload for payload in _tool_payloads(item) if "products" in (payload.get("data") or {}))
        filters = ProductFilter.model_validate(call.arguments["filters"])
        user = next(message.content or "" for message in reversed(item.example.messages) if message.role == "user")
        final = next(message.content or "" for message in reversed(item.example.messages) if message.role == "assistant" and message.content)
        assert item.wording_recipe_id != item.semantic_template_id
        assert filters.product_type is not None
        assert ("AI Server" if filters.product_type == ProductType.AI_SERVER else "AI Workstation") in user
        if filters.min_ram_gb is not None:
            assert f"{filters.min_ram_gb}GB RAM" in user
        if filters.min_gpu_count is not None:
            assert f"{filters.min_gpu_count} khe GPU" in user
        if filters.max_base_price_vnd is not None:
            assert f"{filters.max_base_price_vnd // 1_000_000} triệu" in user
        if item.example.labels.scenario_type == ScenarioType.NO_PRODUCT_FOUND:
            assert payload["data"]["products"] == []
            assert f"{filters.min_ram_gb}GB RAM" in final
            assert f"{filters.min_gpu_count} khe GPU" in final


def test_search_renderer_and_tool_step_share_the_same_filter() -> None:
    profile = PERSONA_PROFILES["MANAGER"]
    context = context_for(17)
    filters = ProductFilter(product_type=ProductType.AI_SERVER, min_gpu_count=7)
    rendered = search_server_gpu_prompt(profile, context, 0, filters)
    step = _search_step(None, filters)

    assert "7 khe GPU" in rendered.text
    assert step["arguments"]["filters"]["min_gpu_count"] == 7
    assert step["data"] == {"products": [], "total": 0}
    assert rendered.recipe_id == "gpu_constraint_first"


def test_no_product_found_never_constructs_a_product(monkeypatch) -> None:
    family = next(
        item for item in EXPANSION_FAMILY_SPECS
        if item.family_id == "expanded_failure_abstention"
    )
    index = family.scenario_types.index(ScenarioType.NO_PRODUCT_FOUND)
    monkeypatch.setattr(
        "lab1_finetune.data.expansion.generator._product",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unused product")),
    )
    built = _build_failure(
        family, index, 1325, PERSONA_PROFILES["MANAGER"], "medium", multi_turn=False
    )
    assert built.example.labels.should_abstain
    assert _tool_payloads(built)[0]["data"] == {"products": [], "total": 0}


def test_semantic_validation_has_no_presentation_import() -> None:
    tree = ast.parse(inspect.getsource(semantic_validation))
    imports = [
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    ]
    assert not any(module and module.endswith(".wording") for module in imports)


def test_product_search_persona_prefix_has_no_duplicate_role_clause() -> None:
    profile = PERSONA_PROFILES["NON_TECHNICAL_USER"]
    rendered = search_server_gpu_prompt(
        profile,
        context_for(17),
        1,
        ProductFilter(product_type=ProductType.AI_SERVER, min_gpu_count=7),
    )
    assert "mình cần cách giải thích dễ hiểu" not in rendered.text
    assert rendered.text.count("Bạn giải thích dễ hiểu giúp mình") == 1


def test_product_search_recipe_bodies_do_not_repeat_connectors() -> None:
    profile = PERSONA_PROFILES["MANAGER"]
    context = context_for(17)
    cases = (
        (search_workstation_ram_prompt, ProductFilter(product_type=ProductType.AI_WORKSTATION, min_ram_gb=512)),
        (no_product_found_prompt, ProductFilter(product_type=ProductType.AI_SERVER, min_ram_gb=4096, min_gpu_count=16)),
    )
    for render, filters in cases:
        for variant in range(4):
            text = render(profile, context, variant, filters).text
            assert "có có" not in text
            assert "theo điều kiện khả năng" not in text


def test_search_recipe_ids_describe_the_selected_body() -> None:
    profile = PERSONA_PROFILES["MANAGER"]
    context = context_for(17)
    cases = (
        (
            search_workstation_ram_prompt,
            ProductFilter(product_type=ProductType.AI_WORKSTATION, min_ram_gb=512),
            ("ram_constraint_first", "catalog_lookup_first", "use_case_first", "filter_first"),
        ),
        (
            search_server_gpu_prompt,
            ProductFilter(product_type=ProductType.AI_SERVER, min_gpu_count=7),
            ("gpu_constraint_first", "use_case_first", "catalog_filter_first", "filter_first"),
        ),
    )
    for render, filters, expected_ids in cases:
        assert tuple(
            render(profile, context, variant, filters).recipe_id
            for variant in range(4)
        ) == expected_ids


def _mutate_current_user(item, content: str):
    messages = list(item.example.messages)
    index = max(i for i, message in enumerate(messages) if message.role == "user")
    messages[index] = messages[index].model_copy(update={"content": content})
    return replace(item, example=item.example.model_copy(update={"messages": messages}))


def test_comparison_uses_the_same_visible_ids_as_tool_result_and_final() -> None:
    rows = [item for item in build_expanded_examples() if item.family_id == "expanded_comparison"]
    assert rows and validate_generated_semantics(rows) == []
    for item in rows:
        call = _tool_calls(item)[0]
        payload = _tool_payloads(item)[0]["data"]
        user = next(m.content or "" for m in reversed(item.example.messages) if m.role == "user")
        final = item.example.messages[-1].content or ""
        if call.name == "compare_products":
            ids = call.arguments["product_ids"]
            assert "sản phẩm" in user.casefold() and "cấu hình" not in user.casefold()
            assert payload["product_ids"] == ids
        else:
            ids = call.arguments["configuration_ids"]
            assert "cấu hình" in user.casefold() and "hai máy" not in user.casefold()
            assert payload["configuration_ids"] == ids
        assert item.wording_recipe_id in {
            "targets_first", "criteria_first", "decision_first", "evidence_first", "tradeoff_first"
        }
        assert item.wording_recipe_id != item.semantic_template_id
        assert all(value in user and value in final for value in ids)


def test_comparison_semantic_gate_rejects_user_tool_id_drift() -> None:
    generated = build_expanded_examples()
    for scenario, tool_name, id_key, replacement_id in (
        (ScenarioType.COMPARE_PRODUCTS, "compare_products", "product_ids", "SYN-WS-DRIFT"),
        (ScenarioType.COMPARE_CONFIGURATIONS, "compare_configurations", "configuration_ids", "cfg-drift"),
    ):
        item = next(row for row in generated if row.example.labels.scenario_type == scenario)
        ids = next(call for call in _tool_calls(item) if call.name == tool_name).arguments[id_key]
        user = next(m.content or "" for m in reversed(item.example.messages) if m.role == "user")
        mutated = _mutate_current_user(item, user.replace(ids[0], replacement_id))
        assert any("comparison" in error for error in validate_generated_semantics([mutated]))


def test_comparison_prompt_receives_typed_targets_and_returns_named_recipes() -> None:
    profile, context = PERSONA_PROFILES["MANAGER"], context_for(17)
    products = ComparisonSpec("product", ("SYN-WS-001", "SYN-WS-002"))
    configs = ComparisonSpec("configuration", ("cfg-demo-a", "cfg-demo-b"))
    product_prompts = [comparison_prompt(profile, context, n, products) for n in range(10)]
    config_prompts = [comparison_prompt(profile, context, n, configs) for n in range(10)]
    assert len({p.recipe_id for p in product_prompts}) >= 4
    assert len({p.recipe_id for p in config_prompts}) >= 4
    assert all(i in p.text for p in product_prompts for i in products.target_ids)
    assert all("cấu hình" in p.text.casefold() and "hai máy" not in p.text.casefold() for p in config_prompts)


def test_multi_tool_flow_controls_wording_order_ids_and_constraints() -> None:
    expected = {
        "estimate_then_search_v3": ["estimate_ai_requirements", "search_products"],
        "search_then_get_v3": ["search_products", "get_product"],
        "get_then_document_v3": ["get_product", "search_product_documents"],
    }
    rows = [item for item in build_expanded_examples() if item.family_id == "expanded_multi_tool"]
    assert rows and validate_generated_semantics(rows) == []
    assert {item.example.labels.scenario_type.value for item in rows} == {
        "solution_complete",
        "search_workstation_by_ram",
        "technical_max_ram",
    }
    expected_intents = {
        "estimate_then_search_v3": Intent.SOLUTION_DESIGN,
        "search_then_get_v3": Intent.PRODUCT_SEARCH,
        "get_then_document_v3": Intent.TECHNICAL_QUESTION,
    }
    for item in rows:
        assert item.example.labels.intent == expected_intents[item.semantic_template_id]
        calls, payloads = _tool_calls(item), _tool_payloads(item)
        assert [call.name for call in calls] == expected[item.semantic_template_id]
        assert item.wording_recipe_id in {"flow_first", "goal_first", "evidence_first", "decision_first"}
        assert item.wording_recipe_id != item.semantic_template_id
        user = next(m.content or "" for m in reversed(item.example.messages) if m.role == "user")
        if item.semantic_template_id == "estimate_then_search_v3":
            assert "ước tính" in user.casefold() and "tìm" in user.casefold()
            assert calls[1].arguments["filters"]["min_ram_gb"] == payloads[0]["data"]["recommended_system_ram_gb"]
        elif item.semantic_template_id == "search_then_get_v3":
            product = payloads[0]["data"]["products"][0]
            assert calls[1].arguments["product_id"] == product["id"]
            assert product["id"] not in user
            minimum_ram = calls[0].arguments["filters"]["min_ram_gb"]
            assert str(minimum_ram) in user
            assert product["max_ram_gb"] >= minimum_ram
            final = next(m.content or "" for m in reversed(item.example.messages) if m.role == "assistant" and m.content)
            assert str(minimum_ram) in final and str(product["max_ram_gb"]) in final
        else:
            product_id = calls[0].arguments["product_id"]
            assert product_id in user and "tài liệu" in user.casefold()
            assert calls[1].arguments["product_id"] == product_id


def test_estimate_contract_keeps_context_and_concurrency_optional() -> None:
    model = TOOL_ARG_MODELS["estimate_ai_requirements"]
    parsed = model.model_validate({"model_parameters_b": 14, "usage": "inference"})

    assert parsed.context_length is None
    assert parsed.concurrent_users is None


def test_estimate_step_copies_unusual_numeric_values_exactly() -> None:
    context = replace(
        context_for(20260925),
        model_size_b=14.0,
        context_length=9216,
        concurrent_users=13,
    )

    arguments = _estimate_step(context)["arguments"]

    assert arguments["model_parameters_b"] == 14.0
    assert arguments["context_length"] == 9216
    assert arguments["concurrent_users"] == 13


def test_numeric_pools_include_non_benchmark_exact_copy_values() -> None:
    assert {
        6144, 9216, 12288, 14336, 18432, 24576, 28672, 32768
    }.issubset(CONTEXT_LENGTHS)
    assert {3, 7, 13, 17, 23, 31, 47}.issubset(CONCURRENCY)
    assert any(value % 1024 != 0 for value in CONTEXT_LENGTHS)


def test_generated_estimates_copy_context_and_concurrency_from_visible_text() -> None:
    rows = build_expanded_examples(seed=20260922)
    seen_context_lengths = set()
    seen_concurrent_users = set()

    for row in rows:
        estimate = next(
            (call for call in _tool_calls(row) if call.name == "estimate_ai_requirements"),
            None,
        )
        if estimate is None:
            continue
        labels = row.example.labels.extracted_requirement
        visible = " ".join(
            message.content or ""
            for message in row.example.messages
            if message.role == "user"
        ).casefold()
        arguments = estimate.arguments

        assert arguments["context_length"] == labels.context_length
        assert arguments["concurrent_users"] == labels.concurrent_users
        if labels.context_length is not None:
            value = labels.context_length
            seen_context_lengths.add(value)
            assert re.search(
                rf"\b(?:context|ngữ cảnh)(?:\s+(?:length|dài))?\s*(?::|là)?\s*{value}\s+tokens?\b",
                visible,
            )
        if labels.concurrent_users is not None:
            value = labels.concurrent_users
            seen_concurrent_users.add(value)
            patterns = (
                rf"\b{value}\s+(?:người dùng(?: đồng thời)?|người|concurrent users?)\b",
                rf"\b(?:người dùng đồng thời|số người dùng đồng thời|peak concurrency|concurrent users?)\b"
                rf"[^.!?]{{0,40}}\b{value}\b",
            )
            assert any(re.search(pattern, visible) for pattern in patterns)

    assert {6144, 9216, 12288, 14336, 18432, 24576, 28672, 32768} <= seen_context_lengths
    assert {3, 7, 13, 17, 23, 31, 47} <= seen_concurrent_users


def test_estimate_then_search_rows_ground_all_multi_number_arguments() -> None:
    rows = [
        row for row in build_expanded_examples(seed=20260922)
        if row.semantic_template_id == "estimate_then_search_v3"
    ]
    assert len(rows) == 33

    for row in rows:
        calls, payloads = _tool_calls(row), _tool_payloads(row)
        estimate_args = calls[0].arguments
        filters = calls[1].arguments["filters"]
        requirement = row.example.labels.extracted_requirement
        user = " ".join(
            message.content or ""
            for message in row.example.messages
            if message.role == "user"
        )
        product = payloads[1]["data"]["products"][0]

        assert estimate_args["context_length"] == requirement.context_length
        assert estimate_args["concurrent_users"] == requirement.concurrent_users
        assert requirement.context_length is not None
        assert requirement.concurrent_users is not None
        assert estimate_args["model_parameters_b"] == requirement.model_size_b
        assert estimate_args["usage"] == requirement.usage.value
        assert requirement.budget_vnd is not None
        assert filters["max_base_price_vnd"] == requirement.budget_vnd
        assert f"context {estimate_args['context_length']} token" in user
        assert f"{estimate_args['concurrent_users']} người dùng đồng thời" in user
        assert f"{int(requirement.model_size_b)}B" in user
        assert f"{requirement.budget_vnd:,}".replace(",", ".") in user
        assert not re.search(
            rf"\b{filters['min_ram_gb']}\s*GB\s*RAM\b",
            user,
            re.IGNORECASE,
        )
        assert product["max_ram_gb"] >= filters["min_ram_gb"]
        assert product["base_price_vnd"] <= filters["max_base_price_vnd"]
        assert payloads[0]["data"]["recommended_storage_gb"] is None


def test_estimate_then_search_semantic_gate_rejects_mismatched_numeric_target() -> None:
    row = next(
        item for item in build_expanded_examples(seed=20260922)
        if item.semantic_template_id == "estimate_then_search_v3"
    )
    messages = list(row.example.messages)
    index = next(
        i for i, message in enumerate(messages)
        if any(call.name == "estimate_ai_requirements" for call in message.tool_calls)
    )
    message = messages[index]
    actual_context_length = next(
        call.arguments["context_length"]
        for call in message.tool_calls
        if call.name == "estimate_ai_requirements"
    )
    calls = [
        call.model_copy(update={"arguments": {**call.arguments, "context_length": actual_context_length + 1}})
        if call.name == "estimate_ai_requirements"
        else call
        for call in message.tool_calls
    ]
    messages[index] = message.model_copy(update={"tool_calls": calls})
    mutated = replace(row, example=row.example.model_copy(update={"messages": messages}))

    assert any("multi-tool" in error for error in validate_generated_semantics([mutated]))

    user = next(message.content or "" for message in reversed(row.example.messages) if message.role == "user")
    mutated_conversation = _mutate_current_user(
        row,
        user.replace(
            f"context {actual_context_length} token",
            "context 9999 token",
            1,
        ),
    )
    assert any("multi-tool" in error for error in validate_generated_semantics([mutated_conversation]))


def test_estimate_ram_recommendation_must_not_leak_into_user_prompt() -> None:
    row = next(
        item for item in build_expanded_examples(seed=20260922)
        if item.semantic_template_id == "estimate_then_search_v3"
    )
    recommended_ram = _tool_calls(row)[1].arguments["filters"]["min_ram_gb"]
    user = next(
        message.content or ""
        for message in reversed(row.example.messages)
        if message.role == "user"
    )
    mutated = _mutate_current_user(
        row,
        user + f" Hãy tìm máy có ít nhất {recommended_ram}GB RAM.",
    )
    assert any(
        "RAM recommendation leaks" in error
        for error in validate_generated_semantics([mutated])
    )


def test_assistant_echo_cannot_ground_user_supplied_multi_tool_values() -> None:
    row = next(
        item for item in build_expanded_examples(seed=20260922)
        if item.semantic_template_id == "estimate_then_search_v3"
    )
    requirement = row.example.labels.extracted_requirement
    messages = list(row.example.messages)
    last_user_index = max(
        index for index, message in enumerate(messages) if message.role == "user"
    )
    assistant_echo = (
        f"The assistant echoed context {requirement.context_length} token and "
        f"{requirement.concurrent_users} ngu?i dùng đồng thời."
    )
    rewritten = []
    for message in messages:
        content = message.content or ""
        if message.role == "user":
            content = re.sub(
                rf"context\s+{requirement.context_length}\s+tokens?",
                "context length chưa rõ",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                rf"\b{requirement.concurrent_users}\s+người dùng đồng thời\b",
                "quy mô người dùng chưa rõ",
                content,
                flags=re.IGNORECASE,
            )
            message = message.model_copy(update={"content": content})
        rewritten.append(message)
    rewritten.insert(
        last_user_index,
        rewritten[0].model_copy(update={"role": "assistant", "content": assistant_echo}),
    )
    mutated = replace(
        row,
        example=row.example.model_copy(update={"messages": rewritten}),
    )

    errors = validate_generated_semantics([mutated])
    assert any("context length is absent" in error for error in errors)
    assert any("concurrency is absent" in error for error in errors)


def test_multi_tool_semantic_gate_rejects_wording_for_a_different_flow() -> None:
    item = next(row for row in build_expanded_examples() if row.semantic_template_id == "get_then_document_v3")
    mutated = _mutate_current_user(item, "Ước tính tài nguyên trước rồi tìm sản phẩm phù hợp.")
    assert any("multi-tool" in error for error in validate_generated_semantics([mutated]))


def test_multi_tool_semantic_gate_rejects_wrong_intent_label() -> None:
    item = next(row for row in build_expanded_examples() if row.semantic_template_id == "estimate_then_search_v3")
    bad_labels = item.example.labels.model_copy(update={"intent": Intent.PRODUCT_SEARCH})
    bad_example = item.example.model_copy(update={"labels": bad_labels})
    mutated = replace(item, example=bad_example)
    assert any("intent category" in error for error in validate_generated_semantics([mutated]))


def test_multi_tool_renderer_is_driven_by_flow_spec() -> None:
    flow = MultiToolFlowSpec(
        MultiToolFlow.GET_THEN_DOCUMENT, "SYN-SRV-001", ProductType.AI_SERVER,
        document_field="max_ram_gb",
    )
    prompts = [multi_tool_prompt(PERSONA_PROFILES["MANAGER"], context_for(17), n, flow) for n in range(8)]
    assert len({p.recipe_id for p in prompts}) >= 3
    assert all("SYN-SRV-001" in p.text and "tài liệu" in p.text.casefold() for p in prompts)
    assert all("ước tính" not in p.text.casefold() for p in prompts)


def test_technical_rows_are_scenario_aware_and_ground_product_facts() -> None:
    rows = [item for item in build_expanded_examples() if item.family_id == "expanded_technical_questions"]
    assert rows and validate_generated_semantics(rows) == []
    expected = {
        ScenarioType.GENERAL_VRAM: {"context_effect", "kv_cache_reasoning", "memory_growth", "concurrency_context"},
        ScenarioType.GENERAL_INFERENCE: {"definition_first", "training_contrast", "weight_update_contrast", "serving_first"},
        ScenarioType.TECHNICAL_MAX_RAM: {"product_first", "field_first", "evidence_first", "decision_first"},
        ScenarioType.TECHNICAL_MAX_GPU: {"product_first", "field_first", "evidence_first", "decision_first"},
        ScenarioType.UNKNOWN_PRODUCT_SPEC: {"product_first", "field_first", "evidence_first", "decision_first"},
    }
    for scenario, recipes in expected.items():
        selected = [r for r in rows if r.example.labels.scenario_type == scenario]
        assert selected and {r.wording_recipe_id for r in selected} == recipes
        assert all(r.wording_recipe_id != r.semantic_template_id for r in selected)
    for item in rows:
        scenario = item.example.labels.scenario_type
        if scenario not in {ScenarioType.TECHNICAL_MAX_RAM, ScenarioType.TECHNICAL_MAX_GPU, ScenarioType.UNKNOWN_PRODUCT_SPEC}:
            continue
        call, result = _tool_calls(item)[0], _tool_payloads(item)[0]
        user = next(
            message.content or ""
            for message in reversed(item.example.messages)
            if message.role == "user"
        )
        final = item.example.messages[-1].content or ""
        product_id = call.arguments["product_id"]
        assert product_id in user and product_id in final
        field = "max_ram_gb" if scenario == ScenarioType.TECHNICAL_MAX_RAM else "max_gpu_slots"
        query = call.arguments["query"].casefold()
        assert ("ram" if field == "max_ram_gb" else "khe gpu") in query
        if scenario == ScenarioType.UNKNOWN_PRODUCT_SPEC:
            assert result["data"]["hits"] == [] and item.example.labels.should_abstain
        else:
            hit = result["data"]["hits"][0]["chunk"]
            assert hit["product_id"] == product_id and hit["metadata"]["field_name"] == field


def test_technical_semantic_gate_rejects_inference_vram_mismatch() -> None:
    item = next(row for row in build_expanded_examples() if row.example.labels.scenario_type == ScenarioType.GENERAL_INFERENCE)
    mutated = _mutate_current_user(item, "Why does increasing context raise VRAM use?")
    assert any("general_inference" in error for error in validate_generated_semantics([mutated]))


def test_general_vram_answers_cover_concurrent_sessions_when_asked() -> None:
    rows = [
        row for row in build_expanded_examples()
        if row.example.labels.scenario_type == ScenarioType.GENERAL_VRAM
        and row.wording_recipe_id in {"kv_cache_reasoning", "memory_growth", "concurrency_context"}
    ]
    assert rows
    assert all(validate_generated_semantics([row]) == [] for row in rows)
    for row in rows:
        final = (row.example.messages[-1].content or "").casefold()
        assert "kv cache" in final
        assert any(term in final for term in ("phiên", "yêu cầu đồng thời", "người dùng đồng thời"))


def test_general_vram_gate_rejects_omitted_concurrency_answer() -> None:
    row = next(
        row for row in build_expanded_examples()
        if row.example.labels.scenario_type == ScenarioType.GENERAL_VRAM
        and row.wording_recipe_id == "concurrency_context"
    )
    messages = list(row.example.messages)
    messages[-1] = messages[-1].model_copy(update={
        "content": "Context dài làm KV cache tăng và cần thêm VRAM."
    })
    mutated = replace(row, example=row.example.model_copy(update={"messages": messages}))
    assert any("concurrent" in error for error in validate_generated_semantics([mutated]))


@pytest.mark.parametrize(
    ("recipe_id", "incomplete_final"),
    [
        ("concurrency_context", "KV cache của mỗi phiên cần VRAM."),
        ("context_effect", "VRAM là bộ nhớ của GPU."),
        ("context_effect", "Context dài làm KV cache lớn hơn nhưng VRAM không đổi."),
    ],
)
def test_general_vram_gate_rejects_keyword_only_answers(
    recipe_id: str, incomplete_final: str
) -> None:
    row = next(
        row for row in build_expanded_examples()
        if row.example.labels.scenario_type == ScenarioType.GENERAL_VRAM
        and row.wording_recipe_id == recipe_id
    )
    messages = list(row.example.messages)
    messages[-1] = messages[-1].model_copy(update={"content": incomplete_final})
    mutated = replace(row, example=row.example.model_copy(update={"messages": messages}))
    assert any("general_vram" in error for error in validate_generated_semantics([mutated]))


def test_technical_prompt_requires_scenario_and_product_fact_spec() -> None:
    profile, context = PERSONA_PROFILES["MANAGER"], context_for(17)
    vram = [technical_prompt(profile, context, n, ScenarioType.GENERAL_VRAM) for n in range(8)]
    inference = [technical_prompt(profile, context, n, ScenarioType.GENERAL_INFERENCE) for n in range(8)]
    fact = TechnicalFactSpec("SYN-WS-001", "max_ram_gb")
    ram = [technical_prompt(profile, context, n, ScenarioType.TECHNICAL_MAX_RAM, fact=fact) for n in range(8)]
    assert len({p.recipe_id for p in vram}) == len({p.recipe_id for p in inference}) == 4
    assert len({p.recipe_id for p in ram}) == 4
    assert all("inference" not in p.text.casefold() for p in vram)
    assert all("vram" not in p.text.casefold() for p in inference)
    assert all("SYN-WS-001" in p.text and "RAM" in p.text for p in ram)


def test_requirement_change_templates_follow_actual_old_new_delta() -> None:
    rows = [row for row in build_expanded_examples() if row.family_id == "expanded_requirement_change"]
    expected = {
        frozenset({"model_size_b"}): "requirement_change_model_v3",
        frozenset({"usage"}): "requirement_change_usage_v3",
        frozenset({"budget_vnd"}): "requirement_change_budget_v3",
        frozenset({"model_size_b", "concurrent_users"}): "requirement_change_multiple_v3",
    }
    assert len(rows) == 80
    assert {row.semantic_template_id for row in rows} == set(expected.values())
    for row in rows:
        spec = row.semantic_spec
        assert spec is not None
        assert spec.changed_fields == frozenset(
            field for field in ("model_size_b", "usage", "budget_vnd", "concurrent_users")
            if getattr(spec.old, field) != getattr(spec.new, field)
        )
        assert row.semantic_template_id == expected[spec.changed_fields]
        assert row.wording_recipe_id != row.semantic_template_id
        labels = row.example.labels.extracted_requirement
        call = _tool_calls(row)[0]
        assert call.arguments["model_parameters_b"] == labels.model_size_b == spec.new.model_size_b
        assert call.arguments["usage"] == labels.usage.value == spec.new.usage.value
        assert labels.budget_vnd == spec.new.budget_vnd
        assert labels.concurrent_users == spec.new.concurrent_users
        assert call.arguments.get("training_method") == labels.training_method
    assert validate_generated_semantics(rows) == []


def test_requirement_change_gate_rejects_template_and_wording_mutations() -> None:
    row = next(row for row in build_expanded_examples() if row.semantic_template_id == "requirement_change_budget_v3")
    assert any("requirement change" in error for error in validate_generated_semantics([
        replace(row, semantic_template_id="requirement_change_model_v3")
    ]))
    mutated = _mutate_current_user(row, "Kế hoạch không đổi, cứ tính như cũ.")
    assert any("requirement change" in error for error in validate_generated_semantics([mutated]))


def test_contradictory_family_has_real_constraints_and_safe_response() -> None:
    rows = [row for row in build_expanded_examples() if row.family_id == "expanded_contradictory"]
    assert len(rows) == 60
    assert {row.semantic_template_id for row in rows} == {
        "contradiction_single_gpu_v3", "contradiction_context_vram_v3",
        "contradiction_low_budget_v3",
    }
    for row in rows:
        spec = row.semantic_spec
        assert spec is not None
        assert row.example.labels.should_abstain
        assert row.wording_recipe_id != row.semantic_template_id
        user = next(m.content or "" for m in reversed(row.example.messages) if m.role == "user")
        final = row.example.messages[-1].content or ""
        if spec.subtype == "large_model_low_budget":
            req = row.example.labels.extracted_requirement
            assert req.model_size_b >= 32 and req.budget_vnd <= 240_000_000
            assert str(req.budget_vnd // 1_000_000) in user
            assert "giá" in final.casefold() or "ngân sách" in final.casefold()
        else:
            assert str(spec.gpu_memory_gb) in user
            assert str(int(spec.context.model_size_b)) in user
            assert "GPU" in final
    assert validate_generated_semantics(rows) == []


def test_contradiction_gate_rejects_missing_constraint() -> None:
    row = next(row for row in build_expanded_examples() if row.semantic_template_id == "contradiction_single_gpu_v3")
    mutated = _mutate_current_user(row, "Tư vấn cấu hình AI bình thường cho bên mình.")
    assert any("contradiction" in error for error in validate_generated_semantics([mutated]))


def test_contradiction_gate_rejects_wrong_low_budget_estimate() -> None:
    row = next(row for row in build_expanded_examples() if row.semantic_template_id == "contradiction_low_budget_v3")
    call = _tool_calls(row)[0]
    bad_call = call.model_copy(update={
        "arguments": {**call.arguments, "model_parameters_b": 8.0}
    })
    messages = [
        message.model_copy(update={"tool_calls": [bad_call]})
        if call in message.tool_calls else message
        for message in row.example.messages
    ]
    mutated = replace(row, example=row.example.model_copy(update={"messages": messages}))
    assert any("contradiction estimate" in error for error in validate_generated_semantics([mutated]))


def test_lora_user_tool_and_labels_match_scenario() -> None:
    rows = [row for row in build_expanded_examples() if row.family_id == "expanded_lora_inference"]
    assert len(rows) == 80
    for row in rows:
        labels = row.example.labels
        user = next(m.content or "" for m in reversed(row.example.messages) if m.role == "user")
        assert row.wording_recipe_id != row.semantic_template_id
        assert "LoRA" in user
        if labels.scenario_type == ScenarioType.GENERAL_LORA:
            assert not labels.should_call_tool
            assert not _tool_calls(row)
        else:
            call = _tool_calls(row)[0]
            assert call.name == "estimate_ai_requirements"
            assert call.arguments["usage"] == "fine_tune"
            assert call.arguments["training_method"] == "LoRA"
            assert call.arguments["model_parameters_b"] == labels.extracted_requirement.model_size_b
            assert labels.extracted_requirement.usage.value == "fine_tune"
            assert labels.extracted_requirement.training_method == "LoRA"
            if labels.scenario_type == ScenarioType.FINETUNE_32B_SOLUTION:
                assert labels.extracted_requirement.model_size_b >= 32
    assert validate_generated_semantics(rows) == []


def test_lora_gate_rejects_wrong_estimate_usage() -> None:
    row = next(row for row in build_expanded_examples() if row.example.labels.scenario_type == ScenarioType.FINETUNE_32B_SOLUTION)
    call = _tool_calls(row)[0]
    bad_call = call.model_copy(update={"arguments": {**call.arguments, "usage": "inference"}})
    messages = [m.model_copy(update={"tool_calls": [bad_call]}) if call in m.tool_calls else m for m in row.example.messages]
    mutated = replace(row, example=row.example.model_copy(update={"messages": messages}))
    assert any("LoRA" in error for error in validate_generated_semantics([mutated]))
