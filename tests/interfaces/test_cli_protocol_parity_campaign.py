from __future__ import annotations

from pathlib import Path

import pytest

import orket.interfaces.cli as cli_module
from tests.interfaces.test_cli_protocol_replay import (
    _DummyExtensionManager,
    _args,
    _bypass_startup_for_protocol_path_test,
    _write_run,
    _write_sqlite_run,
)


@pytest.mark.asyncio
async def test_cli_protocol_parity_campaign_prints_summary(monkeypatch, tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies parity-campaign output while startup is intentionally bypassed."""
    workspace = tmp_path / "workspace" / "default"
    sqlite_db = workspace / ".orket" / "durable" / "db" / "orket_persistence.db"
    _write_run(workspace, "run-a", status="incomplete", ok=True)
    _write_run(workspace, "run-b", status="incomplete", ok=True)
    await _write_sqlite_run(sqlite_db, "run-a", status="incomplete")
    await _write_sqlite_run(sqlite_db, "run-b", status="incomplete")

    _bypass_startup_for_protocol_path_test(monkeypatch)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _args(
            command="protocol",
            subcommand="parity-campaign",
            workspace=str(workspace),
            protocol_sqlite_db=str(sqlite_db),
            protocol_parity_session_id=["run-a", "run-b"],
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"all_match": true' in out.lower()
    assert '"candidate_count": 2' in out.lower()


@pytest.mark.asyncio
async def test_cli_protocol_parity_campaign_strict_reports_mismatch(monkeypatch, tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies parity-campaign strict mismatch reporting on the protocol path only."""
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
            subcommand="parity-campaign",
            workspace=str(workspace),
            protocol_sqlite_db=str(sqlite_db),
            protocol_parity_session_id=["run-a"],
            protocol_strict=True,
        ),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out
    assert '"all_match": false' in out.lower()
    assert "Run ledger parity campaign mismatch detected under --protocol-strict." in out
