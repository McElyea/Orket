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

from scripts.audit.audit_support import evaluate_run_completeness
from scripts.audit.replay_turn import replay_turn_report
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.productflow.productflow_support import (
    build_productflow_engine,
    patched_productflow_provider,
    resolve_productflow_paths,
    resolve_productflow_run_with_engine,
)

DEFAULT_OUTPUT = REPO_ROOT / "benchmarks" / "results" / "productflow" / "replay_review.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical ProductFlow replay review.")
    parser.add_argument("--run-id", required=True, help="Canonical ProductFlow governed run id.")
    parser.add_argument("--workspace-root", default="", help="Optional ProductFlow workspace root override.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Stable rerunnable JSON output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted payload.")
    return parser.parse_args(argv)


async def _run(*, paths: Any, engine: Any, run_id: str) -> dict[str, Any]:
    resolved_run = await resolve_productflow_run_with_engine(
        run_id=run_id,
        engine=engine,
        workspace_root=paths.workspace_root,
    )
    approvals = await engine.list_approvals(session_id=resolved_run.session_id, limit=1000)
    approval_matches = [
        item
        for item in approvals
        if str(item.get("control_plane_target_ref") or "").strip() == resolved_run.run_id
        and str(item.get("reason") or "").strip() == "approval_required_tool:write_file"
    ]
    if len(approval_matches) != 1:
        raise ValueError(f"productflow_replay_review_approval_match_count:{len(approval_matches)}")
    approval = approval_matches[0]
    payload = dict(approval.get("payload") or {})
    issue_id = str(approval.get("issue_id") or payload.get("issue_id") or "").strip()
    turn_index = int(payload.get("turn_index") or 0)
    role = str(approval.get("seat_name") or payload.get("role") or "").strip() or None
    if not issue_id or turn_index <= 0:
        raise ValueError("productflow_replay_review_turn_identity_missing")

    completeness = evaluate_run_completeness(workspace=paths.workspace_root, session_id=resolved_run.session_id)
    replay_ready = bool(completeness.get("replay_ready"))
    replay_payload: dict[str, Any] = {}
    if replay_ready:
        with patched_productflow_provider():
            replay_payload = await replay_turn_report(
                workspace=paths.workspace_root,
                session_id=resolved_run.session_id,
                issue_id=issue_id,
                turn_index=turn_index,
                role=role,
            )
    stability_status = (
        str(replay_payload.get("stability_status") or "").strip()
        if replay_payload
        else str(completeness.get("stability_status") or "").strip()
    )
    claim_tier = "replay_deterministic" if replay_ready and stability_status == "stable" else "non_deterministic_lab_only"
    control_plane = dict(resolved_run.run_summary.get("control_plane") or {})
    return {
        "schema_version": "productflow.replay_review.v1",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": str(replay_payload.get("proof_kind") or "structural"),
        "observed_path": str(replay_payload.get("observed_path") or "blocked"),
        "observed_result": (
            str(replay_payload.get("observed_result") or "")
            if replay_payload
            else ("failure" if replay_ready else "partial success")
        ),
        "run_id": resolved_run.run_id,
        "session_id": resolved_run.session_id,
        "issue_id": issue_id,
        "turn_index": turn_index,
        "role": role,
        "replay_ready": replay_ready,
        "stability_status": stability_status,
        "claim_tier": claim_tier,
        "compare_scope": "productflow_governed_write_file_turn_replay_v1",
        "operator_surface": "audit.replay_turn.v1",
        "policy_digest": str(control_plane.get("policy_digest") or ""),
        "control_bundle_ref": f"runs/{resolved_run.session_id}/run_summary.json#control_plane",
        "evidence_ref": f"runs/{resolved_run.session_id}/productflow_review_index.json",
        "replay_turn": replay_payload,
        "missing_evidence": list(completeness.get("missing_evidence") or []),
    }


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    workspace_override = Path(str(args.workspace_root)).resolve() if str(args.workspace_root).strip() else None
    paths = resolve_productflow_paths(workspace_override)
    engine = build_productflow_engine(paths)
    payload = asyncio.run(_run(paths=paths, engine=engine, run_id=str(args.run_id)))
    persisted = write_payload_with_diff_ledger(Path(str(args.output)).resolve(), payload)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"replay_ready={persisted.get('replay_ready')}",
                    f"stability_status={persisted.get('stability_status')}",
                    f"run_id={persisted.get('run_id')}",
                    f"output={Path(str(args.output)).resolve()}",
                ]
            )
        )
    stable_or_truthful = str(persisted.get("stability_status") or "") in {"stable", "diverged", "blocked", "not_evaluable"}
    return 0 if stable_or_truthful else 1


if __name__ == "__main__":
    raise SystemExit(main())
