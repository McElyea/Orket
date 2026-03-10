from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.capability_fallback_hierarchy import (
    capability_fallback_hierarchy_snapshot,
    validate_capability_fallback_hierarchy,
)

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import importlib.util

    helper_path = Path(__file__).resolve().parents[1] / "common" / "rerun_diff_ledger.py"
    spec = importlib.util.spec_from_file_location("rerun_diff_ledger", helper_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"E_DIFF_LEDGER_HELPER_LOAD_FAILED:{helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_payload_with_diff_ledger = module.write_payload_with_diff_ledger


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check capability fallback hierarchy contract.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_capability_fallback_hierarchy() -> dict[str, Any]:
    snapshot = capability_fallback_hierarchy_snapshot()
    try:
        hierarchy = validate_capability_fallback_hierarchy(snapshot)
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "snapshot": snapshot,
        }

    fallback_hierarchy = dict(hierarchy.get("fallback_hierarchy") or {})
    return {
        "schema_version": "1.0",
        "ok": True,
        "capability_count": len(fallback_hierarchy),
        "capabilities": sorted(fallback_hierarchy.keys()),
        "snapshot": snapshot,
    }


def check_capability_fallback_hierarchy(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_capability_fallback_hierarchy()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_capability_fallback_hierarchy(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
