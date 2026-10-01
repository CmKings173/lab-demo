from lab1_finetune.data.seed import build_seed_examples
from lab1_finetune.data.splitter import DatasetSplitter
from lab1_finetune.evaluation.evaluator import DeterministicEvaluationSkeleton
from lab1_finetune.evaluation.schema import EvaluationCase
from lab1_finetune.training.config import TrainingConfig


def test_lab1_defaults_to_safe_lora_foundation_settings() -> None:
    config = TrainingConfig()

    assert config.model_name == "Qwen/Qwen3-14B"
    assert config.use_lora is True
    assert config.use_qlora is False
    assert config.bf16 is True


def test_dataset_pipeline_splits_examples_deterministically() -> None:
    examples = build_seed_examples()

    first = DatasetSplitter(seed=7).split(examples)
    second = DatasetSplitter(seed=7).split(examples)

    assert first == second
    assert len(first.train) + len(first.validation) + len(first.test) == len(examples)


def test_evaluation_case_uses_messages_tools_and_gold_labels() -> None:
    example = build_seed_examples()[0]
    case = EvaluationCase(
        case_id="1",
        messages=example.messages,
        tools=example.tools,
        gold_labels=example.labels,
    )

    prepared = DeterministicEvaluationSkeleton().prepare([case])

    assert prepared == [case]
