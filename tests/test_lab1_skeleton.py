from lab1.configs.training_config import TrainingConfig
from lab1.data.schema import FineTuneExample
from lab1.src.evaluation import EvaluationCase, EvaluationRunner
from lab1.src.pipeline import DatasetPipeline


def test_lab1_defaults_to_safe_lora_foundation_settings() -> None:
    config = TrainingConfig()

    assert config.model_name == "Qwen3-8B"
    assert config.use_lora is True
    assert config.use_qlora is False
    assert config.bf16 is True


def test_dataset_pipeline_splits_examples_deterministically() -> None:
    examples = [
        FineTuneExample(
            example_id=str(index),
            user_input=f"request {index}",
            expected_output={"status": "ok"},
        )
        for index in range(20)
    ]

    first = DatasetPipeline(seed=7).split(examples)
    second = DatasetPipeline(seed=7).split(examples)

    assert first == second
    assert len(first.train) + len(first.validation) + len(first.test) == 20


def test_evaluation_runner_has_a_stable_result_contract() -> None:
    runner = EvaluationRunner()
    result = runner.run([EvaluationCase(case_id="1", prompt="hello", expected={"x": 1})])

    assert result.total == 1
    assert result.passed == 0
    assert result.skipped == 1
