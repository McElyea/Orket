from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
import orket.interfaces.cli as cli_module


def _write_run(workspace: Path, run_id: str, *, status: str, ok: bool) -> None:
    events = workspace / "runs" / run_id / "events.log"
    ledger = AppendOnlyRunLedger(events)
    ledger.append_event(
        {
            "kind": "run_started",
            "session_id": run_id,
            "run_type": "epic",
            "run_name": "CLI Protocol",
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


def _args(**overrides):
    base = {
        "command": "protocol",
        "subcommand": "replay",
        "target": "run-a",
        "seed": None,
        "ref": None,
        "epic": None,
        "card": None,
        "rock": None,
        "department": "core",
        "workspace": "workspace/default",
        "model": None,
        "build_id": None,
        "interactive_conductor": False,
        "driver_steered": False,
        "resume": None,
        "task": None,
        "board": False,
        "loop": False,
        "archive_card": [],
        "archive_build": None,
        "archive_related": [],
        "archive_reason": "manual archive",
        "replay_turn": None,
        "marshaller_request": None,
        "marshaller_proposal": [],
        "marshaller_run_id": None,
        "marshaller_allow_path": [],
        "marshaller_promote": False,
        "marshaller_actor_id": None,
        "marshaller_actor_source": "cli",
        "marshaller_branch": "main",
        "marshaller_inspect_attempt": None,
        "marshaller_list_limit": 20,
        "protocol_run_b": None,
        "protocol_events_a": None,
        "protocol_events_b": None,
        "protocol_artifacts_a": None,
        "protocol_artifacts_b": None,
        "protocol_sqlite_db": None,
        "protocol_strict": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _DummyExtensionManager:
    def __init__(self, *args, **kwargs):
        return None


async def _write_sqlite_run(db_path: Path, run_id: str, *, status: str) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    repo = AsyncRunLedgerRepository(db_path)
    await repo.start_run(
        session_id=run_id,
        run_type="epic",
        run_name="CLI Protocol",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/default"},
    )
    await repo.finalize_run(
        session_id=run_id,
        status=status,
        summary={"session_status": status},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )


@pytest.mark.asyncio
async def test_cli_protocol_replay_prints_summary(monkeypatch, tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace" / "default"
    _write_run(workspace, "run-a", status="incomplete", ok=True)

    monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: None)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="replay",
            target="run-a",
            workspace=str(workspace),
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"session_id": "run-a"' in out
    assert '"status": "incomplete"' in out


@pytest.mark.asyncio
async def test_cli_protocol_compare_strict_reports_mismatch(monkeypatch, tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace" / "default"
    _write_run(workspace, "run-a", status="incomplete", ok=True)
    _write_run(workspace, "run-b", status="failed", ok=False)

    monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: None)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="compare",
            target="run-a",
            protocol_run_b="run-b",
            protocol_strict=True,
            workspace=str(workspace),
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"deterministic_match": false' in out.lower()
    assert "Protocol replay mismatch detected under --protocol-strict." in out


@pytest.mark.asyncio
async def test_cli_protocol_parity_prints_parity_result(monkeypatch, tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace" / "default"
    sqlite_db = workspace / ".orket" / "durable" / "db" / "orket_persistence.db"
    _write_run(workspace, "run-a", status="incomplete", ok=True)
    await _write_sqlite_run(sqlite_db, "run-a", status="incomplete")

    monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: None)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="parity",
            target="run-a",
            protocol_sqlite_db=str(sqlite_db),
            workspace=str(workspace),
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"parity_ok": true' in out.lower()


@pytest.mark.asyncio
async def test_cli_protocol_parity_strict_reports_mismatch(monkeypatch, tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace" / "default"
    sqlite_db = workspace / ".orket" / "durable" / "db" / "orket_persistence.db"
    _write_run(workspace, "run-a", status="failed", ok=False)
    await _write_sqlite_run(sqlite_db, "run-a", status="incomplete")

    monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: None)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="parity",
            target="run-a",
            protocol_sqlite_db=str(sqlite_db),
            protocol_strict=True,
            workspace=str(workspace),
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"parity_ok": false' in out.lower()
    assert "Run ledger parity mismatch detected under --protocol-strict." in out


@pytest.mark.asyncio
async def test_cli_protocol_parity_missing_sqlite_reports_error(monkeypatch, tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace" / "default"
    _write_run(workspace, "run-a", status="incomplete", ok=True)

    missing_db = workspace / "missing.db"
    monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: None)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="parity",
            target="run-a",
            protocol_sqlite_db=str(missing_db),
            workspace=str(workspace),
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert "SQLite run ledger database not found" in out
