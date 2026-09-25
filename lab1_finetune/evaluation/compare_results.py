"""Report per-metric Base/LoRA deltas without inventing an overall winner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare_reports(base: dict, candidate: dict) -> dict:
    if base.get("benchmark_hash") != candidate.get("benchmark_hash") or not base.get(
        "benchmark_hash"
    ):
        raise ValueError("Results must use the same benchmark content hash")
    if base.get("total_cases") != candidate.get("total_cases"):
        raise ValueError("Results have different benchmark case counts")
    base_ids = [case["case_id"] for case in base.get("cases", [])]
    candidate_ids = [case["case_id"] for case in candidate.get("cases", [])]
    if base_ids and candidate_ids and base_ids != candidate_ids:
        raise ValueError("Results have different benchmark case IDs or order")
    if base.get("evaluation_config") != candidate.get("evaluation_config"):
        raise ValueError("Results have different evaluation configurations")
    names = set(base["metrics"]) | set(candidate["metrics"])
    metrics = {}
    for name in sorted(names):
        left = base["metrics"].get(name, {})
        right = candidate["metrics"].get(name, {})
        a, b = left.get("value"), right.get("value")
        metrics[name] = {
            "base": a,
            "candidate": b,
            "delta": round(b - a, 6) if a is not None and b is not None else None,
            "base_count": left.get("count", 0),
            "candidate_count": right.get("count", 0),
        }
    return {
        "benchmark_hash": base["benchmark_hash"],
        "base_model": base.get("model_name"),
        "candidate_model": candidate.get("model_name"),
        "base_failed_cases": base.get("failed_cases"),
        "candidate_failed_cases": candidate.get("failed_cases"),
        "metrics": metrics,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args(argv)
    base = json.loads(args.base.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    print(json.dumps(compare_reports(base, candidate), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
