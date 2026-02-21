from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate context rollup consistency against context ceiling artifact.")
    parser.add_argument("--rollup", required=True)
    parser.add_argument("--context-ceiling", required=True)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    rollup = _load(Path(args.rollup))
    ceiling = _load(Path(args.context_ceiling))

    failures: list[str] = []
    if str(rollup.get("schema_version") or "") != "explorer.context_sweep_rollup.v1":
        failures.append("INVALID_ROLLUP_SCHEMA_VERSION")
    for key in ["execution_lane", "vram_profile", "provenance", "safe_context_ceiling", "contexts_total", "contexts_passed", "contexts_failed"]:
        if key not in rollup:
            failures.append(f"MISSING_ROLLUP_FIELD:{key}")

    points = ceiling.get("points") if isinstance(ceiling.get("points"), list) else []
    total = len(points)
    passed = sum(1 for point in points if isinstance(point, dict) and bool(point.get("passed")))
    failed = total - passed
    if int(rollup.get("contexts_total", -1)) != total:
        failures.append("TOTAL_COUNT_MISMATCH")
    if int(rollup.get("contexts_passed", -1)) != passed:
        failures.append("PASSED_COUNT_MISMATCH")
    if int(rollup.get("contexts_failed", -1)) != failed:
        failures.append("FAILED_COUNT_MISMATCH")
    if rollup.get("safe_context_ceiling") != ceiling.get("safe_context_ceiling"):
        failures.append("SAFE_CEILING_MISMATCH")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "rollup": str(Path(args.rollup)).replace("\\", "/"),
        "context_ceiling": str(Path(args.context_ceiling)).replace("\\", "/"),
        "failures": failures,
    }
    text = json.dumps(report, indent=2)
    print(text)
    if str(args.out or "").strip():
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
