"""Real outward API/storage fixtures for BT-0; only model output and time are fixtures."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.outward_store_transaction import OutwardStoreUnitOfWork
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.domain.control_plane_effect_journal import validate_effect_journal_chain
from orket.interfaces.api import create_api_app
from tests.helpers.outward_model import FakeOutwardModelClient

TEST_API_KEY = "bt0-local-test-key"


class FixedInputs(RuntimeInputService):
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 11, 12, tzinfo=UTC)

    def utc_now(self) -> datetime:
        return self.now


class SequenceModelClient(FakeOutwardModelClient):
    def __init__(self, calls: list[dict]) -> None:
        super().__init__()
        self.calls = iter(calls)

    async def complete(self, messages, runtime_context=None):
        call = next(self.calls)
        self.tool, self.args = call["tool"], call["args"]
        return await super().complete(messages, runtime_context)


@pytest.fixture
def boundary(tmp_path, monkeypatch):
    """Isolate storage, credentials and model output; keep application/effects real."""
    import orket.application.services.outward_model_tool_call_service as model_module

    db_path = tmp_path / "outward.sqlite3"
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(db_path))
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    calls = [
        {"tool": "write_file", "args": {"path": "first.txt", "content": "first approved effect"}},
        {"tool": "write_file", "args": {"path": "second.txt", "content": "second requires approval"}},
    ]
    model = SequenceModelClient(calls)
    monkeypatch.setattr(model_module, "create_configured_model_client", lambda **_: model)
    return db_path, FixedInputs(), calls


@asynccontextmanager
async def outward_api(root: Path, inputs: FixedInputs, *, api_key: str = TEST_API_KEY):
    environment = dict(os.environ)
    # Fresh subprocess fixtures have no bound settings; their synchronous bootstrap
    # belongs to a retained worker. Runtime acquisition still requires the lifespan.
    app = await run_owned_thread(
        lambda: create_api_app(project_root=root, runtime_inputs=inputs, environment=environment),
        label="outward-test-settings-bootstrap",
    )
    async with app.router.lifespan_context(app):
        context = app.state.api_runtime_context
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://orket.test",
            headers={"X-API-Key": api_key},
            timeout=15,
        ) as client:
            yield client, context
    assert context.closed
    assert context.active_background_task_count == 0


async def submit_sequence(client: AsyncClient, calls: list[dict], *, approval_seconds: int = 300) -> str:
    response = await client.post(
        "/v1/runs",
        json={
            "run_id": "bt0-run",
            "task": {
                "description": "BT-0 local authorization boundary",
                "instruction": "Execute each governed call after its own approval.",
                "acceptance_contract": {"governed_tool_sequence": calls},
            },
            "policy_overrides": {
                "approval_required_tools": sorted({call["tool"] for call in calls}),
                "max_turns": len(calls),
                "approval_timeout_seconds": approval_seconds,
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "approval_required", payload
    return payload["pending_proposals"][0]["proposal_id"]


async def approve(client: AsyncClient, proposal_id: str, *, endpoint: str = "approve"):
    return await client.post(
        f"/v1/approvals/{proposal_id}/{endpoint}",
        json={"decision": "approve"} if endpoint == "decision" else {},
    )


async def approve_in_new_process(root: Path, proposal_id: str, endpoint: str) -> tuple[int, dict]:
    source = """
import asyncio, json, sys
from pathlib import Path
from tests.helpers.outward_authorization import FixedInputs, approve, outward_api

async def main():
    async with outward_api(Path(sys.argv[1]), FixedInputs()) as (client, context):
        response = await approve(client, sys.argv[2], endpoint=sys.argv[3])
        result = [response.status_code, response.json()]
    print('BT0_RESPONSE=' + json.dumps(result))

asyncio.run(main())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", source, str(root), proposal_id, endpoint,
        cwd=await asyncio.to_thread(lambda: Path(__file__).resolve().parents[2]),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode == 0, stderr.decode(errors="replace")
    response = next(line.removeprefix("BT0_RESPONSE=") for line in stdout.decode().splitlines()
                    if line.startswith("BT0_RESPONSE="))
    status, payload = json.loads(response)
    return status, payload


@asynccontextmanager
async def hold_decision_writers(db_path: Path, monkeypatch, *, writers: int = 2):
    """Observe real write attempts while another SQLite connection holds the lock."""
    ready = asyncio.Event()
    connections = set()
    original = aiosqlite.Connection.execute
    async with connect_sqlite_wal(db_path) as lock:
        await lock.execute("BEGIN IMMEDIATE")

        def observe(connection, sql, *args, **kwargs):
            normalized = " ".join(sql.upper().split())
            if normalized == "BEGIN IMMEDIATE" or normalized.startswith("INSERT OR REPLACE INTO OUTWARD_APPROVAL_PROPOSALS"):
                connections.add(id(connection))
                if len(connections) >= writers:
                    ready.set()
            return original(connection, sql, *args, **kwargs)

        try:
            with monkeypatch.context() as patch:
                patch.setattr(aiosqlite.Connection, "execute", observe)
                yield ready
        finally:
            await lock.rollback()


def append_command(monkeypatch):
    import orket.application.services.outward_model_tool_call_service as model_module

    calls = [{"tool": "run_command", "args": {"command": [sys.executable, "-c",
        "from pathlib import Path; f=Path('effects.txt').open('a'); f.write('effect\\n'); f.close()"]}}]
    monkeypatch.setattr(model_module, "create_configured_model_client", lambda **_: SequenceModelClient(calls))
    return calls


async def effect_snapshot(db_path, proposal_id):
    unit = OutwardStoreUnitOfWork(
        approvals=OutwardApprovalStore(db_path), runs=OutwardRunStore(db_path), events=OutwardRunEventStore(db_path),
    )
    async with unit.transaction() as transaction:
        effect = await transaction.effects.get(f"outward-effect:{proposal_id}")
        journal = validate_effect_journal_chain(await transaction.effects.list_journal("bt0-run"))
    return effect, journal
