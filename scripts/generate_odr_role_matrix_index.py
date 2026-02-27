from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _safe_rounds_used(scenario: dict[str, Any]) -> int:
    final_state = scenario.get("final_state")
    if isinstance(final_state, dict):
        value = final_state.get("history_round_count")
        if isinstance(value, int):
            return value
    rounds = scenario.get("rounds")
    if isinstance(rounds, list):
        return len(rounds)
    return 0


def _extract_runs_from_file(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, dict):
        return []

    generated_at = payload.get("generated_at")
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    rows: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        architect_model = str(result.get("architect_model") or "")
        auditor_model = str(result.get("auditor_model") or "")
        scenarios = result.get("scenarios")
        if not isinstance(scenarios, list):
            scenarios = []

        scenario_rows: list[dict[str, Any]] = []
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                continue
            scenario_rows.append(
                {
                    "scenario_id": scenario.get("scenario_id"),
                    "stop_reason": (scenario.get("final_state") or {}).get("stop_reason")
                    if isinstance(scenario.get("final_state"), dict)
                    else None,
                    "rounds_used": _safe_rounds_used(scenario),
                }
            )

        rows.append(
            {
                "file": path.name,
                "generated_at": generated_at,
                "architect_model": architect_model,
                "auditor_model": auditor_model,
                "scenarios": sorted(scenario_rows, key=lambda item: str(item.get("scenario_id") or "")),
            }
        )
    return rows


def generate_index(input_dir: Path, output_path: Path) -> dict[str, Any]:
    run_rows: list[dict[str, Any]] = []
    for path in sorted(input_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        run_rows.extend(_extract_runs_from_file(path))

    run_rows.sort(
        key=lambda item: (
            str(item.get("file") or ""),
            str(item.get("architect_model") or ""),
            str(item.get("auditor_model") or ""),
        )
    )

    payload = {
        "index_v": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(input_dir).replace("\\", "/"),
        "run_count": len(run_rows),
        "runs": run_rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ODR live role-matrix summary index.")
    parser.add_argument("--input-dir", default="benchmarks/published/ODR")
    parser.add_argument("--out", default="benchmarks/published/ODR/index.json")
    args = parser.parse_args()

    payload = generate_index(input_dir=Path(args.input_dir), output_path=Path(args.out))
    print(f"Wrote {args.out} (runs={payload['run_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
