from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a markdown benchmark dashboard.")
    parser.add_argument("--trends", required=True, help="Path to trend JSON report.")
    parser.add_argument("--leaderboard", required=True, help="Path to leaderboard JSON report.")
    parser.add_argument("--out", default="benchmarks/results/benchmark_dashboard.md")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def build_dashboard_markdown(trends: dict[str, Any], leaderboard: dict[str, Any]) -> str:
    lines: list[str] = ["# Benchmark Dashboard", ""]
    lines.append(f"- Trend rows: {int(trends.get('row_count', 0) or 0)}")
    lines.append(f"- Leaderboard groups: {int(leaderboard.get('group_count', 0) or 0)}")
    lines.append("")

    lines.append("## Trends")
    rows = trends.get("rows", [])
    if isinstance(rows, list) and rows:
        lines.append("| Source | Venue | Flow | Score | Determinism | Avg Latency (ms) | Avg Cost (USD) |")
        lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: |")
        for row in rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                "| {source} | {venue} | {flow} | {score} | {det} | {lat} | {cost} |".format(
                    source=row.get("source", ""),
                    venue=row.get("venue", ""),
                    flow=row.get("flow", ""),
                    score=row.get("overall_avg_score", 0.0),
                    det=row.get("determinism_rate", 0.0),
                    lat=row.get("avg_latency_ms", 0.0),
                    cost=row.get("avg_cost_usd", 0.0),
                )
            )
    else:
        lines.append("No trend rows available.")
    lines.append("")

    lines.append("## Leaderboard")
    groups = leaderboard.get("groups", [])
    if isinstance(groups, list) and groups:
        for group in groups:
            if not isinstance(group, dict):
                continue
            schema_version = group.get("schema_version", "unknown")
            policy_version = group.get("policy_version", "unknown")
            lines.append(f"### Schema `{schema_version}` / Policy `{policy_version}`")
            lines.append("| Rank | Source | Venue | Flow | Score |")
            lines.append("| ---: | --- | --- | --- | ---: |")
            entries = group.get("entries", [])
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    lines.append(
                        "| {rank} | {source} | {venue} | {flow} | {score} |".format(
                            rank=entry.get("rank", ""),
                            source=entry.get("source", ""),
                            venue=entry.get("venue", ""),
                            flow=entry.get("flow", ""),
                            score=entry.get("overall_avg_score", 0.0),
                        )
                    )
            lines.append("")
    else:
        lines.append("No leaderboard entries available.")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = _parse_args()
    trends = _load_json(Path(args.trends))
    leaderboard = _load_json(Path(args.leaderboard))
    markdown = build_dashboard_markdown(trends=trends, leaderboard=leaderboard)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
