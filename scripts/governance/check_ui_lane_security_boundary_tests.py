from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.decision_nodes.api_runtime_strategy_node import DefaultApiRuntimeStrategyNode
from orket.interfaces import api as api_module
from orket.interfaces.routers.companion import _raise_companion_http_error
from orket.runtime.state_transition_registry import state_transition_registry_snapshot
from orket.runtime.ui_lane_security_boundary_test_contract import (
    ui_lane_security_boundary_test_contract_snapshot,
    validate_ui_lane_security_boundary_test_contract,
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
    parser = argparse.ArgumentParser(description="Check UI lane security boundary tests.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def _explorer_path_traversal_blocked() -> dict[str, Any]:
    strategy = DefaultApiRuntimeStrategyNode()
    with tempfile.TemporaryDirectory(prefix="ui-lane-boundary-") as tmp_dir:
        project_root = Path(tmp_dir).resolve()
        resolved = strategy.resolve_explorer_path(project_root, "../../secrets.txt")
    return {
        "check": "explorer_path_traversal_blocked",
        "ok": resolved is None,
    }


def _session_workspace_escape_blocked() -> dict[str, Any]:
    try:
        _ = api_module._validate_session_path("../../secrets")
    except HTTPException as exc:
        return {
            "check": "session_workspace_escape_blocked",
            "ok": int(exc.status_code) == 400,
            "status_code": int(exc.status_code),
        }
    return {
        "check": "session_workspace_escape_blocked",
        "ok": False,
        "status_code": 200,
    }


def _companion_error_mapping_is_structured() -> dict[str, Any]:
    try:
        _raise_companion_http_error(ValueError("E_UI_BOUNDARY_TEST:blocked"))
    except HTTPException as exc:
        detail = exc.detail
        detail_payload = detail if isinstance(detail, dict) else {}
        return {
            "check": "companion_error_mapping_is_structured",
            "ok": int(exc.status_code) == 400
            and str(detail_payload.get("code") or "").strip() == "E_UI_BOUNDARY_TEST"
            and str(detail_payload.get("message") or "").strip() == "E_UI_BOUNDARY_TEST:blocked",
            "status_code": int(exc.status_code),
        }
    return {
        "check": "companion_error_mapping_is_structured",
        "ok": False,
        "status_code": 200,
    }


def _ui_state_registry_blocked_boundary_enforced() -> dict[str, Any]:
    snapshot = state_transition_registry_snapshot()
    domains = list(snapshot.get("domains") or [])
    ui_domain = next(
        (
            row
            for row in domains
            if isinstance(row, dict) and str(row.get("domain") or "").strip() == "ui"
        ),
        None,
    )
    blocked_targets: list[str] = []
    transitions = (ui_domain or {}).get("transitions")
    if isinstance(transitions, list):
        blocked_row = next(
            (
                row
                for row in transitions
                if isinstance(row, dict) and str(row.get("from") or "").strip() == "blocked"
            ),
            None,
        )
        blocked_targets = list((blocked_row or {}).get("to") or [])
    elif isinstance(transitions, dict):
        blocked_targets = list(transitions.get("blocked") or [])
    normalized = {str(token).strip() for token in blocked_targets if str(token).strip()}
    return {
        "check": "ui_state_registry_blocked_boundary_enforced",
        "ok": normalized == {"ready", "degraded"},
        "blocked_targets": sorted(normalized),
    }


def evaluate_ui_lane_security_boundary_tests() -> dict[str, Any]:
    contract = ui_lane_security_boundary_test_contract_snapshot()
    try:
        check_ids = list(validate_ui_lane_security_boundary_test_contract(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    check_map = {
        "explorer_path_traversal_blocked": _explorer_path_traversal_blocked,
        "session_workspace_escape_blocked": _session_workspace_escape_blocked,
        "companion_error_mapping_is_structured": _companion_error_mapping_is_structured,
        "ui_state_registry_blocked_boundary_enforced": _ui_state_registry_blocked_boundary_enforced,
    }
    checks = [check_map[check_id]() for check_id in check_ids]
    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "check_count": len(check_ids),
        "checks": checks,
        "contract": contract,
    }


def check_ui_lane_security_boundary_tests(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_ui_lane_security_boundary_tests()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_ui_lane_security_boundary_tests(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
