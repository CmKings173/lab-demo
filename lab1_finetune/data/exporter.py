import json
from collections.abc import Iterable
from pathlib import Path

from lab1_finetune.data.schema import FineTuneExample


def export_qwen_jsonl(examples: Iterable[FineTuneExample], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "messages": [message.model_dump(mode="json") for message in example.messages],
            "tools": [tool.model_dump(mode="json") for tool in example.tools],
        }
        for example in examples
    ]
    output.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
