#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.exceptions import ExecutionFailed
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.productflow.productflow_support import (
    DEFAULT_OPERATOR_ACTOR_REF,
    PRODUCTFLOW_EPIC_ID,
    PRODUCTFLOW_ISSUE_ID,
    PRODUCTFLOW_OUTPUT_CONTENT,
    PRODUCTFLOW_OUTPUT_PATH,
    build_productflow_engine,
    patched_productflow_provider,
    relative_to_workspace,
    reset_productflow_runtime_state,
    resolve_productflow_paths,
)

DEFAULT_OUTPUT = REPO_ROOT / "benchmarks" / "results" / "productflow" / "governed_write_file_live_run.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical ProductFlow governed write_file approval flow.")
    parser.add_argument("--workspace-root", default="", help="Optional ProductFlow workspace root override.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Stable rerunnable JSON output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted payload.")
    return parser.parse_args(argv)


async def _run(*, paths: Any, engine: Any) -> dict[str, Any]:
    first_error: str | None = None

    try:
        await engine.run_card(PRODUCTFLOW_EPIC_ID)
        first_error = "approval_pending_not_observed"
    except ExecutionFailed as exc:
        first_error = str(exc)

    approvals = await engine.list_approvals(status="PENDING", limit=100)
    matches = [
        item
        for item in approvals
        if str(item.get("session_id") or "").strip()
        and str(item.get("issue_id") or "").strip() == PRODUCTFLOW_ISSUE_ID
        and str(item.get("control_plane_target_ref") or "").strip()
        and str(item.get("reason") or "").strip() == "approval_required_tool:write_file"
    ]
    if len(matches) != 1:
        return {
            "schema_version": "productflow.governed_write_file_live_run.v1",
            "recorded_at_utc": _now_utc_iso(),
            "proof_kind": "live",
            "observed_path": "blocked",
            "observed_result": "failure",
            "workspace_root": str(paths.workspace_root),
            "error": "productflow_pending_approval_not_found",
            "pending_approvals_found": len(matches),
            "first_error": first_error,
        }

    approval = matches[0]
    session_id = str(approval["session_id"])
    run_id = str(approval["control_plane_target_ref"])
    pending_run = await engine.control_plane_execution_repository.get_run_record(run_id=run_id)
    pending_truth = await engine.control_plane_repository.get_final_truth(run_id=run_id)
    pending_resource = await engine.control_plane_repository.get_latest_resource_record(
        resource_id=f"namespace:issue:{PRODUCTFLOW_ISSUE_ID}"
    )

    resolved = await engine.decide_approval(
        approval_id=str(approval["approval_id"]),
        decision="approve",
        operator_actor_ref=DEFAULT_OPERATOR_ACTOR_REF,
    )

    final_truth = await engine.control_plane_repository.get_final_truth(run_id=run_id)
    completed_run = await engine.control_plane_execution_repository.get_run_record(run_id=run_id)
    issue = await engine.cards.get_by_id(PRODUCTFLOW_ISSUE_ID)
    output_path = paths.workspace_root / PRODUCTFLOW_OUTPUT_PATH
    run_summary_path = paths.workspace_root / "runs" / session_id / "run_summary.json"
    approval_after = dict(resolved.get("approval") or {})

    issue_status = getattr(issue, "status", None)
    normalized_issue_status = issue_status.value if hasattr(issue_status, "value") else str(issue_status or "")
    success = (
        str(first_error or "").startswith("Approval required for tool 'write_file'")
        and pending_run is not None
        and pending_truth is None
        and pending_resource is not None
        and str(getattr(pending_resource, "resource_kind", "") or "") == "turn_tool_namespace"
        and completed_run is not None
        and getattr(completed_run, "lifecycle_state", None) is not None
        and final_truth is not None
        and output_path.exists()
        and output_path.read_text(encoding="utf-8") == PRODUCTFLOW_OUTPUT_CONTENT
        and normalized_issue_status == "done"
    )
    return {
        "schema_version": "productflow.governed_write_file_live_run.v1",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": "live",
        "observed_path": "primary",
        "observed_result": "success" if success else "partial success",
        "workspace_root": str(paths.workspace_root),
        "config_root": str(paths.config_root),
        "runtime_db_path": str(paths.runtime_db_path),
        "control_plane_db_path": str(paths.control_plane_db_path),
        "session_id": session_id,
        "run_id": run_id,
        "artifact_root": relative_to_workspace(paths.workspace_root / "runs" / session_id, paths.workspace_root),
        "approval_id": str(approval["approval_id"]),
        "approval_status": str(approval_after.get("status") or ""),
        "operator_actor_ref": DEFAULT_OPERATOR_ACTOR_REF,
        "first_pause_error": first_error,
        "pending_pause": {
            "approval_id": str(approval["approval_id"]),
            "request_type": str(approval.get("request_type") or ""),
            "gate_mode": str(approval.get("gate_mode") or ""),
            "reason": str(approval.get("reason") or ""),
            "control_plane_target_ref": run_id,
            "target_checkpoint": approval.get("control_plane_target_checkpoint"),
            "target_resource": approval.get("control_plane_target_resource"),
            "pending_run_state": pending_run.lifecycle_state.value if pending_run is not None else "",
        },
        "continuation": {
            "result_status": str(resolved.get("status") or ""),
            "approval_status": str(approval_after.get("status") or ""),
            "target_operator_action": approval_after.get("control_plane_target_operator_action"),
            "target_effect_journal": approval_after.get("control_plane_target_effect_journal"),
            "target_final_truth": approval_after.get("control_plane_target_final_truth"),
        },
        "run_summary_path": relative_to_workspace(run_summary_path, paths.workspace_root),
        "output_artifact_path": relative_to_workspace(output_path, paths.workspace_root),
        "issue_status": normalized_issue_status,
        "final_truth_result_class": getattr(final_truth, "result_class", None).value if final_truth is not None else "",
        "final_truth_record_id": getattr(final_truth, "final_truth_record_id", None) if final_truth is not None else "",
    }


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    workspace_override = Path(str(args.workspace_root)).resolve() if str(args.workspace_root).strip() else None
    paths = resolve_productflow_paths(workspace_override)
    reset_productflow_runtime_state(paths)
    with patched_productflow_provider():
        engine = build_productflow_engine(paths)
        payload = asyncio.run(_run(paths=paths, engine=engine))
    persisted = write_payload_with_diff_ledger(Path(str(args.output)).resolve(), payload)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"run_id={persisted.get('run_id')}",
                    f"session_id={persisted.get('session_id')}",
                    f"output={Path(str(args.output)).resolve()}",
                ]
            )
        )
    return 0 if str(persisted.get("observed_result") or "") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
