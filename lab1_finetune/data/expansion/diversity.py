# ruff: noqa: E501

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

from lab1_finetune.data.expansion.generator import GeneratedExample
from lab1_finetune.data.expansion.semantic_validation import validate_generated_semantics
from lab1_finetune.data.expansion.spec import NEAR_DUPLICATE_THRESHOLD
from lab1_finetune.data.schema import FineTuneExample
from lab1_finetune.data.similarity import near_duplicate_stats
from lab1_finetune.data.validator import DatasetValidator

LEGACY_TERMS = ("budget", "sizing", "workload", "catalog", "giá nền")
PRODUCT_ID_PATTERN = re.compile(r"SYN-(?:WS|SRV)-\d+")
PYTHON_REPR_PATTERN = re.compile(r"(?:\('[^\n]*',\)|\[[^\n]*\]|\{[^\n]*\})")


@dataclass(frozen=True)
class DiversityReport:
    example_count: int
    family_counts: dict[str, int]
    persona_counts: dict[str, int]
    difficulty_counts: dict[str, int]
    turn_counts: dict[str, int]
    tool_pattern_counts: dict[str, int]
    exact_duplicates: int
    near_duplicate_pairs: int
    near_duplicate_rate: float
    exact_user_duplicates: int = 0
    exact_history_user_duplicates: int = 0
    exact_final_duplicates: int = 0
    exact_conversation_duplicates: int = 0
    near_user_duplicate_pairs: int = 0
    near_history_user_pairs: int = 0
    near_conversation_duplicate_pairs: int = 0
    near_user_duplicate_example_ratio: float = 0.0
    near_history_user_example_ratio: float = 0.0
    near_conversation_duplicate_example_ratio: float = 0.0
    legacy_term_hits: list[str] = field(default_factory=list)
    unsupported_product_claims: list[str] = field(default_factory=list)
    validator_errors: list[str] = field(default_factory=list)
    label_text_errors: list[str] = field(default_factory=list)
    semantic_errors: list[str] = field(default_factory=list)
    python_repr_errors: list[str] = field(default_factory=list)
    encoding_errors: list[str] = field(default_factory=list)
    final_unique_count: int = 0
    final_duplicate_ratio: float = 0.0

    @property
    def valid(self) -> bool:
        return not (
            self.exact_user_duplicates
            or self.exact_conversation_duplicates
            or self.legacy_term_hits
            or self.unsupported_product_claims
            or self.validator_errors
            or self.label_text_errors
            or self.semantic_errors
            or self.python_repr_errors
            or self.encoding_errors
        )


def _unwrap(item: GeneratedExample | FineTuneExample) -> tuple[FineTuneExample, str]:
    if isinstance(item, GeneratedExample):
        return item.example, item.persona
    return item, "UNSPECIFIED"


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _tool_pattern(example: FineTuneExample) -> str:
    calls = [call for message in example.messages for call in message.tool_calls]
    if not calls:
        return "no_tool"
    tool_messages = [message for message in example.messages if message.role == "tool"]
    if any(not json.loads(message.content or "{}").get("ok", True) for message in tool_messages):
        return "failure"
    return "single_tool" if len(calls) == 1 else "multi_tool"


def _unsupported_product_claims(example: FineTuneExample) -> list[str]:
    available = {
        product_id
        for message in example.messages
        if message.role == "tool"
        for product_id in PRODUCT_ID_PATTERN.findall(message.content or "")
    }
    # A failed/empty document result may not echo the requested product ID;
    # referencing that ID is still grounded when it came from the validated
    # tool arguments, without authorizing any unreturned technical fact.
    available.update(
        str(call.arguments.get("product_id"))
        for message in example.messages
        if message.role == "assistant"
        for call in message.tool_calls
        if isinstance(call.arguments, dict)
        and PRODUCT_ID_PATTERN.fullmatch(str(call.arguments.get("product_id", "")))
    )
    claimed = {
        product_id
        for message in example.messages
        if message.role == "assistant"
        for product_id in PRODUCT_ID_PATTERN.findall(message.content or "")
    }
    return sorted(claimed - available)



# The following helpers keep duplicate dimensions explicit.  They intentionally
# replace the legacy all-message fingerprint used by the original audit above.
def _normalized_user_text_v2(example: FineTuneExample) -> str:
    """Fingerprint the current user turn; history is audited separately."""
    return _normalize(
        next(
            (message.content or "" for message in reversed(example.messages) if message.role == "user"),
            "",
        )
    )


def _normalized_history_plus_user_v2(example: FineTuneExample) -> str:
    messages = example.messages[:-1] if example.messages and example.messages[-1].role == "assistant" else example.messages
    return _normalize(
        "\n".join(
            message.content or ""
            for message in messages
            if message.role in {"user", "assistant"}
        )
    )


def _normalized_final_v2(example: FineTuneExample) -> str:
    return _normalize(
        next(
            (message.content or "" for message in reversed(example.messages) if message.role == "assistant"),
            "",
        )
    )


def _normalized_full_conversation_v2(example: FineTuneExample) -> str:
    return _normalize(
        "\n".join(
            f"{message.role}:{message.content or ''}:{[call.name for call in message.tool_calls]}"
            for message in example.messages
        )
    )


def _label_text_consistency_errors(examples: Sequence[FineTuneExample]) -> list[str]:
    """Reject generated rows whose visible wording contradicts extracted usage."""
    errors: list[str] = []
    fine_tune_terms = ("fine-tune", "fine tune", "lora", "tinh chỉnh", "huấn luyện")
    for example in examples:
        if example.labels.extracted_requirement.usage == "fine_tune":
            visible = "\n".join(
                message.content or ""
                for message in example.messages
                if message.role in {"user", "assistant"}
            ).casefold()
            if not any(term in visible for term in fine_tune_terms):
                errors.append(
                    f"{example.example_id}:fine_tune label has no matching visible wording"
                )
    return errors


def find_encoding_errors(examples: Sequence[FineTuneExample]) -> list[str]:
    """Find replacement characters in user-facing dataset messages."""
    return [
        f"{example.example_id}:{message.role}:replacement_character"
        for example in examples
        for message in example.messages
        if message.role in {"user", "assistant"} and "\ufffd" in (message.content or "")
    ]


def _near_duplicate_stats_v2(
    texts: Sequence[str],
    threshold: float,
    groups: Sequence[str] | None = None,
) -> tuple[int, float]:
    # Retain the legacy argument for callers; groups never suppress lexical pairs.
    del groups
    return near_duplicate_stats(texts, threshold)


def audit_examples(
    items: Sequence[GeneratedExample | FineTuneExample],
    *,
    near_duplicate_threshold: float = NEAR_DUPLICATE_THRESHOLD,
) -> DiversityReport:
    examples = [_unwrap(item)[0] for item in items]
    personas = [_unwrap(item)[1] for item in items]
    users = [_normalized_user_text_v2(example) for example in examples]
    history_users = [_normalized_history_plus_user_v2(example) for example in examples]
    finals = [_normalized_final_v2(example) for example in examples]
    conversations = [_normalized_full_conversation_v2(example) for example in examples]
    near_user_pairs, near_user_ratio = _near_duplicate_stats_v2(users, near_duplicate_threshold)
    near_history_pairs, near_history_ratio = _near_duplicate_stats_v2(history_users, near_duplicate_threshold)
    near_conversation_pairs, near_conversation_ratio = _near_duplicate_stats_v2(conversations, near_duplicate_threshold)
    user_facing = "\n".join(
        message.content or ""
        for example in examples
        for message in example.messages
        if message.role in {"user", "assistant"}
    ).casefold()
    legacy_hits = [term for term in LEGACY_TERMS if term in user_facing]
    python_repr_errors = [
        f"{example.example_id}:python_repr"
        for example in examples
        for message in example.messages
        if message.role == "user" and PYTHON_REPR_PATTERN.search(message.content or "")
    ]
    validator_errors = DatasetValidator().validate(examples).errors
    semantic_errors = validate_generated_semantics(items)
    unsupported = [
        f"{example.example_id}:{product_id}"
        for example in examples
        for product_id in _unsupported_product_claims(example)
    ]
    possible_pairs = len(examples) * (len(examples) - 1) // 2
    return DiversityReport(
        example_count=len(examples),
        family_counts=dict(Counter(example.scenario_family_id for example in examples)),
        persona_counts=dict(Counter(personas)),
        difficulty_counts=dict(Counter(example.difficulty for example in examples)),
        turn_counts=dict(
            Counter(
                "multi_turn"
                if sum(message.role == "user" for message in example.messages) > 1
                else "single_turn"
                for example in examples
            )
        ),
        tool_pattern_counts=dict(Counter(_tool_pattern(example) for example in examples)),
        exact_duplicates=len(conversations) - len(set(conversations)),
        near_duplicate_pairs=near_conversation_pairs,
        near_duplicate_rate=near_conversation_pairs / possible_pairs if possible_pairs else 0.0,
        exact_user_duplicates=len(users) - len(set(users)),
        exact_history_user_duplicates=len(history_users) - len(set(history_users)),
        exact_final_duplicates=len(finals) - len(set(finals)),
        exact_conversation_duplicates=len(conversations) - len(set(conversations)),
        near_user_duplicate_pairs=near_user_pairs,
        near_history_user_pairs=near_history_pairs,
        near_conversation_duplicate_pairs=near_conversation_pairs,
        near_user_duplicate_example_ratio=near_user_ratio,
        near_history_user_example_ratio=near_history_ratio,
        near_conversation_duplicate_example_ratio=near_conversation_ratio,
        legacy_term_hits=legacy_hits,
        unsupported_product_claims=unsupported,
        validator_errors=validator_errors,
        label_text_errors=_label_text_consistency_errors(examples),
        semantic_errors=semantic_errors,
        python_repr_errors=python_repr_errors,
        encoding_errors=find_encoding_errors(examples),
        final_unique_count=len(set(finals)),
        final_duplicate_ratio=(len(finals) - len(set(finals))) / len(finals) if finals else 0.0,
    )
