from __future__ import annotations

import json
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

from pydantic import ValidationError

from lab1_finetune.data.fixtures.tool_results import TOOL_RESULT_MODELS
from lab1_finetune.data.schema import (
    DatasetSplit,
    DatasetValidationReport,
    FineTuneExample,
)
from lab1_finetune.data.statistics import build_manifest
from shared.contracts import ToolDefinition
from shared.tool_args import TOOL_ARG_MODELS


class DatasetValidator:
    def validate_records(self, records: Sequence[dict[str, Any]]) -> DatasetValidationReport:
        """Validate untrusted serialized records without failing on the first schema error."""
        examples: list[FineTuneExample] = []
        errors: list[str] = []
        for index, record in enumerate(records):
            try:
                examples.append(FineTuneExample.model_validate(record))
            except ValidationError as exc:
                for issue in exc.errors(include_url=False):
                    location = ".".join(str(part) for part in issue["loc"])
                    errors.append(f"record {index}.{location}: {issue['msg']}")
        semantic = self.validate(examples)
        errors.extend(semantic.errors)
        return DatasetValidationReport(
            valid=not errors,
            errors=errors,
            manifest=semantic.manifest,
        )

    def validate(self, examples: Sequence[FineTuneExample]) -> DatasetValidationReport:
        items = list(examples)
        errors: list[str] = []
        ids: set[str] = set()
        family_summaries: dict[str, str] = {}
        summary_families: dict[str, str] = {}
        for example in items:
            if example.example_id in ids:
                errors.append(f"duplicate example_id: {example.example_id}")
            ids.add(example.example_id)
            normalized_summary = " ".join(example.scenario_summary.casefold().split())
            is_new_family = example.scenario_family_id not in family_summaries
            previous_summary = family_summaries.setdefault(
                example.scenario_family_id, normalized_summary
            )
            if previous_summary != normalized_summary:
                errors.append(
                    f"inconsistent family metadata: {example.scenario_family_id}"
                )
            if is_new_family:
                near_duplicate = next(
                    (
                        family_id
                        for summary, family_id in summary_families.items()
                        if family_id != example.scenario_family_id
                        and SequenceMatcher(None, summary, normalized_summary).ratio() >= 0.9
                    ),
                    None,
                )
                if near_duplicate is not None:
                    errors.append(
                        "duplicate or near-duplicate family metadata: "
                        f"{near_duplicate} and {example.scenario_family_id}"
                    )
            summary_families.setdefault(normalized_summary, example.scenario_family_id)
            errors.extend(self._validate_example(example))
        manifest = build_manifest(items)
        return DatasetValidationReport(valid=not errors, errors=errors, manifest=manifest)

    def validate_split(self, split: DatasetSplit) -> DatasetValidationReport:
        partitions = {
            "train": split.train,
            "validation": split.validation,
            "test": split.test,
        }
        errors: list[str] = []
        family_sets = {
            name: {example.scenario_family_id for example in examples}
            for name, examples in partitions.items()
        }
        for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
            overlap = family_sets[left] & family_sets[right]
            if overlap:
                errors.append(
                    "scenario-family split leakage between "
                    f"{left} and {right}: {sorted(overlap)}"
                )
        examples = split.train + split.validation + split.test
        semantic = self.validate(examples)
        errors.extend(semantic.errors)
        manifest = semantic.manifest.model_copy(
            update={"split_counts": {name: len(items) for name, items in partitions.items()}}
        )
        return DatasetValidationReport(valid=not errors, errors=errors, manifest=manifest)

    def _validate_example(self, example: FineTuneExample) -> list[str]:
        errors: list[str] = []
        definitions = {definition.name: definition for definition in example.tools}
        outstanding_calls: set[str] = set()
        actual_tools: list[str] = []
        actual_calls = []
        calls_by_id = {}
        if not example.messages:
            return [f"{example.example_id}: empty messages"]
        previous_role: str | None = None
        conversation_started = False
        for message in example.messages:
            role_error = False
            if message.role == "system":
                role_error = conversation_started
            else:
                conversation_started = True
                if message.role == "user":
                    role_error = previous_role not in (
                        None,
                        "system",
                        "assistant",
                    ) or bool(outstanding_calls)
                elif message.role == "assistant":
                    role_error = previous_role not in ("user", "tool") or bool(
                        outstanding_calls
                    )
                elif message.role == "tool":
                    role_error = previous_role not in ("assistant", "tool")
            if role_error:
                errors.append(f"{example.example_id}: invalid role ordering")

            if message.role == "assistant":
                for call in message.tool_calls:
                    actual_tools.append(call.name)
                    actual_calls.append(call)
                    if call.id in calls_by_id:
                        errors.append(f"{example.example_id}: duplicate tool call id")
                    calls_by_id[call.id] = call
                    definition = definitions.get(call.name)
                    if definition is None:
                        errors.append(
                            f"{example.example_id}: tool call {call.name} has no tool definition"
                        )
                    else:
                        errors.extend(
                            self._validate_arguments(example.example_id, call.arguments, definition)
                        )
                    outstanding_calls.add(call.id)
                if message.content and message.content.lstrip().startswith("{"):
                    try:
                        json.loads(message.content)
                    except json.JSONDecodeError:
                        errors.append(f"{example.example_id}: malformed structured output")
            elif message.role == "tool":
                if not message.tool_call_id or message.tool_call_id not in outstanding_calls:
                    errors.append(f"{example.example_id}: unmatched tool_call_id")
                else:
                    outstanding_calls.remove(message.tool_call_id)
                    call = calls_by_id[message.tool_call_id]
                    try:
                        TOOL_RESULT_MODELS[call.name].model_validate_json(message.content or "")
                    except (KeyError, ValueError):
                        errors.append(f"{example.example_id}: invalid tool result")
            previous_role = message.role
        if outstanding_calls:
            errors.append(f"{example.example_id}: tool call has no matching tool response")
        if example.labels.should_call_tool and not example.labels.expected_tool:
            errors.append(f"{example.example_id}: expected_tool is required")
        if not example.labels.should_call_tool and actual_tools:
            errors.append(f"{example.example_id}: should_call_tool=false but tool was called")
        if example.labels.should_call_tool and not actual_tools:
            errors.append(f"{example.example_id}: should_call_tool=true but no tool was called")
        if (
            example.labels.expected_tool
            and example.labels.expected_tool not in actual_tools
        ):
            errors.append(
                f"{example.example_id}: expected_tool does not match actual tool call"
            )
        try:
            actual = [
                (
                    call.name,
                    TOOL_ARG_MODELS[call.name]
                    .model_validate(call.arguments)
                    .model_dump(),
                )
                for call in actual_calls
            ]
            expected = [
                (
                    call.name,
                    TOOL_ARG_MODELS[call.name]
                    .model_validate(call.arguments)
                    .model_dump(),
                )
                for call in example.labels.expected_tool_calls
            ]
            if actual != expected:
                errors.append(
                    f"{example.example_id}: expected_tool_calls argument/sequence mismatch"
                )
        except (KeyError, ValueError):
            errors.append(f"{example.example_id}: invalid expected/actual arguments")
        return errors

    @staticmethod
    def _validate_arguments(
        example_id: str, arguments: dict[str, Any], definition: ToolDefinition
    ) -> list[str]:
        try:
            TOOL_ARG_MODELS[definition.name].model_validate(arguments)
        except (KeyError, ValueError) as exc:
            return [f"{example_id}: invalid arguments for {definition.name}: {exc}"]
        return []
