from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate explorer artifact schema contracts.")
    parser.add_argument("--frontier", default="", help="Path to quant frontier explorer artifact.")
    parser.add_argument("--context", default="", help="Path to context ceiling artifact.")
    parser.add_argument("--thermal", default="", help="Path to thermal stability artifact.")
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _check_required(payload: dict[str, Any], required: list[str], label: str, failures: list[str]) -> None:
    for key in required:
        if key not in payload:
            failures.append(f"{label}:missing:{key}")


def _check_common(payload: dict[str, Any], label: str, failures: list[str]) -> None:
    _check_required(payload, ["schema_version", "generated_at", "execution_lane", "vram_profile", "provenance"], label, failures)


def main() -> int:
    args = _parse_args()
    inputs = {
        "frontier": (args.frontier, ["hardware_fingerprint", "model_id", "quant_tag", "sessions"]),
        "context": (args.context, ["hardware_fingerprint", "model_id", "quant_tag", "safe_context_ceiling", "points"]),
        "thermal": (args.thermal, ["hardware_fingerprint", "model_id", "quant_tag", "heat_soak_detected", "points"]),
    }
    failures: list[str] = []
    checked: list[str] = []
    for label, (raw_path, required) in inputs.items():
        path_text = str(raw_path or "").strip()
        if not path_text:
            continue
        path = Path(path_text)
        payload = _load(path)
        _check_common(payload, label, failures)
        _check_required(payload, required, label, failures)
        checked.append(str(path).replace("\\", "/"))
    report = {
        "status": "PASS" if not failures else "FAIL",
        "checked": checked,
        "failures": failures,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
