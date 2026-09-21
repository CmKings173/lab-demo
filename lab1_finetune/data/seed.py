from __future__ import annotations

import json
from pathlib import Path

from lab1_finetune.data.fixtures.tool_results import typed_result
from lab1_finetune.data.schema import DatasetLabels, ExpectedToolCall, FineTuneExample
from shared.contracts import ChatMessage, ToolCall
from shared.tool_args import TOOL_ARG_MODELS
from shared.tool_contracts import TOOL_DEFINITIONS

SEED_PATH = Path(__file__).with_name("seed") / "gold_seed_vi.jsonl"
GOLD_SOURCE_TYPE = "synthetic_curated_unreviewed"
SYSTEM_MESSAGE = (
    "Bạn là trợ lý tư vấn AI Server và AI Workstation. Dùng dữ liệu công cụ để trả lời; "
    "không suy đoán thông số, giá hoặc tồn kho và hỏi lại khi thiếu yêu cầu bắt buộc."
)


def build_gold_seed_examples() -> list[FineTuneExample]:
    specs = json.loads(Path(__file__).with_name("gold_specs.json").read_text(encoding="utf-8"))
    examples = []
    for spec in specs:
        example_id = spec["example_id"]
        if not spec.get("final"):
            raise ValueError(f"Gold example {example_id} must define explicit final response")
        messages = [ChatMessage(role="system", content=SYSTEM_MESSAGE)]
        messages.extend(ChatMessage.model_validate(item) for item in spec.get("history", []))
        messages.append(ChatMessage(role="user", content=spec["user"]))
        expected = []
        for index, step in enumerate(spec["steps"]):
            if "arguments" not in step:
                raise ValueError(f"Gold example {example_id} must define explicit tool arguments")
            TOOL_ARG_MODELS[step["name"]].model_validate(step["arguments"])
            call = ToolCall(id=f"{example_id}-call-{index}", name=step["name"],
                            arguments=step["arguments"])
            expected.append(ExpectedToolCall(name=call.name, arguments=call.arguments))
            messages.extend([
                ChatMessage(role="assistant", tool_calls=[call]),
                ChatMessage(role="tool", tool_call_id=call.id,
                            content=typed_result(step).model_dump_json()),
            ])
        messages.append(ChatMessage(role="assistant", content=spec["final"]))
        examples.append(FineTuneExample(
            example_id=example_id, scenario_family_id=spec["family"],
            scenario_summary=spec["scenario"], language="vi", difficulty="medium",
            source_type=GOLD_SOURCE_TYPE,
            task_type="tool_calling" if expected else "conversation",
            messages=messages, tools=TOOL_DEFINITIONS if expected else [],
            labels=DatasetLabels(
                intent=spec["intent"], scenario_type=spec["scenario"],
                extracted_requirement=spec["requirement"], missing_fields=spec["missing"],
                should_call_tool=bool(expected),
                expected_tool=expected[0].name if expected else None,
                expected_tool_calls=expected, should_abstain=spec["should_abstain"],
            ),
        ))
    return examples


def write_gold_seed(path: Path = SEED_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(item.model_dump_json() + "\n" for item in build_gold_seed_examples()),
                    encoding="utf-8")


def load_gold_seed(path: Path = SEED_PATH) -> list[FineTuneExample]:
    return [FineTuneExample.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_seed_examples() -> list[FineTuneExample]:
    return load_gold_seed()


if __name__ == "__main__":
    write_gold_seed()
