"""Re-score saved Base/LoRA reports without loading or calling a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab1_finetune.evaluation.compare_results import compare_reports
from lab1_finetune.evaluation.run_model_eval import rescore_report

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_BASE = _ROOT / "artifacts/lab1/eval/base.json"
_DEFAULT_LORA = _ROOT / "artifacts/lab1/eval/lora.json"
_ARGUMENT_METRICS = (
    ("tool_argument_accuracy", "Exact (existing)"),
    ("tool_argument_contract_normalized_accuracy", "Contract-normalized"),
    ("tool_argument_critical_field_accuracy", "Critical business fields"),
)


def _load_rescored(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"saved evaluation report not found: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError(f"saved evaluation report must be a JSON object: {path}")
    return rescore_report(report)


def render_summary(base: dict, lora: dict) -> str:
    comparison = compare_reports(base, lora)
    lines = [
        "| Argument metric | Base | LoRA | Delta (LoRA − Base) |",
        "|---|---:|---:|---:|",
    ]
    for metric, label in _ARGUMENT_METRICS:
        row = comparison["metrics"].get(metric, {})
        values = (row.get("base"), row.get("candidate"), row.get("delta"))
        base_value = "N/A" if values[0] is None else f"{values[0] * 100:.2f}%"
        lora_value = "N/A" if values[1] is None else f"{values[1] * 100:.2f}%"
        delta = "N/A" if values[2] is None else f"{values[2] * 100:+.2f} pp"
        lines.append(f"| {label} | {base_value} | {lora_value} | {delta} |")

    lines.extend(("", "Top critical mismatch categories:"))
    for label, report in (("Base", base), ("LoRA", lora)):
        categories = report.get("critical_argument_mismatch_categories", [])[:10]
        summary = ", ".join(
            f"{item['category']} ({item['count']})" for item in categories
        ) or "none"
        lines.append(f"- {label}: {summary}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=_DEFAULT_BASE)
    parser.add_argument("--lora", type=Path, default=_DEFAULT_LORA)
    args = parser.parse_args(argv)
    try:
        base = _load_rescored(args.base)
        lora = _load_rescored(args.lora)
        print(render_summary(base, lora))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
