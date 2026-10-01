"""Lab 2 contract extensions must not change frozen Lab 1 generation."""

import json
from pathlib import Path

from lab1_finetune.data.build_expanded import _content_hash
from lab1_finetune.data.expansion.generator import build_expanded_examples
from lab1_finetune.data.frozen_contracts import TOOL_ARG_MODELS
from lab1_finetune.evaluation.benchmark import (
    benchmark_content_hash,
    build_independent_eval_records,
)


def test_expansion_matches_frozen_content_hash() -> None:
    manifest_path = Path(__file__).parents[1] / "data/generated/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    examples = [item.example for item in build_expanded_examples(seed=manifest["seed"])]
    assert _content_hash(examples) == manifest["content_hash"]


def test_expansion_keeps_frozen_search_tool_schema() -> None:
    examples = build_expanded_examples()
    search = next(tool for tool in examples[0].example.tools if tool.name == "search_products")
    fields = search.parameters["$defs"]["ProductFilter"]["properties"]
    assert set(fields) == {"min_ram_gb", "min_gpu_count", "max_base_price_vnd", "product_type"}
    assert search.parameters["$defs"]["ProductType"]["enum"] == [
        "ai_server", "ai_workstation"
    ]


def test_all_six_lab1_argument_models_are_locally_pinned() -> None:
    from shared.tool_args import TOOL_ARG_MODELS as runtime_models

    expected = {
        "search_products",
        "get_product",
        "search_product_documents",
        "compare_products",
        "compare_configurations",
        "estimate_ai_requirements",
    }
    assert set(TOOL_ARG_MODELS) == expected
    assert all(TOOL_ARG_MODELS[name] is not runtime_models[name] for name in expected)


def test_runtime_contract_replacements_do_not_change_lab1_builds(monkeypatch) -> None:
    from shared import contracts, tool_args, tool_contracts

    generated_before = _content_hash(
        [item.example for item in build_expanded_examples(seed=20260922)]
    )
    eval_before = benchmark_content_hash(build_independent_eval_records(seed=20260923))

    class RuntimeOnlyContract:
        @classmethod
        def model_validate(cls, *_args, **_kwargs):
            raise AssertionError("Lab 1 must not call a runtime shared contract")

    monkeypatch.setattr(
        tool_args,
        "TOOL_ARG_MODELS",
        {name: RuntimeOnlyContract for name in TOOL_ARG_MODELS},
    )
    monkeypatch.setattr(
        tool_contracts,
        "TOOL_DEFINITIONS",
        [RuntimeOnlyContract],
    )
    monkeypatch.setattr(contracts, "ProductType", RuntimeOnlyContract, raising=False)
    monkeypatch.setattr(contracts, "UsageType", RuntimeOnlyContract, raising=False)

    generated_after = _content_hash(
        [item.example for item in build_expanded_examples(seed=20260922)]
    )
    eval_after = benchmark_content_hash(build_independent_eval_records(seed=20260923))
    assert generated_after == generated_before
    assert eval_after == eval_before


def test_lab1_runtime_modules_do_not_import_shared_wire_contracts() -> None:
    root = Path(__file__).parents[1]
    allowed = {root / "training/config.py"}
    violations = []
    for path in root.rglob("*.py"):
        if path.parent.name == "tests" or path in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        if "from shared.contracts" in source or "from shared.tool_args" in source:
            violations.append(path.relative_to(root).as_posix())
    assert violations == []


def test_evaluation_matches_frozen_content_hash() -> None:
    manifest_path = Path(__file__).parents[1] / "evaluation/eval_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = build_independent_eval_records(seed=manifest["seed"])
    assert benchmark_content_hash(records) == manifest["content_hash"]
