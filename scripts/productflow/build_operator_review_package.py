#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit.audit_support import evaluate_run_completeness, load_json_object
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.observability.emit_run_evidence_graph import _run as emit_run_evidence_graph
from scripts.productflow.productflow_support import (
    build_productflow_engine,
    relative_to_workspace,
    resolve_productflow_paths,
    resolve_productflow_run_with_engine,
)

DEFAULT_PROOF_OUTPUT = REPO_ROOT / "benchmarks" / "results" / "productflow" / "operator_review_proof.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the canonical ProductFlow operator review package.")
    parser.add_argument("--run-id", required=True, help="Canonical ProductFlow governed run id.")
    parser.add_argument("--workspace-root", default="", help="Optional ProductFlow workspace root override.")
    parser.add_argument("--output", default=str(DEFAULT_PROOF_OUTPUT), help="Stable rerunnable proof output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted proof payload.")
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
        raise ValueError(f"productflow_review_package_approval_match_count:{len(approval_matches)}")
    approval = approval_matches[0]

    graph_payload = await emit_run_evidence_graph(
        Namespace(
            run_id=resolved_run.run_id,
            workspace_root=str(paths.workspace_root),
            control_plane_db=str(paths.control_plane_db_path),
            session_id=resolved_run.session_id,
            view=[],
            generation_timestamp="",
        )
    )
    completeness = evaluate_run_completeness(workspace=paths.workspace_root, session_id=resolved_run.session_id)
    replay_review_payload = load_json_object(paths.results_root / "replay_review.json")
    if str(replay_review_payload.get("run_id") or "").strip() != resolved_run.run_id:
        replay_review_payload = {}

    run_summary = dict(resolved_run.run_summary)
    packet1 = dict(run_summary.get("truthful_runtime_packet1") or {})
    packet2 = dict(run_summary.get("truthful_runtime_packet2") or {})
    artifact_provenance = dict(run_summary.get("truthful_runtime_artifact_provenance") or {})

    review_index_path = resolved_run.artifact_root / "productflow_review_index.json"
    review_index = {
        "schema_version": "productflow.operator_review_package.v1",
        "generated_at_utc": _now_utc_iso(),
        "run_id": resolved_run.run_id,
        "session_id": resolved_run.session_id,
        "artifact_root": relative_to_workspace(resolved_run.artifact_root, paths.workspace_root),
        "resolution_basis": dict(resolved_run.resolution_basis),
        "run_summary": {
            "path": relative_to_workspace(resolved_run.run_summary_path, paths.workspace_root),
            "status": str(run_summary.get("status") or ""),
            "failure_reason": run_summary.get("failure_reason"),
            "control_plane": dict(run_summary.get("control_plane") or {}),
        },
        "terminal_final_truth": approval.get("control_plane_target_final_truth"),
        "packet1": packet1,
        "packet2": packet2,
        "artifact_provenance": artifact_provenance,
        "approval_continuation_evidence": {
            "approval_id": str(approval.get("approval_id") or ""),
            "approval_status": str(approval.get("status") or ""),
            "approval_operator_action": approval.get("control_plane_operator_action"),
            "control_plane_target_ref": str(approval.get("control_plane_target_ref") or ""),
            "target_run": approval.get("control_plane_target_run"),
            "target_checkpoint": approval.get("control_plane_target_checkpoint"),
            "target_effect_journal": approval.get("control_plane_target_effect_journal"),
            "target_resource": approval.get("control_plane_target_resource"),
            "target_reservation": approval.get("control_plane_target_reservation"),
            "target_operator_action": approval.get("control_plane_target_operator_action"),
            "target_final_truth": approval.get("control_plane_target_final_truth"),
        },
        "run_evidence_graph": {
            "graph_result": str(graph_payload.get("graph_result") or ""),
            "json_path": str(graph_payload.get("json_path") or ""),
            "mermaid_path": str(graph_payload.get("mermaid_path") or ""),
            "html_path": str(graph_payload.get("html_path") or ""),
        },
        "replay_review": {
            "available": bool(replay_review_payload),
            "path": "benchmarks/results/productflow/replay_review.json" if replay_review_payload else "",
            "replay_ready": replay_review_payload.get("replay_ready") if replay_review_payload else completeness.get("replay_ready"),
            "stability_status": replay_review_payload.get("stability_status")
            if replay_review_payload
            else completeness.get("stability_status"),
        },
        "review_questions": _review_questions(
            run_id=resolved_run.run_id,
            run_summary_path=relative_to_workspace(resolved_run.run_summary_path, paths.workspace_root),
            approval=approval,
            graph_payload=graph_payload,
            completeness=completeness,
            replay_review_payload=replay_review_payload,
        ),
    }
    persisted_index = write_payload_with_diff_ledger(review_index_path, review_index)
    questions = list(persisted_index.get("review_questions") or [])
    answered = [row for row in questions if bool((row or {}).get("answerable"))]
    unanswered = [str((row or {}).get("id") or "") for row in questions if not bool((row or {}).get("answerable"))]
    graph_ok = bool(graph_payload.get("ok"))
    proof_payload = {
        "schema_version": "productflow.operator_review_proof.v1",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary",
        "observed_result": "success" if graph_ok and not unanswered else "failure",
        "run_id": resolved_run.run_id,
        "session_id": resolved_run.session_id,
        "review_index_path": relative_to_workspace(review_index_path, paths.workspace_root),
        "answered_question_count": len(answered),
        "required_question_count": len(questions),
        "unanswered_questions": unanswered,
        "replay_ready": completeness.get("replay_ready"),
        "stability_status": (
            replay_review_payload.get("stability_status")
            if replay_review_payload
            else completeness.get("stability_status")
        ),
        "supporting_refs_by_question": {
            str((row or {}).get("id") or ""): list((row or {}).get("supporting_refs") or [])
            for row in questions
            if str((row or {}).get("id") or "").strip()
        },
    }
    return proof_payload


def _review_questions(
    *,
    run_id: str,
    run_summary_path: str,
    approval: dict[str, Any],
    graph_payload: dict[str, Any],
    completeness: dict[str, Any],
    replay_review_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    packet1_refs = [f"{run_summary_path}#truthful_runtime_packet1"]
    packet2_refs = [f"{run_summary_path}#truthful_runtime_packet2"]
    final_truth = approval.get("control_plane_target_final_truth")
    questions = [
        {
            "id": "run_identity",
            "question": "What run is this?",
            "answerable": bool(run_id),
            "supporting_refs": [run_summary_path, f"control_plane:{run_id}"],
        },
        {
            "id": "requested_work",
            "question": "What was requested?",
            "answerable": isinstance(approval.get("payload"), dict),
            "supporting_refs": [f"approval:{approval.get('approval_id')}#payload"],
        },
        {
            "id": "runtime_path",
            "question": "What path did the runtime take?",
            "answerable": bool(graph_payload.get("json_path")) and bool(approval.get("control_plane_target_checkpoint")),
            "supporting_refs": [
                str(graph_payload.get("json_path") or ""),
                f"approval:{approval.get('approval_id')}#control_plane_target_checkpoint",
            ],
        },
        {
            "id": "governed_action",
            "question": "What action or effect was governed?",
            "answerable": bool(approval.get("control_plane_target_effect_journal")),
            "supporting_refs": [
                f"approval:{approval.get('approval_id')}#control_plane_target_effect_journal",
                f"approval:{approval.get('approval_id')}#control_plane_target_operator_action",
            ],
        },
        {
            "id": "terminal_truth",
            "question": "What terminal closure truth was assigned?",
            "answerable": isinstance(final_truth, dict) and bool(final_truth.get("result_class")),
            "supporting_refs": [f"approval:{approval.get('approval_id')}#control_plane_target_final_truth"],
        },
        {
            "id": "packet1_truth",
            "question": "Which packet-1 truth classifications applied?",
            "answerable": True,
            "supporting_refs": packet1_refs,
        },
        {
            "id": "replay_status",
            "question": "Is the run replay_ready and what is its stability_status?",
            "answerable": bool(completeness),
            "supporting_refs": (
                ["benchmarks/results/productflow/replay_review.json"]
                if replay_review_payload
                else [run_summary_path, "benchmarks/results/productflow/operator_review_proof.json"]
            ),
        },
    ]
    return questions


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
                    f"observed_result={persisted.get('observed_result')}",
                    f"run_id={persisted.get('run_id')}",
                    f"review_index={persisted.get('review_index_path')}",
                    f"output={Path(str(args.output)).resolve()}",
                ]
            )
        )
    return 0 if str(persisted.get("observed_result") or "") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
