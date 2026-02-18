from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build benchmark leaderboard grouped by version/policy.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Input scored report JSON files.")
    parser.add_argument("--out", default="benchmarks/results/benchmark_leaderboard.json")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_leaderboard(inputs: list[Path]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in inputs:
        scored = _load_json(path)
        entries.append(
            {
                "source": str(path).replace("\\", "/"),
                "schema_version": str(scored.get("schema_version", "unknown")),
                "policy_version": str(scored.get("policy_version", "unknown")),
                "venue": str(scored.get("venue", "unknown")),
                "flow": str(scored.get("flow", "unknown")),
                "overall_avg_score": _to_float(scored.get("overall_avg_score")),
            }
        )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        key = (entry["schema_version"], entry["policy_version"])
        grouped.setdefault(key, []).append(entry)

    leaderboard_groups = []
    for (schema_version, policy_version), rows in sorted(grouped.items()):
        ordered = sorted(
            rows,
            key=lambda row: row["overall_avg_score"],
            reverse=True,
        )
        for index, row in enumerate(ordered, start=1):
            row["rank"] = index
        leaderboard_groups.append(
            {
                "schema_version": schema_version,
                "policy_version": policy_version,
                "entries": ordered,
            }
        )

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "group_count": len(leaderboard_groups),
        "groups": leaderboard_groups,
    }


def main() -> int:
    args = _parse_args()
    input_paths = [Path(item) for item in args.inputs]
    report = build_leaderboard(input_paths)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
