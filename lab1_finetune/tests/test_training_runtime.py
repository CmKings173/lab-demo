import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from lab1_finetune.training import train as training_module
from lab1_finetune.training.config import TrainingConfig
from lab1_finetune.training.data import load_qwen_export, normalize_qwen_record
from lab1_finetune.training.train import (
    _check_assistant_mask,
    _load_data_and_tokenizer,
    _prepare_training_chat_template,
    calculate_warmup_steps,
    inspect_token_lengths,
    validate_training_inputs,
)


def test_training_config_selects_qwen3_14b_lora_baseline() -> None:
    config = TrainingConfig()

    assert config.model_name == "Qwen/Qwen3-14B"
    assert config.lora_target_modules == "all-linear"
    assert config.task_type == "CAUSAL_LM"
    assert config.use_lora is True
    assert config.use_qlora is False
    assert config.bf16 is True
    assert config.lr_scheduler_type == "cosine"
    assert config.warmup_ratio == 0.05
    assert config.weight_decay == 0.01
    assert config.eval_strategy == config.save_strategy == "epoch"


def test_qwen_export_tool_call_is_renderable_by_transformers(tmp_path) -> None:
    record = {
        "messages": [
            {"role": "user", "content": "Tra RAM", "tool_calls": [], "tool_call_id": None},
            {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "call-1", "name": "lookup", "arguments": {"id": "ws-1"}}],
                "tool_call_id": None,
            },
            {
                "role": "tool", "content": "{\"ram\":512}",
                "tool_calls": [], "tool_call_id": "call-1",
            },
            {"role": "assistant", "content": "512GB", "tool_calls": [], "tool_call_id": None},
        ],
        "tools": [{"name": "lookup", "description": "Find RAM", "parameters": {"type": "object"}}],
    }
    source = tmp_path / "train.jsonl"
    source.write_text(json.dumps(record) + "\n", encoding="utf-8")

    normalized = load_qwen_export(source)[0]

    assert normalized == normalize_qwen_record(record)
    assert normalized["messages"][1]["tool_calls"] == [
        {"type": "function", "function": {"name": "lookup", "arguments": {"id": "ws-1"}}}
    ]
    assert normalized["messages"][2] == {
        "role": "tool", "name": "lookup", "content": "{\"ram\":512}"
    }
    assert normalized["tools"][0]["function"]["name"] == "lookup"


def test_qwen_export_rejects_tool_result_without_matching_call() -> None:
    record = {
        "messages": [
            {"role": "user", "content": "Tra RAM"},
            {"role": "tool", "content": "512", "tool_call_id": "missing"},
            {"role": "assistant", "content": "512GB"},
        ],
        "tools": [],
    }

    with pytest.raises(ValueError, match="unknown tool_call_id"):
        normalize_qwen_record(record)


def test_qwen_export_rejects_malformed_tool_calls() -> None:
    record = {
        "messages": [
            {"role": "user", "content": "Tra RAM", "tool_calls": {}},
            {"role": "assistant", "content": "Chưa rõ"},
        ],
        "tools": [],
    }

    with pytest.raises(ValueError, match="tool_calls"):
        normalize_qwen_record(record)


def test_training_requires_pinned_revision_for_remote_model(tmp_path) -> None:
    config = TrainingConfig(
        train_file=tmp_path / "train.jsonl",
        validation_file=tmp_path / "validation.jsonl",
    )
    with pytest.raises(ValueError, match="model_revision"):
        validate_training_inputs(config)


def test_training_accepts_local_model_and_separate_frozen_exports(tmp_path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    train_file = tmp_path / "train.jsonl"
    validation_file = tmp_path / "validation.jsonl"
    train_file.write_text("{}\n", encoding="utf-8")
    validation_file.write_text("{}\n", encoding="utf-8")
    config = TrainingConfig(
        model_name=str(model_dir), train_file=train_file, validation_file=validation_file,
        output_dir=tmp_path / "adapter",
    )

    validate_training_inputs(config)


def test_frozen_training_and_validation_exports_load_without_schema_drift() -> None:
    exports = Path(__file__).resolve().parents[1] / "data/generated/exports"

    train_rows = load_qwen_export(exports / "train_qwen.jsonl")
    validation_rows = load_qwen_export(exports / "validation_qwen.jsonl")

    assert train_rows and validation_rows
    assert any(row["tools"] for row in train_rows)
    assert all(row["messages"][-1]["role"] == "assistant" for row in train_rows)


def test_training_accepts_pinned_remote_revision(tmp_path) -> None:
    train_file = tmp_path / "train.jsonl"
    validation_file = tmp_path / "validation.jsonl"
    train_file.write_text("{}\n", encoding="utf-8")
    validation_file.write_text("{}\n", encoding="utf-8")
    config = TrainingConfig(
        model_revision="a" * 40,
        train_file=train_file,
        validation_file=validation_file,
        output_dir=tmp_path / "adapter",
    )

    validate_training_inputs(config)


def test_preflight_rejects_any_conversation_that_would_be_truncated() -> None:
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return list(range(len(messages) * 5))

    rows = [{"messages": [{"role": "user"}, {"role": "assistant"}], "tools": []}]

    with pytest.raises(ValueError, match="exceed max_seq_length"):
        inspect_token_lengths(rows, Tokenizer(), 8)


@pytest.mark.parametrize(
    "encoded,expected_count",
    [
        ({"input_ids": [11, 12, 13]}, 3),
        (SimpleNamespace(input_ids=[11, 12, 13, 14]), 4),
        (SimpleNamespace(input_ids=SimpleNamespace(tolist=lambda: [11, 12])), 2),
        ({"input_ids": [[11, 12, 13, 14, 15]]}, 5),
    ],
)
def test_preflight_counts_token_ids_from_supported_tokenizer_outputs(
    encoded, expected_count
) -> None:
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return encoded

    rows = [{"messages": [{"role": "user", "content": "x"}], "tools": []}]

    report = inspect_token_lengths(rows, Tokenizer(), 16)

    assert report["max"] == expected_count


def test_preflight_rejects_multi_conversation_batch_token_ids() -> None:
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return {"input_ids": [[1, 2], [3, 4]]}

    rows = [{"messages": [{"role": "user", "content": "x"}], "tools": []}]

    with pytest.raises(ValueError, match="exactly one conversation"):
        inspect_token_lengths(rows, Tokenizer(), 16)


def test_training_template_is_patched_before_shared_preflight_inspection(
    monkeypatch, tmp_path
) -> None:
    expected_template = "{% generation %}assistant{% endgeneration %}"

    class Tokenizer:
        chat_template = "original"
        pad_token = "pad"
        eos_token = "eos"

        def apply_chat_template(self, messages, **kwargs):
            assert self.chat_template == expected_template
            return SimpleNamespace(input_ids=SimpleNamespace(tolist=lambda: [1, 2, 3]))

    tokenizer = Tokenizer()
    transformers = ModuleType("transformers")
    transformers.AutoTokenizer = SimpleNamespace(
        from_pretrained=lambda *args, **kwargs: tokenizer
    )
    trl = ModuleType("trl")
    trl.__path__ = []
    trl_chat_utils = ModuleType("trl.chat_template_utils")
    trl_chat_utils.get_training_chat_template = lambda processing_class: expected_template
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "trl", trl)
    monkeypatch.setitem(sys.modules, "trl.chat_template_utils", trl_chat_utils)
    monkeypatch.setattr(
        training_module,
        "load_qwen_export",
        lambda path: [{"messages": [{"role": "user", "content": "x"}], "tools": []}],
    )

    config = TrainingConfig(
        model_name="local-model",
        train_file=tmp_path / "train.jsonl",
        validation_file=tmp_path / "validation.jsonl",
    )

    prepared_tokenizer, _, _, lengths = _load_data_and_tokenizer(config)

    assert prepared_tokenizer is tokenizer
    assert tokenizer.chat_template == expected_template
    assert lengths["train"]["max"] == 3
    assert lengths["validation"]["max"] == 3


@pytest.mark.parametrize(
    "template",
    [
        "plain template without training markers",
        "{% generation %}missing closing marker",
        "missing opening marker{% endgeneration %}",
    ],
)
def test_training_template_requires_both_assistant_generation_markers(
    monkeypatch, template
) -> None:
    trl = ModuleType("trl")
    trl.__path__ = []
    trl_chat_utils = ModuleType("trl.chat_template_utils")
    trl_chat_utils.get_training_chat_template = lambda processing_class: template
    monkeypatch.setitem(sys.modules, "trl", trl)
    monkeypatch.setitem(sys.modules, "trl.chat_template_utils", trl_chat_utils)

    with pytest.raises(ValueError, match="generation markers"):
        _prepare_training_chat_template(SimpleNamespace(chat_template="original"))


def test_warmup_steps_use_ceiling_optimizer_step_count() -> None:
    assert calculate_warmup_steps(
        train_examples=961,
        per_device_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=3,
        warmup_ratio=0.05,
    ) == 19
    assert calculate_warmup_steps(
        train_examples=9,
        per_device_batch_size=2,
        gradient_accumulation_steps=4,
        num_train_epochs=3,
        warmup_ratio=0.05,
    ) == 1


def test_assistant_mask_rejects_tool_results_in_supervised_tokens() -> None:
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return {"input_ids": [1, 2, 3], "assistant_masks": [0, 1, 1]}

        def decode(self, ids):
            return "<tool_call><tool_response>"

    rows = [{"messages": [{"role": "assistant", "tool_calls": [{}]}], "tools": []}]

    with pytest.raises(ValueError, match="exclude tool results"):
        _check_assistant_mask(Tokenizer(), rows)


def test_assistant_mask_allows_assistant_tool_calls_without_tool_results() -> None:
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return {"input_ids": [1, 2, 3], "assistant_masks": [0, 1, 1]}

        def decode(self, ids):
            return "<tool_call>lookup</tool_call>"

    rows = [{"messages": [{"role": "assistant", "tool_calls": [{}]}], "tools": []}]

    _check_assistant_mask(Tokenizer(), rows)


def test_assistant_mask_checks_plain_and_tool_conversations() -> None:
    class Tokenizer:
        def __init__(self) -> None:
            self.checked: list[str] = []

        def apply_chat_template(self, messages, **kwargs):
            self.checked.append(messages[0]["content"])
            return {"input_ids": [1, 2, 3], "assistant_masks": [0, 1, 1]}

        def decode(self, ids):
            return "<tool_call>lookup</tool_call>"

    tokenizer = Tokenizer()
    rows = [
        {"messages": [{"role": "assistant", "content": "tool", "tool_calls": [{}]}], "tools": []},
        {"messages": [{"role": "assistant", "content": "plain"}], "tools": []},
    ]

    _check_assistant_mask(tokenizer, rows)

    assert tokenizer.checked == ["plain", "tool"]
