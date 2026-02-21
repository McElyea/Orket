from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TELEMETRY_KEYS = [
    "internal_model_seconds",
    "orchestration_overhead_ratio",
    "run_quality_reasons",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate orchestration-overhead telemetry consistency.")
    parser.add_argument("--report", required=True, help="Path to benchmark determinism report JSON.")
    parser.add_argument("--out", default="", help="Optional output path for report JSON.")
    return parser.parse_args()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = _parse_args()
    report_path = Path(args.report)
    payload = _load(report_path)
    failures: list[str] = []

    runs = payload.get("test_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        failures.append("report:missing:test_runs")
        runs = []

    for idx, run in enumerate(runs):
        if not isinstance(run, dict):
            failures.append(f"test_runs:{idx}:invalid_type")
            continue
        telemetry = run.get("telemetry")
        if not isinstance(telemetry, dict):
            failures.append(f"test_runs:{idx}:missing:telemetry")
            continue
        outcome = str(run.get("outcome", "")).strip().lower()
        for key in REQUIRED_TELEMETRY_KEYS:
            if key not in telemetry:
                failures.append(f"test_runs:{idx}:{outcome or 'unknown'}:missing:{key}")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "report": str(report_path).replace("\\", "/"),
        "checked_runs": len(runs),
        "required_telemetry_keys": REQUIRED_TELEMETRY_KEYS,
        "failures": failures,
    }
    text = json.dumps(report, indent=2)
    print(text)

    out_text = str(args.out or "").strip()
    if out_text:
        out_path = Path(out_text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

