from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.outward_ledger_service import OutwardLedgerService
from orket.application.services.outward_run_inspection_service import OutwardRunInspectionService
from orket.runtime.run_evidence_graph import (
    RUN_EVIDENCE_GRAPH_DEFAULT_VIEWS,
    write_run_evidence_graph_artifact,
)
from orket.runtime.run_evidence_graph_projection import project_run_evidence_graph_primary_lineage
from orket.runtime.run_evidence_graph_rendering import (
    write_run_evidence_graph_rendered_artifacts,
)
from orket.runtime.run_summary import validate_run_summary_payload
from orket.runtime_paths import resolve_control_plane_db_path

def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit the canonical run-evidence graph artifact family.")
    parser.add_argument("--run-id", required=True, help="Selected control-plane run id.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root containing runs/<session_id>/.")
    parser.add_argument("--control-plane-db", default="", help="Optional control-plane SQLite path override.")
    parser.add_argument("--outward-pipeline-db", default="", help="Optional outward pipeline SQLite path override.")
    parser.add_argument("--session-id", default="", help="Optional session id override.")
    parser.add_argument(
        "--view",
        action="append",
        default=[],
        help="Optional selected view token. Repeat to limit rendered views.",
    )
    parser.add_argument(
        "--generation-timestamp",
        default="",
        help="Optional ISO timestamp override for deterministic proof runs.",
    )
    return parser.parse_args(argv)

async def _run(args: argparse.Namespace) -> dict[str, Any]:
    workspace_root = Path(args.workspace_root).resolve()
    requested_run_id = str(args.run_id or "").strip()
    selected_views = _selected_views(args.view)
    session_id = await _locate_session_id(
        workspace_root=workspace_root,
        run_id=requested_run_id,
        explicit_session_id=str(args.session_id or "").strip(),
    )
    if not session_id:
        outward_payload = await _run_outward_graph(
            args=args,
            workspace_root=workspace_root,
            run_id=requested_run_id,
            selected_views=selected_views,
        )
        if outward_payload is not None:
            return outward_payload
        return {
            "schema_version": "1.0",
            "ok": False,
            "run_id": requested_run_id,
            "graph_result": "blocked",
            "error_code": "E_RUN_SESSION_NOT_LOCATED",
            "detail": "Unable to truthfully locate runs/<session_id>/ for the selected run id.",
            "selected_views": selected_views,
        }
    run_id = _resolve_effective_run_id(
        workspace_root=workspace_root,
        session_id=session_id,
        requested_run_id=requested_run_id,
    )

    generation_timestamp = str(args.generation_timestamp or "").strip() or _now_utc_iso()
    control_plane_db_path = resolve_control_plane_db_path(str(args.control_plane_db or "").strip() or None)
    execution_repository = AsyncControlPlaneExecutionRepository(control_plane_db_path)
    record_repository = AsyncControlPlaneRecordRepository(control_plane_db_path)
    payload = await project_run_evidence_graph_primary_lineage(
        root=workspace_root,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=generation_timestamp,
        execution_repository=execution_repository,
        record_repository=record_repository,
        selected_views=selected_views,
    )
    json_path = await write_run_evidence_graph_artifact(
        root=workspace_root,
        session_id=session_id,
        payload=payload,
    )
    rendered = await write_run_evidence_graph_rendered_artifacts(
        root=workspace_root,
        session_id=session_id,
        payload=payload,
    )
    return {
        "schema_version": "1.0",
        "ok": str(payload.get("graph_result") or "") != "blocked",
        "run_id": run_id,
        "requested_run_id": requested_run_id,
        "session_id": session_id,
        "graph_result": payload["graph_result"],
        "selected_views": payload["selected_views"],
        "json_path": str(json_path).replace("\\", "/"),
        "mermaid_path": str(rendered["mermaid_path"]).replace("\\", "/"),
        "html_path": str(rendered["html_path"]).replace("\\", "/"),
        "issue_count": len(payload.get("issues", [])),
    }

async def _run_outward_graph(
    *,
    args: argparse.Namespace,
    workspace_root: Path,
    run_id: str,
    selected_views: list[str],
) -> dict[str, Any] | None:
    db_path = _outward_pipeline_db_path(args)
    run_store = OutwardRunStore(db_path)
    event_store = OutwardRunEventStore(db_path)
    approval_store = OutwardApprovalStore(db_path)
    run = await run_store.get(run_id)
    if run is None:
        return None

    generation_timestamp = str(args.generation_timestamp or "").strip() or _now_utc_iso()
    ledger_service = OutwardLedgerService(run_store=run_store, event_store=event_store, utc_now=lambda: generation_timestamp)
    ledger = await ledger_service.export(run_id, types=("all",), include_pii=False, record_request=False)
    inspection = OutwardRunInspectionService(run_store=run_store, event_store=event_store)
    events_payload = await inspection.events(run_id, limit=5000)
    summary_payload = await inspection.summary(run_id)
    proposals = await approval_store.list(run_id=run_id, status=None, limit=500)
    payload = _outward_graph_payload(
        run=run.to_status_payload(),
        events=events_payload["events"],
        summary=summary_payload,
        proposals=[proposal.to_decision_payload() for proposal in proposals],
        ledger=ledger,
        selected_views=selected_views,
        generation_timestamp=generation_timestamp,
    )
    graph_dir = _outward_graph_dir(workspace_root=workspace_root, namespace=run.namespace, run_id=run.run_id)
    graph_dir.mkdir(parents=True, exist_ok=True)
    json_path = graph_dir / "run_evidence_graph.json"
    svg_path = graph_dir / "run_evidence_graph.svg"
    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    svg_path.write_text(_outward_graph_svg(payload), encoding="utf-8")
    return {
        "schema_version": "1.0",
        "ok": True,
        "run_id": run.run_id,
        "requested_run_id": run_id,
        "session_id": None,
        "graph_kind": "outward_pipeline",
        "graph_result": payload["graph_result"],
        "selected_views": payload["selected_views"],
        "json_path": str(json_path).replace("\\", "/"),
        "svg_path": str(svg_path).replace("\\", "/"),
        "event_count": len(payload["events"]),
        "proposal_count": len(payload["proposals"]),
        "tool_invocation_count": len(payload["tool_invocations"]),
        "ledger_hash": payload["ledger_references"]["ledger_hash"],
    }

def _outward_pipeline_db_path(args: argparse.Namespace) -> Path:
    explicit = str(getattr(args, "outward_pipeline_db", "") or "").strip()
    if explicit:
        return Path(explicit)
    env_path = str(os.getenv("ORKET_OUTWARD_PIPELINE_DB_PATH") or "").strip()
    if env_path:
        return Path(env_path)
    control_plane = str(getattr(args, "control_plane_db", "") or "").strip()
    return resolve_control_plane_db_path(control_plane or None)

def _outward_graph_payload(
    *,
    run: dict[str, Any],
    events: list[dict[str, Any]],
    summary: dict[str, Any],
    proposals: list[dict[str, Any]],
    ledger: dict[str, Any],
    selected_views: list[str],
    generation_timestamp: str,
) -> dict[str, Any]:
    tool_invocations = [event for event in events if event.get("event_type") == "tool_invoked"]
    nodes = [
        {"id": f"run:{run['run_id']}", "kind": "outward_run", "label": run["run_id"], "status": run["status"]},
        {
            "id": f"ledger:{run['run_id']}",
            "kind": "ledger_reference",
            "label": str((ledger.get("canonical") or {}).get("ledger_hash") or ""),
        },
    ]
    nodes.extend(
        {
            "id": f"event:{event['event_id']}",
            "kind": "run_event",
            "label": event["event_type"],
            "event_hash": event.get("event_hash"),
            "chain_hash": event.get("chain_hash"),
        }
        for event in events
    )
    nodes.extend(
        {"id": f"proposal:{proposal['proposal_id']}", "kind": "approval_proposal", "label": proposal["tool"]}
        for proposal in proposals
    )
    edges = [{"from": f"run:{run['run_id']}", "to": f"event:{events[0]['event_id']}", "kind": "starts"}] if events else []
    edges.extend(
        {"from": f"event:{left['event_id']}", "to": f"event:{right['event_id']}", "kind": "ordered_after"}
        for left, right in zip(events, events[1:], strict=False)
    )
    proposal_event_ids = [event["event_id"] for event in events if event.get("event_type") == "proposal_made"]
    for proposal in proposals:
        if proposal_event_ids:
            edges.append({"from": f"event:{proposal_event_ids.pop(0)}", "to": f"proposal:{proposal['proposal_id']}", "kind": "created"})
    edges.append({"from": f"event:{events[-1]['event_id']}", "to": f"ledger:{run['run_id']}", "kind": "hashes_to"} if events else {})
    return {
        "schema_version": "outward_run_evidence_graph.v1",
        "graph_kind": "outward_pipeline",
        "graph_result": "complete",
        "generated_at": generation_timestamp,
        "run_id": run["run_id"],
        "namespace": run["namespace"],
        "selected_views": selected_views,
        "run": run,
        "summary": summary,
        "events": events,
        "proposals": proposals,
        "tool_invocations": tool_invocations,
        "ledger_references": {
            "schema_version": ledger.get("schema_version"),
            "export_scope": ledger.get("export_scope"),
            "ledger_hash": (ledger.get("canonical") or {}).get("ledger_hash"),
            "event_count": ((ledger.get("canonical") or {}).get("event_count")),
            "verification_result": (ledger.get("verification") or {}).get("result"),
        },
        "nodes": [node for node in nodes if node],
        "edges": [edge for edge in edges if edge],
    }

def _outward_graph_dir(*, workspace_root: Path, namespace: str, run_id: str) -> Path:
    root = (workspace_root / "workspace").resolve()
    path = (root / _slug(namespace) / "runs" / _slug(run_id)).resolve()
    if not path.is_relative_to(root):
        raise ValueError("outward graph path escaped workspace root")
    return path

def _slug(value: str) -> str:
    token = "".join(char if char.isalnum() or char in "._-" else "_" for char in str(value or "").strip())
    return token.strip("._-")[:120] or "default"

def _outward_graph_svg(payload: dict[str, Any]) -> str:
    nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
    height = max(160, 70 + len(nodes) * 28)
    rows = []
    for index, node in enumerate(nodes[:40]):
        y = 50 + index * 28
        label = html.escape(f"{node.get('kind')}: {node.get('label')}")
        rows.append(f'<text x="24" y="{y}" font-size="13" font-family="Consolas, monospace">{label}</text>')
    title = html.escape(f"Outward run evidence graph: {payload.get('run_id')}")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">\n'
        '<rect width="1200" height="100%" fill="#ffffff"/>\n'
        f'<text x="24" y="28" font-size="18" font-family="Arial, sans-serif" font-weight="700">{title}</text>\n'
        + "\n".join(rows)
        + "\n</svg>\n"
    )

async def _locate_session_id(
    *,
    workspace_root: Path,
    run_id: str,
    explicit_session_id: str,
) -> str:
    if explicit_session_id:
        return explicit_session_id
    runs_root = workspace_root / "runs"
    if not runs_root.exists():
        return ""
    for candidate in _session_id_candidates(run_id):
        if (runs_root / candidate).exists():
            return candidate
    for session_root in sorted(runs_root.iterdir(), key=lambda path: path.name):
        if not session_root.is_dir():
            continue
        if _run_summary_matches(run_summary_path=session_root / "run_summary.json", run_id=run_id):
            return session_root.name
    ledger_repository = AsyncProtocolRunLedgerRepository(workspace_root)
    for session_root in sorted(runs_root.iterdir(), key=lambda path: path.name):
        if not session_root.is_dir() or not (session_root / "events.log").exists():
            continue
        ledger_run = await ledger_repository.get_run(session_root.name)
        summary = dict(ledger_run.get("summary_json") or {}) if isinstance(ledger_run, dict) else {}
        if _validated_summary_matches(payload=summary, run_id=run_id):
            return session_root.name
    return ""

def _selected_views(raw_views: list[str]) -> list[str]:
    normalized = [str(view or "").strip() for view in raw_views if str(view or "").strip()]
    if not normalized:
        return list(RUN_EVIDENCE_GRAPH_DEFAULT_VIEWS)
    deduped = []
    seen: set[str] = set()
    for view in normalized:
        if view in seen:
            continue
        seen.add(view)
        deduped.append(view)
    return deduped

def _session_id_candidates(run_id: str) -> list[str]:
    candidates: list[str] = []
    tokens = [token.strip() for token in str(run_id or "").split(":") if token.strip()]
    if len(tokens) >= 2 and tokens[0].endswith("-run"):
        candidates.append(tokens[1])
    if run_id:
        candidates.append(str(run_id))
    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered

def _run_summary_matches(*, run_summary_path: Path, run_id: str) -> bool:
    if not run_summary_path.exists():
        return False
    try:
        payload = json.loads(run_summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return _validated_summary_matches(payload=payload, run_id=run_id)

def _validated_summary_matches(*, payload: Any, run_id: str) -> bool:
    if not isinstance(payload, dict):
        return False
    try:
        validate_run_summary_payload(payload)
    except ValueError:
        return False
    if str(payload.get("run_id") or "").strip() == run_id:
        return True
    control_plane = payload.get("control_plane")
    return isinstance(control_plane, dict) and str(control_plane.get("run_id") or "").strip() == run_id

def _resolve_effective_run_id(*, workspace_root: Path, session_id: str, requested_run_id: str) -> str:
    run_summary_path = workspace_root / "runs" / session_id / "run_summary.json"
    if not run_summary_path.exists():
        return requested_run_id
    try:
        payload = json.loads(run_summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return requested_run_id
    if not isinstance(payload, dict):
        return requested_run_id
    control_plane = payload.get("control_plane")
    control_plane_run_id = str(control_plane.get("run_id") or "").strip() if isinstance(control_plane, dict) else ""
    if not control_plane_run_id:
        return requested_run_id
    summary_run_id = str(payload.get("run_id") or "").strip()
    if requested_run_id in {"", session_id, summary_run_id}:
        return control_plane_run_id
    return requested_run_id

def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = asyncio.run(_run(args))
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if bool(payload.get("ok")) else 1

if __name__ == "__main__":
    raise SystemExit(main())
