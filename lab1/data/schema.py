from __future__ import annotations

from typing import Any

from pydantic import Field

from shared.contracts.models import ContractModel


class FineTuneExample(ContractModel):
    example_id: str
    user_input: str
    expected_output: dict[str, Any]
    source: str | None = None
    tags: list[str] = Field(default_factory=list)


class DatasetSplit(ContractModel):
    train: list[FineTuneExample]
    validation: list[FineTuneExample]
    test: list[FineTuneExample]


class DatasetBundle(ContractModel):
    examples: list[FineTuneExample]
    split: DatasetSplit | None = None
