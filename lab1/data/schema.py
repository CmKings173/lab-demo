from __future__ import annotations

from collections import Counter

from pydantic import Field

from shared.contracts import ChatMessage, ToolDefinition
from shared.contracts.models import ContractModel


class DatasetLabels(ContractModel):
    intent: str = Field(min_length=1)
    missing_fields: list[str] = Field(default_factory=list)
    should_call_tool: bool
    expected_tool: str | None = None
    must_not_invent_product_fact: bool = True


class FineTuneExample(ContractModel):
    example_id: str = Field(min_length=1)
    scenario_family_id: str = Field(min_length=1)
    scenario_summary: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)
    language: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    tools: list[ToolDefinition] = Field(default_factory=list)
    labels: DatasetLabels


class DatasetSplit(ContractModel):
    train: list[FineTuneExample]
    validation: list[FineTuneExample]
    test: list[FineTuneExample]


class DatasetManifest(ContractModel):
    example_count: int = Field(ge=0)
    family_count: int = Field(ge=0)
    task_type_counts: dict[str, int] = Field(default_factory=dict)
    language_counts: dict[str, int] = Field(default_factory=dict)
    split_counts: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_examples(cls, examples: list[FineTuneExample]) -> "DatasetManifest":
        return cls(
            example_count=len(examples),
            family_count=len({example.scenario_family_id for example in examples}),
            task_type_counts=dict(Counter(example.task_type for example in examples)),
            language_counts=dict(Counter(example.language for example in examples)),
        )


class DatasetValidationReport(ContractModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    manifest: DatasetManifest


class DatasetBundle(ContractModel):
    examples: list[FineTuneExample]
    split: DatasetSplit | None = None
    manifest: DatasetManifest | None = None
