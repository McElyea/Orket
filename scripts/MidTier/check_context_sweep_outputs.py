from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate context sweep output coverage.")
    parser.add_argument("--contexts", required=True, help="Comma-separated contexts")
    parser.add_argument("--summary-template", required=True, help="Template with {context}")
    parser.add_argument("--context-ceiling", required=True, help="Path to context ceiling artifact")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def main() -> int:
    args = _parse_args()
    contexts = [int(token.strip()) for token in str(args.contexts).split(",") if token.strip()]
    if not contexts:
        raise SystemExit("No contexts provided")
    missing_files: list[str] = []
    found_files: list[str] = []
    for context in contexts:
        path = Path(str(args.summary_template).format(context=context))
        if path.exists():
            found_files.append(str(path).replace("\\", "/"))
        else:
            missing_files.append(str(path).replace("\\", "/"))

    ceiling_path = Path(args.context_ceiling)
    ceiling_exists = ceiling_path.exists()
    coverage_missing: list[int] = []
    if ceiling_exists:
        ceiling = _load_json(ceiling_path)
        points = ceiling.get("points") if isinstance(ceiling.get("points"), list) else []
        present_contexts = {
            int(point.get("context"))
            for point in points
            if isinstance(point, dict) and isinstance(point.get("context"), int)
        }
        coverage_missing = [ctx for ctx in contexts if ctx not in present_contexts]
    else:
        coverage_missing = list(contexts)

    failures: list[str] = []
    if missing_files:
        failures.append("MISSING_CONTEXT_SUMMARY_FILES")
    if not ceiling_exists:
        failures.append("MISSING_CONTEXT_CEILING_ARTIFACT")
    if coverage_missing:
        failures.append("MISSING_CONTEXT_POINTS_IN_CEILING")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "contexts": contexts,
        "summary_files_found": found_files,
        "summary_files_missing": missing_files,
        "context_ceiling_exists": ceiling_exists,
        "coverage_missing_contexts": coverage_missing,
        "failures": failures,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
