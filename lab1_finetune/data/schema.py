from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from shared.contracts import ChatMessage, CustomerRequirement, ToolDefinition
from shared.contracts.models import ContractModel


class Intent(StrEnum):
    SOLUTION_DESIGN = "solution_design"
    PRODUCT_SEARCH = "product_search"
    PRODUCT_COMPARISON = "product_comparison"
    TECHNICAL_QUESTION = "technical_question"
    GENERAL_AI_QUESTION = "general_ai_question"
    OUT_OF_SCOPE = "out_of_scope"


class ScenarioType(StrEnum):
    SOLUTION_COMPLETE = "solution_complete"
    MISSING_BUDGET = "missing_budget"
    MISSING_USAGE = "missing_usage"
    MISSING_MODEL_SIZE = "missing_model_size"
    MISSING_MULTIPLE_FIELDS = "missing_multiple_fields"
    AMBIGUOUS_SOLUTION = "ambiguous_solution"
    CONTRADICTORY_REQUIREMENT = "contradictory_requirement"
    SEARCH_WORKSTATION_BY_RAM = "search_workstation_by_ram"
    SEARCH_SERVER_BY_GPU_SLOTS = "search_server_by_gpu_slots"
    SEARCH_PRODUCT_BY_BUDGET = "search_product_by_budget"
    NO_PRODUCT_FOUND = "no_product_found"
    COMPARE_PRODUCTS = "compare_products"
    COMPARE_CONFIGURATIONS = "compare_configurations"
    TECHNICAL_MAX_RAM = "technical_max_ram"
    TECHNICAL_MAX_GPU = "technical_max_gpu"
    UNKNOWN_PRODUCT_SPEC = "unknown_product_spec"
    TOOL_FAILURE = "tool_failure"
    GENERAL_VRAM = "general_vram"
    GENERAL_INFERENCE = "general_inference"
    GENERAL_LORA = "general_lora"
    OUT_SCOPE_LAPTOP = "out_scope_laptop"
    OUT_SCOPE_NETWORK_SWITCH = "out_scope_network_switch"
    FINETUNE_32B_SOLUTION = "finetune_32b_solution"
    LARGE_MODEL_LOW_BUDGET = "large_model_low_budget"
    REQUIREMENT_CHANGED_MID_CONVERSATION = "requirement_changed_mid_conversation"


class DatasetLabels(ContractModel):
    intent: Intent
    scenario_type: ScenarioType
    extracted_requirement: CustomerRequirement = Field(default_factory=CustomerRequirement)
    missing_fields: list[str] = Field(default_factory=list)
    should_call_tool: bool
    expected_tool: str | None = None
    must_not_invent_product_fact: bool = True
    expected_behavior: str | None = None
    expected_final_response_type: str | None = None


class FineTuneExample(ContractModel):
    example_id: str = Field(min_length=1)
    scenario_family_id: str = Field(min_length=1)
    scenario_summary: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)
    language: Literal["vi"]
    source_type: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    tools: list[ToolDefinition] = Field(default_factory=list)
    labels: DatasetLabels


class DatasetSplit(ContractModel):
    train: list[FineTuneExample]
    validation: list[FineTuneExample]
    test: list[FineTuneExample]


class DatasetManifest(ContractModel):
    dataset_version: str
    created_at: datetime
    example_count: int = Field(ge=0)
    family_count: int = Field(ge=0)
    language_counts: dict[str, int] = Field(default_factory=dict)
    intent_counts: dict[str, int] = Field(default_factory=dict)
    scenario_type_counts: dict[str, int] = Field(default_factory=dict)
    task_type_counts: dict[str, int] = Field(default_factory=dict)
    split_counts: dict[str, int] = Field(default_factory=dict)
    seed: int
    content_hash: str


class DatasetValidationReport(ContractModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    manifest: DatasetManifest


class DatasetBundle(ContractModel):
    examples: list[FineTuneExample]
    split: DatasetSplit | None = None
    manifest: DatasetManifest | None = None
