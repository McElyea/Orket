from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orket.runtime.offline_mode import (  # noqa: E402
    OFFLINE_CAPABILITY_MATRIX,
    assert_default_offline_surface,
    resolve_network_mode,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate offline capability matrix contract.")
    parser.add_argument(
        "--matrix-doc",
        default="docs/projects/core-pillars/09-OFFLINE-CAPABILITY-MATRIX.md",
        help="Offline capability matrix document path.",
    )
    parser.add_argument("--out", default="benchmarks/results/offline_matrix_check.json")
    parser.add_argument("--require-default-offline", action="store_true")
    return parser.parse_args()


def _doc_includes_commands(text: str, commands: List[str]) -> List[str]:
    lowered = text.lower()
    missing: List[str] = []
    for command in commands:
        token = f"`{command}`"
        if token.lower() not in lowered:
            missing.append(command)
    return missing


def main() -> int:
    args = _parse_args()
    failures: List[str] = []
    required_commands = ["init", "api_add", "refactor"]

    doc_path = Path(args.matrix_doc)
    if not doc_path.exists():
        failures.append(f"missing_matrix_doc:{doc_path.as_posix()}")
        doc_text = ""
    else:
        doc_text = doc_path.read_text(encoding="utf-8")
        missing_in_doc = _doc_includes_commands(doc_text, required_commands)
        if missing_in_doc:
            failures.extend(f"doc_missing_command:{name}" for name in missing_in_doc)

    for command in required_commands:
        if command not in OFFLINE_CAPABILITY_MATRIX:
            failures.append(f"matrix_missing_command:{command}")

    mode = ""
    try:
        mode = resolve_network_mode()
    except Exception as exc:
        failures.append(f"default_network_mode_error:{type(exc).__name__}:{exc}")
    if mode != "offline":
        failures.append(f"default_network_mode_not_offline:{mode}")

    if args.require_default_offline:
        try:
            assert_default_offline_surface(required_commands)
        except Exception as exc:
            failures.append(f"default_offline_surface_failed:{type(exc).__name__}:{exc}")

    payload: Dict[str, Any] = {
        "ok": len(failures) == 0,
        "status": "PASS" if not failures else "FAIL",
        "matrix_doc": str(doc_path).replace("\\", "/"),
        "default_network_mode": mode or "<unresolved>",
        "required_commands": required_commands,
        "failure_count": len(failures),
        "failures": failures,
    }
    out_path = Path(str(args.out))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
