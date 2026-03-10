from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.runtime_boundary_audit_checklist import (
    runtime_boundary_audit_checklist_snapshot,
    validate_runtime_boundary_audit_checklist,
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
    parser = argparse.ArgumentParser(description="Check runtime boundary audit checklist contract.")
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root used to validate boundary paths.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_runtime_boundary_audit_checklist(*, workspace: Path) -> dict[str, Any]:
    snapshot = runtime_boundary_audit_checklist_snapshot()
    try:
        boundary_ids = list(validate_runtime_boundary_audit_checklist(snapshot, workspace_root=workspace))
        return {
            "schema_version": "1.0",
            "ok": True,
            "boundary_count": len(boundary_ids),
            "boundary_ids": boundary_ids,
            "snapshot": snapshot,
        }
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "snapshot": snapshot,
        }


def check_runtime_boundary_audit_checklist(
    *,
    workspace: Path,
    out_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = evaluate_runtime_boundary_audit_checklist(workspace=workspace)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    workspace = Path(args.workspace).resolve()
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_runtime_boundary_audit_checklist(
        workspace=workspace,
        out_path=out_path,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
