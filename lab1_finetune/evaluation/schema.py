from pydantic import Field

from lab1_finetune.data.schema import DatasetLabels
from shared.contracts import ChatMessage, ToolCall, ToolDefinition
from shared.contracts.models import ContractModel


class EvaluationCase(ContractModel):
    case_id: str
    messages: list[ChatMessage] = Field(min_length=1)
    tools: list[ToolDefinition] = Field(default_factory=list)
    gold_labels: DatasetLabels


class EvaluationPrediction(ContractModel):
    intent: str | None = None
    extracted_requirement: dict[str, object] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    structured_output: dict[str, object] | str | None = None
    unsupported_product_claims: int = 0
    total_product_claims: int = 0
    abstained: bool = False


class EvaluationMetrics(ContractModel):
    intent_accuracy: float
    field_extraction_precision: float
    field_extraction_recall: float
    field_extraction_f1: float
    missing_fields_exact_match: float
    tool_needed_accuracy: float
    tool_name_accuracy: float
    tool_argument_validity: float
    tool_sequence_accuracy: float
    tool_argument_schema_validity: float
    tool_argument_exact_match: float
    tool_argument_semantic_match: float
    structured_output_validity: float
    unsupported_product_claim_rate: float
    abstention_accuracy: float
