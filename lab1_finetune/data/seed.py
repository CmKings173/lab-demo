from __future__ import annotations

import json

from lab1_finetune.data.schema import DatasetLabels, FineTuneExample
from shared.contracts import ChatMessage, ToolCall
from shared.tool_contracts import TOOL_DEFINITIONS

_FAMILIES = [
    ("complete_solution", "Complete configuration request", "vi", "search_products", []),
    ("missing_budget", "Request missing a budget", "vi", None, ["budget_vnd"]),
    ("missing_usage", "Request missing intended usage", "vi", None, ["usage"]),
    ("missing_model_size", "Request missing model size", "vi", None, ["model_size_b"]),
    (
        "several_missing_fields",
        "Request missing several required fields",
        "vi",
        None,
        ["usage", "budget_vnd"],
    ),
    ("product_search", "Direct product platform search", "en", "search_products", []),
    ("product_comparison", "Compare known product platforms", "en", "compare_products", []),
    (
        "technical_question",
        "Technical question grounded in documents",
        "en",
        "search_product_documents",
        [],
    ),
    ("general_ai_question", "General AI question without catalog facts", "en", None, []),
    ("no_tool_case", "Simple greeting that needs no tool", "vi", None, []),
    ("correct_tool_case", "Fetch one known product by id", "en", "get_product", []),
    ("tool_result_empty", "Catalog search returns no products", "en", "search_products", []),
    (
        "tool_result_unknown_field",
        "Product result contains unknown fields",
        "en",
        "get_product",
        [],
    ),
    ("tool_failure", "Catalog tool reports a controlled failure", "en", "search_products", []),
    ("out_of_scope", "Request falls outside AI configuration scope", "vi", None, []),
    ("ambiguous_request", "Request is ambiguous and needs clarification", "vi", None, ["usage"]),
    ("contradictory_request", "Request contains contradictory constraints", "en", None, []),
    ("vietnamese_request", "Vietnamese sizing request", "vi", "estimate_ai_requirements", []),
    (
        "mixed_language_request",
        "Mixed Vietnamese and English request",
        "mixed",
        "search_products",
        [],
    ),
    ("english_request", "English sizing request", "en", "estimate_ai_requirements", []),
]


def _tool_arguments(tool_name: str) -> dict[str, object]:
    return {
        "search_products": {"filters": {"product_type": "ai_server"}},
        "get_product": {"product_id": "example-product"},
        "search_product_documents": {
            "query": "GPU memory support",
            "product_id": "example-product",
        },
        "compare_products": {"product_ids": ["example-a", "example-b"]},
        "estimate_ai_requirements": {
            "model_parameters_b": 32,
            "usage": "inference",
        },
    }[tool_name]


def build_seed_examples() -> list[FineTuneExample]:
    examples: list[FineTuneExample] = []
    for family_id, summary, language, tool_name, missing_fields in _FAMILIES:
        for variant in range(2):
            messages = [
                ChatMessage(
                    role="system",
                    content="Use shared tools when needed and never invent product facts.",
                ),
                ChatMessage(
                    role="user",
                    content=f"{summary}. Review variant {variant + 1}.",
                ),
            ]
            if tool_name:
                call_id = f"{family_id}-call-{variant + 1}"
                messages.extend(
                    [
                        ChatMessage(
                            role="assistant",
                            tool_calls=[
                                ToolCall(
                                    id=call_id,
                                    name=tool_name,
                                    arguments=_tool_arguments(tool_name),
                                )
                            ],
                        ),
                        ChatMessage(
                            role="tool",
                            tool_call_id=call_id,
                            content=json.dumps(
                                {"ok": family_id != "tool_failure", "data": []}
                            ),
                        ),
                        ChatMessage(
                            role="assistant",
                            content="I will only report facts present in the tool result.",
                        ),
                    ]
                )
            else:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content="I will clarify or answer without inventing catalog facts.",
                    )
                )
            examples.append(
                FineTuneExample(
                    example_id=f"{family_id}-{variant + 1}",
                    scenario_family_id=family_id,
                    scenario_summary=summary,
                    task_type="tool_calling" if tool_name else "conversation",
                    difficulty="medium",
                    language=language,
                    source_type="synthetic_reviewed",
                    messages=messages,
                    tools=TOOL_DEFINITIONS if tool_name else [],
                    labels=DatasetLabels(
                        intent=family_id,
                        missing_fields=missing_fields,
                        should_call_tool=tool_name is not None,
                        expected_tool=tool_name,
                        must_not_invent_product_fact=True,
                    ),
                )
            )
    return examples


__all__ = ["build_seed_examples"]
