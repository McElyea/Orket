from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from scripts.ci import memory_fixture_smoke, migration_smoke_validator, sandbox_leak_gate


def test_memory_fixture_smoke_writes_profile_fixtures(tmp_path: Path) -> None:
    """Layer: unit. Verifies CI memory fixture extraction writes the expected deterministic fixture set."""
    memory_fixture_smoke.write_fixtures(out_dir=tmp_path, profile="nightly")

    filenames = {path.name for path in tmp_path.iterdir()}
    assert filenames == {
        "memory_trace_fixture_left.json",
        "memory_retrieval_trace_fixture_left.json",
        "memory_trace_fixture_right.json",
        "memory_retrieval_trace_fixture_right.json",
    }
    trace = json.loads((tmp_path / "memory_trace_fixture_left.json").read_text(encoding="utf-8"))
    assert trace["run_id"] == "nightly-memory-fixture"
    assert trace["metadata"] == {"truncated": False}


def test_sandbox_leak_gate_evaluate_leaks_respects_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies sandbox leak extraction filters explicit allowlisted resources."""

    def fake_compose_projects() -> list[dict[str, object]]:
        return [
            {"Name": "orket-sandbox-live"},
            {"Name": "orket-sandbox-allowed"},
            {"Name": "unrelated"},
        ]

    def fake_lines(*cmd: str) -> list[str]:
        if cmd[:2] == ("docker", "ps"):
            return ["container-live", "container-allowed"]
        if cmd[:2] == ("docker", "network"):
            return ["network-live"]
        if cmd[:2] == ("docker", "volume"):
            return ["volume-live"]
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(sandbox_leak_gate, "_compose_projects", fake_compose_projects)
    monkeypatch.setattr(sandbox_leak_gate, "_lines", fake_lines)

    leaks = sandbox_leak_gate.evaluate_leaks({"orket-sandbox-allowed", "container-allowed"})

    assert leaks == {
        "compose_projects": ["orket-sandbox-live"],
        "containers": ["container-live"],
        "networks": ["network-live"],
        "volumes": ["volume-live"],
    }


def test_sandbox_leak_gate_fails_closed_when_docker_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies missing Docker/Compose cannot produce a false-green leak report."""

    def fake_run(*args, **_kwargs):
        cmd = args[0]
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="docker unavailable")

    monkeypatch.setattr(sandbox_leak_gate.subprocess, "run", fake_run)

    assert sandbox_leak_gate.main([]) == 1


def _write_migration_db(path: Path, count: int) -> None:
    connection = sqlite3.connect(path)
    try:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE _schema_migrations (id TEXT)")
        for index in range(count):
            cursor.execute("INSERT INTO _schema_migrations (id) VALUES (?)", (f"migration-{index}",))
        connection.commit()
    finally:
        connection.close()


def test_migration_smoke_validator_accepts_migration_rows(tmp_path: Path) -> None:
    """Layer: unit. Verifies migration smoke validation requires recorded migration rows in both DBs."""
    runtime_db = tmp_path / "runtime.db"
    webhook_db = tmp_path / "webhook.db"
    _write_migration_db(runtime_db, 1)
    _write_migration_db(webhook_db, 1)

    migration_smoke_validator._validate(runtime_db, webhook_db)


def test_migration_smoke_validator_rejects_empty_migration_table(tmp_path: Path) -> None:
    """Layer: unit. Verifies empty migration ledgers are not reported as successful smoke validation."""
    runtime_db = tmp_path / "runtime.db"
    webhook_db = tmp_path / "webhook.db"
    _write_migration_db(runtime_db, 1)
    _write_migration_db(webhook_db, 0)

    with pytest.raises(RuntimeError, match="No migrations recorded"):
        migration_smoke_validator._validate(runtime_db, webhook_db)
