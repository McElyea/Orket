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

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.run_evidence_graph import (
    RUN_EVIDENCE_GRAPH_VIEW_ORDER,
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
    run_id = str(args.run_id or "").strip()
    selected_views = _selected_views(args.view)
    session_id = await _locate_session_id(
        workspace_root=workspace_root,
        run_id=run_id,
        explicit_session_id=str(args.session_id or "").strip(),
    )
    if not session_id:
        return {
            "schema_version": "1.0",
            "ok": False,
            "run_id": run_id,
            "graph_result": "blocked",
            "error_code": "E_RUN_SESSION_NOT_LOCATED",
            "detail": "Unable to truthfully locate runs/<session_id>/ for the selected run id.",
            "selected_views": selected_views,
        }

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
        "session_id": session_id,
        "graph_result": payload["graph_result"],
        "selected_views": payload["selected_views"],
        "json_path": str(json_path).replace("\\", "/"),
        "mermaid_path": str(rendered["mermaid_path"]).replace("\\", "/"),
        "html_path": str(rendered["html_path"]).replace("\\", "/"),
        "issue_count": len(payload.get("issues", [])),
    }


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
        return list(RUN_EVIDENCE_GRAPH_VIEW_ORDER)
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


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = asyncio.run(_run(args))
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
