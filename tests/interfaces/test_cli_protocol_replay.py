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
        "protocol_runs_root": None,
        "protocol_campaign_run_id": [],
        "protocol_baseline_run_id": None,
        "protocol_parity_session_id": [],
        "protocol_parity_discover_limit": 200,
        "protocol_max_parity_mismatches": 0,
        "protocol_sqlite_db": None,
        "protocol_strict": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _DummyExtensionManager:
    def __init__(self, *args, **kwargs):
        return None


def _bypass_startup_for_protocol_path_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: test-truthfulness cleanup. Protocol tests bypass startup; startup truth is covered elsewhere."""
    monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: None)


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


def _write_campaign_run(workspace: Path, run_id: str, *, session_id: str, status: str, ok: bool) -> None:
    events = workspace / "runs" / run_id / "events.log"
    ledger = AppendOnlyRunLedger(events)
    ledger.append_event(
        {
            "kind": "run_started",
            "session_id": session_id,
            "run_type": "epic",
            "run_name": "CLI Campaign",
            "department": "core",
            "build_id": "build-1",
            "status": "running",
        }
    )
    ledger.append_event(
        {
            "kind": "operation_result",
            "session_id": session_id,
            "operation_id": "op-1",
            "tool": "write_file",
            "result": {"ok": ok},
        }
    )
    ledger.append_event(
        {
            "kind": "run_finalized",
            "session_id": session_id,
            "status": status,
            "failure_class": None if status == "incomplete" else "ExecutionFailed",
            "failure_reason": None if status == "incomplete" else "failed",
        }
    )


@pytest.mark.asyncio
async def test_cli_protocol_replay_prints_summary(monkeypatch, tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies protocol replay output while intentionally bypassing startup semantics."""
    workspace = tmp_path / "workspace" / "default"
    _write_run(workspace, "run-a", status="incomplete", ok=True)

    _bypass_startup_for_protocol_path_test(monkeypatch)
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
    """Layer: integration. Verifies protocol compare strict mismatch reporting on the protocol path only."""
    workspace = tmp_path / "workspace" / "default"
    _write_run(workspace, "run-a", status="incomplete", ok=True)
    _write_run(workspace, "run-b", status="failed", ok=False)

    _bypass_startup_for_protocol_path_test(monkeypatch)
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
    """Layer: integration. Verifies protocol parity output while startup is intentionally bypassed."""
    workspace = tmp_path / "workspace" / "default"
    sqlite_db = workspace / ".orket" / "durable" / "db" / "orket_persistence.db"
    _write_run(workspace, "run-a", status="incomplete", ok=True)
    await _write_sqlite_run(sqlite_db, "run-a", status="incomplete")

    _bypass_startup_for_protocol_path_test(monkeypatch)
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
    """Layer: integration. Verifies parity strict-mode mismatch reporting on the protocol path only."""
    workspace = tmp_path / "workspace" / "default"
    sqlite_db = workspace / ".orket" / "durable" / "db" / "orket_persistence.db"
    _write_run(workspace, "run-a", status="failed", ok=False)
    await _write_sqlite_run(sqlite_db, "run-a", status="incomplete")

    _bypass_startup_for_protocol_path_test(monkeypatch)
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
    """Layer: integration. Verifies parity command surfaces missing-SQLite errors on the protocol path only."""
    workspace = tmp_path / "workspace" / "default"
    _write_run(workspace, "run-a", status="incomplete", ok=True)

    missing_db = workspace / "missing.db"
    _bypass_startup_for_protocol_path_test(monkeypatch)
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


@pytest.mark.asyncio
async def test_cli_protocol_campaign_prints_match_summary(monkeypatch, tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies replay campaign output while startup is intentionally bypassed."""
    workspace = tmp_path / "workspace" / "default"
    _write_campaign_run(workspace, "run-a", session_id="sess-campaign", status="incomplete", ok=True)
    _write_campaign_run(workspace, "run-b", session_id="sess-campaign", status="incomplete", ok=True)

    _bypass_startup_for_protocol_path_test(monkeypatch)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="campaign",
            workspace=str(workspace),
            protocol_baseline_run_id="run-a",
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"all_match": true' in out.lower()
    assert '"candidate_count": 2' in out.lower()


@pytest.mark.asyncio
async def test_cli_protocol_campaign_strict_reports_mismatch(monkeypatch, tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies replay campaign strict mismatch reporting on the protocol path only."""
    workspace = tmp_path / "workspace" / "default"
    _write_campaign_run(workspace, "run-a", session_id="sess-campaign", status="incomplete", ok=True)
    _write_campaign_run(workspace, "run-b", session_id="sess-campaign", status="failed", ok=False)

    _bypass_startup_for_protocol_path_test(monkeypatch)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="campaign",
            workspace=str(workspace),
            protocol_baseline_run_id="run-a",
            protocol_strict=True,
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"all_match": false' in out.lower()
    assert "Protocol replay campaign mismatch detected under --protocol-strict." in out


@pytest.mark.asyncio
async def test_cli_protocol_campaign_supports_explicit_run_id_filter(monkeypatch, tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies campaign filtering semantics without treating the test as startup proof."""
    workspace = tmp_path / "workspace" / "default"
    _write_campaign_run(workspace, "run-a", session_id="sess-campaign", status="incomplete", ok=True)
    _write_campaign_run(workspace, "run-b", session_id="sess-campaign", status="incomplete", ok=True)
    _write_campaign_run(workspace, "run-c", session_id="sess-campaign", status="failed", ok=False)

    _bypass_startup_for_protocol_path_test(monkeypatch)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="campaign",
            workspace=str(workspace),
            protocol_baseline_run_id="run-a",
            protocol_campaign_run_id=["run-a", "run-b"],
            protocol_strict=True,
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"all_match": true' in out.lower()
    assert '"candidate_count": 2' in out.lower()


@pytest.mark.asyncio
async def test_cli_protocol_campaign_uses_explicit_runs_root(monkeypatch, tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies explicit runs-root support on the protocol path only."""
    workspace = tmp_path / "workspace" / "default"
    custom_root = tmp_path / "custom-root"
    _write_campaign_run(custom_root, "run-a", session_id="sess-campaign", status="incomplete", ok=True)
    _write_campaign_run(custom_root, "run-b", session_id="sess-campaign", status="incomplete", ok=True)

    _bypass_startup_for_protocol_path_test(monkeypatch)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="campaign",
            workspace=str(workspace),
            protocol_runs_root=str(custom_root / "runs"),
            protocol_baseline_run_id="run-a",
            protocol_strict=True,
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"all_match": true' in out.lower()
