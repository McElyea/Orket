from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build trend report from benchmark scored reports.")
    parser.add_argument("--inputs", nargs="*", default=[], help="Input scored report JSON files.")
    parser.add_argument(
        "--input-glob",
        action="append",
        default=[],
        help="Optional glob pattern(s) for scored report files.",
    )
    parser.add_argument("--out", default="benchmarks/results/benchmark_trends.json")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_input_paths(inputs: list[str], globs: list[str]) -> list[Path]:
    paths: list[Path] = [Path(item) for item in inputs]
    for pattern in globs:
        paths.extend(Path().glob(pattern))
    deduped = {str(path.resolve()): path for path in paths}
    ordered = sorted(deduped.values(), key=lambda path: str(path).replace("\\", "/"))
    return ordered


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round(current - previous, 6)


def build_trend_report(inputs: list[Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for path in inputs:
        scored = _load_json(path)
        row = {
            "source": str(path).replace("\\", "/"),
            "schema_version": scored.get("schema_version"),
            "policy_version": scored.get("policy_version"),
            "venue": scored.get("venue"),
            "flow": scored.get("flow"),
            "overall_avg_score": _to_float(scored.get("overall_avg_score")),
            "determinism_rate": _to_float(scored.get("determinism_rate")),
            "avg_latency_ms": _to_float(scored.get("avg_latency_ms")),
            "avg_cost_usd": _to_float(scored.get("avg_cost_usd")),
        }
        row["delta_overall_avg_score"] = _delta(
            row["overall_avg_score"],
            None if previous is None else previous["overall_avg_score"],
        )
        row["delta_determinism_rate"] = _delta(
            row["determinism_rate"],
            None if previous is None else previous["determinism_rate"],
        )
        row["delta_avg_latency_ms"] = _delta(
            row["avg_latency_ms"],
            None if previous is None else previous["avg_latency_ms"],
        )
        row["delta_avg_cost_usd"] = _delta(
            row["avg_cost_usd"],
            None if previous is None else previous["avg_cost_usd"],
        )
        rows.append(row)
        previous = row

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "row_count": len(rows),
        "rows": rows,
    }


def main() -> int:
    args = _parse_args()
    input_paths = _resolve_input_paths(inputs=list(args.inputs), globs=list(args.input_glob))
    if not input_paths:
        raise SystemExit("At least one input path or input glob match is required.")
    report = build_trend_report(input_paths)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
