from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build trend report from benchmark scored reports.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Input scored report JSON files.")
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


def build_trend_report(inputs: list[Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in inputs:
        scored = _load_json(path)
        rows.append(
            {
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
        )

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "row_count": len(rows),
        "rows": rows,
    }


def main() -> int:
    args = _parse_args()
    input_paths = [Path(item) for item in args.inputs]
    report = build_trend_report(input_paths)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
