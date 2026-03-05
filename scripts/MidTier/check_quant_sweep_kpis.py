from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate quant sweep KPI thresholds.")
    parser.add_argument("--summary", required=True, help="Path to sweep_summary.json")
    parser.add_argument("--max-missing-telemetry-rate", type=float, default=0.01)
    parser.add_argument("--max-polluted-run-rate", type=float, default=0.1)
    parser.add_argument("--min-frontier-success-rate", type=float, default=0.8)
    parser.add_argument("--min-determinism-rate", type=float, default=1.0)
    return parser.parse_args()


def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Sweep summary must be a JSON object")
    return payload


def _float_or(value: Any, fallback: float) -> float:
    return float(value) if isinstance(value, (int, float)) else float(fallback)


def main() -> int:
    args = _parse_args()
    summary = _load_summary(Path(args.summary))
    kpis = summary.get("stability_kpis") if isinstance(summary.get("stability_kpis"), dict) else {}
    missing = _float_or(kpis.get("missing_telemetry_rate"), 1.0)
    polluted = _float_or(kpis.get("polluted_run_rate"), 1.0)
    frontier = _float_or(kpis.get("frontier_success_rate"), 0.0)
    determinism = _float_or(kpis.get("determinism_rate"), 0.0)

    failures: list[str] = []
    if missing > float(args.max_missing_telemetry_rate):
        failures.append(
            f"missing_telemetry_rate={missing} exceeds max_missing_telemetry_rate={float(args.max_missing_telemetry_rate)}"
        )
    if polluted > float(args.max_polluted_run_rate):
        failures.append(f"polluted_run_rate={polluted} exceeds max_polluted_run_rate={float(args.max_polluted_run_rate)}")
    if frontier < float(args.min_frontier_success_rate):
        failures.append(
            f"frontier_success_rate={frontier} below min_frontier_success_rate={float(args.min_frontier_success_rate)}"
        )
    if determinism < float(args.min_determinism_rate):
        failures.append(f"determinism_rate={determinism} below min_determinism_rate={float(args.min_determinism_rate)}")

    report = {
        "summary_path": str(Path(args.summary)).replace("\\", "/"),
        "stability_kpis": kpis,
        "thresholds": {
            "max_missing_telemetry_rate": float(args.max_missing_telemetry_rate),
            "max_polluted_run_rate": float(args.max_polluted_run_rate),
            "min_frontier_success_rate": float(args.min_frontier_success_rate),
            "min_determinism_rate": float(args.min_determinism_rate),
        },
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
