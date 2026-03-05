from __future__ import annotations

from pathlib import Path
from typing import Any
import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.interfaces.routers.sessions import build_sessions_router


class _StubInteractionManager:
    def stream_enabled(self) -> bool:
        return True

    async def start(self, _params: dict[str, Any]) -> str:
        return "session-1"

    async def begin_turn(self, *, session_id: str, input_payload: dict[str, Any], turn_params: dict[str, Any]) -> str:
        return "turn-1"

    async def create_context(self, _session_id: str, _turn_id: str) -> Any:
        class _Ctx:
            async def request_commit(self, _intent: Any) -> None:
                return None

        return _Ctx()

    async def finalize(self, _session_id: str, _turn_id: str) -> Any:
        class _Handle:
            def model_dump(self) -> dict[str, Any]:
                return {"turn_id": "turn-1", "status": "done"}

        return _Handle()

    async def cancel(self, _target: str) -> None:
        return None


class _StubExtensionManager:
    def resolve_workload(self, _workload_id: str) -> None:
        return None

    async def run_workload(self, **_kwargs: Any) -> None:
        return None


def _build_client(workspace_root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_sessions_router(
            interaction_manager_getter=lambda: _StubInteractionManager(),
            extension_manager_getter=lambda: _StubExtensionManager(),
            is_builtin_workload=lambda _workload_id: False,
            validate_builtin_workload_start=lambda **_kwargs: None,
            run_builtin_workload=lambda **_kwargs: None,
            commit_intent_factory=lambda _reason: {"type": "decision"},
            workspace_root_getter=lambda: workspace_root,
        ),
        prefix="/v1",
    )
    return TestClient(app)


def _write_protocol_run(workspace_root: Path, run_id: str, *, status: str, ok: bool) -> None:
    run_root = workspace_root / "runs" / run_id
    ledger = AppendOnlyRunLedger(run_root / "events.log")
    ledger.append_event(
        {
            "kind": "run_started",
            "session_id": run_id,
            "run_type": "epic",
            "run_name": "Replay",
            "department": "core",
            "build_id": "build-1",
            "status": "running",
            "summary": {"session_status": "running"},
            "artifacts": {"workspace": "workspace/default"},
        }
    )
    ledger.append_event(
        {
            "kind": "operation_result",
            "session_id": run_id,
            "operation_id": "op-1",
            "tool": "write_file",
            "result": {"ok": ok},
        }
    )
    ledger.append_event(
        {
            "kind": "run_finalized",
            "session_id": run_id,
            "status": status,
            "failure_class": None if status == "incomplete" else "ExecutionFailed",
            "failure_reason": None if status == "incomplete" else "failed",
            "summary": {"session_status": status},
            "artifacts": {"gitea_export": {"provider": "gitea"}},
        }
    )


async def _seed_sqlite_run(*, sqlite_db: Path, session_id: str, status: str) -> None:
    sqlite_db.parent.mkdir(parents=True, exist_ok=True)
    sqlite_repo = AsyncRunLedgerRepository(sqlite_db)
    await sqlite_repo.start_run(
        session_id=session_id,
        run_type="epic",
        run_name="Replay",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/default"},
    )
    await sqlite_repo.finalize_run(
        session_id=session_id,
        status=status,
        summary={"session_status": status},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )


def test_sessions_router_replay_protocol_run(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    _write_protocol_run(workspace_root, "run-a", status="incomplete", ok=True)
    client = _build_client(workspace_root)

    response = client.get("/v1/protocol/runs/run-a/replay")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "run-a"
    assert payload["status"] == "incomplete"
    assert payload["operation_count"] == 1


def test_sessions_router_compare_protocol_runs(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    _write_protocol_run(workspace_root, "run-a", status="incomplete", ok=True)
    _write_protocol_run(workspace_root, "run-b", status="failed", ok=False)
    client = _build_client(workspace_root)

    response = client.get("/v1/protocol/replay/compare?run_a=run-a&run_b=run-b")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deterministic_match"] is False
    assert any(row["field"] == "status" for row in payload["differences"])


def test_sessions_router_protocol_run_missing_events_returns_404(tmp_path: Path) -> None:
    client = _build_client(tmp_path / "workspace")
    response = client.get("/v1/protocol/runs/missing/replay")
    assert response.status_code == 404
    assert "Protocol events log not found for run 'missing'" in response.text


def test_sessions_router_protocol_run_rejects_traversal_run_id(tmp_path: Path) -> None:
    client = _build_client(tmp_path / "workspace")
    response = client.get("/v1/protocol/replay/compare?run_a=../../etc&run_b=run-b")
    assert response.status_code == 400
    assert "Invalid run_id" in response.text


def test_sessions_router_protocol_ledger_parity_endpoint(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    sqlite_db = workspace_root / ".orket" / "durable" / "db" / "orket_persistence.db"
    _write_protocol_run(workspace_root, "run-a", status="incomplete", ok=True)
    asyncio.run(_seed_sqlite_run(sqlite_db=sqlite_db, session_id="run-a", status="incomplete"))
    client = _build_client(workspace_root)

    response = client.get(f"/v1/protocol/runs/run-a/ledger-parity?sqlite_db_path={sqlite_db}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["parity_ok"] is True
    assert payload["differences"] == []


def test_sessions_router_protocol_ledger_parity_missing_sqlite_returns_404(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    _write_protocol_run(workspace_root, "run-a", status="incomplete", ok=True)
    client = _build_client(workspace_root)

    missing = tmp_path / "missing.db"
    response = client.get(f"/v1/protocol/runs/run-a/ledger-parity?sqlite_db_path={missing}")
    assert response.status_code == 404
    assert "SQLite run ledger database not found" in response.text


def test_sessions_router_protocol_ledger_parity_reports_mismatch(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    sqlite_db = workspace_root / ".orket" / "durable" / "db" / "orket_persistence.db"
    _write_protocol_run(workspace_root, "run-a", status="failed", ok=False)
    asyncio.run(_seed_sqlite_run(sqlite_db=sqlite_db, session_id="run-a", status="incomplete"))
    client = _build_client(workspace_root)

    response = client.get(f"/v1/protocol/runs/run-a/ledger-parity?sqlite_db_path={sqlite_db}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["parity_ok"] is False
    fields = {row["field"] for row in payload["differences"]}
    assert "status" in fields
