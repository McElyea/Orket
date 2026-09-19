"""Layer: end-to-end. Installed CLI, actual startup, ledger files and SQLite."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from tests.helpers.core_effect_fixtures import BOARD_ASSETS
from tests.interfaces.test_sessions_router_protocol_replay import _seed_sqlite_run, _write_protocol_run

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]


async def _command(project, label, *args):
    executable = Path(sys.executable).parent / ("orket.exe" if os.name == "nt" else "orket")
    assert executable.is_file()
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", ORKET_DURABLE_ROOT=str(project / ".orket/durable"))
    environment.pop("PYTHONPATH", None)
    process = await asyncio.create_subprocess_exec(str(executable), "runtime", "protocol", *args,
        cwd=project, env=environment, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    (project / f"{label}.stdout.log").write_bytes(stdout)
    (project / f"{label}.stderr.log").write_bytes(stderr)
    text = stdout.decode("utf-8")
    # Startup may print status before the machine-readable protocol payload.
    payload = None
    for index, char in enumerate(text):
        if char == "{":
            try:
                payload, _ = json.JSONDecoder().raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            break
    return process.returncode, payload, text, stderr.decode("utf-8")


async def test_installed_protocol_commands_and_strict_evidence_gate(tmp_path):
    project, workspace, outside = tmp_path / "project", tmp_path / "workspace", tmp_path / "operator-inputs"
    project.mkdir()
    for asset in BOARD_ASSETS:
        path = project / "model" / asset.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(asset.content, encoding="utf-8")
    for run_id in ("run-a", "run-b"):
        _write_protocol_run(workspace, run_id, status="incomplete", ok=True)
    _write_protocol_run(outside, "external", status="incomplete", ok=True)
    database = workspace / ".orket/durable/db/orket_persistence.db"
    await _seed_sqlite_run(sqlite_db=database, session_id="run-a", status="incomplete")
    common = ("--workspace", str(workspace), "--protocol-strict")
    operations = [
        ("replay", ("replay", "run-a"), "session_id", "run-a"),
        ("compare", ("compare", "run-a", "--protocol-run-b", "run-b"), "deterministic_match", True),
        ("campaign", ("campaign",), "all_match", True),
        ("parity", ("parity", "run-a"), "parity_ok", True),
        ("parity-campaign", ("parity-campaign", "--protocol-parity-session-id", "run-a"), "all_match", True),
        ("external", ("replay", "external", "--protocol-events-a", "../operator-inputs/runs/external/events.log"),
         "session_id", "external"),
    ]
    before = {path: path.read_bytes() for path in workspace.glob("runs/*/events.log")}
    for label, args, field, expected in operations:
        code, payload, stdout, stderr = await _command(project, label, *args, *common)
        assert code == 0, (label, stdout, stderr)
        assert payload[field] == expected, payload
    empty = workspace / "runs/empty/events.log"
    empty.parent.mkdir()
    empty.touch()
    code, payload, stdout, stderr = await _command(project, "empty", "campaign",
        "--protocol-campaign-run-id", "empty", *common)
    assert code == 1 and payload["all_match"] is False, (stdout, stderr)
    assert payload["comparisons"][0]["comparison_status"] == "insufficient_evidence"
    code, payload, stdout, stderr = await _command(project, "escape", "parity-campaign",
        "--protocol-parity-session-id", "../../outside", *common)
    assert code == 1 and payload is None and "Invalid run_id" in stdout + stderr
    assert all(path.read_bytes() == content for path, content in before.items())
