"""Native CLI observations checked against SQLite and independent process state.

Model/custom-policy and missing-build-member fixtures are explicit. The actual
CLI, admission, control-plane, publication and cleanup owners execute unchanged.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

import orket
from tests.integration.test_verification_process_lifetime import (
    assert_stopped,
    await_fixture_bootstrap,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def read_authority(root):
    """Called through to_thread; inspect only the declared fixture databases."""
    with sqlite3.connect((root / "cards.db").as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        ledger = [dict(row) for row in connection.execute("SELECT * FROM run_ledger")]
    observed = {"ledger": ledger}
    for filename, tables in {
        "control_plane_records.sqlite3": {"runs": "control_plane_runs", "truths": "final_truth_records"},
        "cards.db.epic-publications.sqlite3": {"publications": "epic_publications", "admissions": "epic_run_admissions"},
    }.items():
        with sqlite3.connect((root / filename).as_uri() + "?mode=ro", uri=True) as connection:
            for name, table in tables.items():
                column = "payload_json" if name in {"runs", "truths"} else "payload"
                observed[name] = [json.loads(row[0]) for row in connection.execute(f"SELECT {column} FROM {table}")]
    return observed


def assert_cli_truth(case, stdout, authority):
    ledger, = authority["ledger"]
    parent, = [run for run in authority["runs"] if run["run_id"].startswith("cards-epic-run:")]
    assert not [truth for truth in authority["truths"] if truth["run_id"] == parent["run_id"]]
    assert parent["final_truth_record_id"] is None
    assert ledger["session_id"] in stdout
    assert "not successful" in stdout and "result: blocked" in stdout
    assert "Evidence:" in stdout
    if case == "incomplete":
        assert ledger["status"] == "incomplete" and parent["lifecycle_state"] == "waiting_on_observation"
        assert "Observation: published" in stdout
        publication, = authority["publications"]
        assert publication["phase"] == 4
        assert authority["admissions"][0]["phase"] == "released"
    else:
        assert ledger["status"] == "running" and parent["lifecycle_state"] == "executing"
        assert not authority["publications"] and authority["admissions"][0]["phase"] == "active"
        assert ("Observation: approval_pending" if case == "pending" else "Observation: cancelled") in stdout


@pytest.mark.parametrize("alias", ["card", "epic", "rock"])
@pytest.mark.parametrize("case", ["pending", "incomplete", "signal", "repeated-cancel"])
# Layer: integration
async def test_native_cli_preserves_unfinished_truth_and_exit(tmp_path, alias, case):
    harness = (await asyncio.to_thread(Path(__file__).resolve)).parents[2]
    env = dict(os.environ, PYTHONPATH=str(harness), ORKET_DISABLE_SANDBOX="1",
               ORKET_DISABLE_RUNTIME_VERIFIER="true", ORKET_DURABLE_ROOT=str(tmp_path / ".orket/durable"))
    # The child owns an isolated durable root and must exercise normal CLI
    # settings bootstrap, not settings.py's in-process pytest cache behavior.
    env.pop("PYTEST_CURRENT_TEST", None)
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tests.helpers.runtime_cli_lifecycle_worker", str(tmp_path), case, alias,
        cwd=tmp_path, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    output = asyncio.create_task(process.communicate())
    processes = []
    try:
        if case in {"signal", "repeated-cancel"}:
            await await_fixture_bootstrap(tmp_path, process, output)
            processes = await await_tree(tmp_path / "children")
            await asyncio.to_thread((tmp_path / "interrupt-now").touch)
        stdout, stderr = await asyncio.wait_for(asyncio.shield(output), 30)
        await asyncio.to_thread((tmp_path / "cli-stdout.log").write_bytes, stdout)
        await asyncio.to_thread((tmp_path / "cli-stderr.log").write_bytes, stderr)
        assert process.returncode == (130 if processes else 1), (stdout, stderr)
        assert await asyncio.to_thread((tmp_path / "cards.db").exists), (stdout, stderr)
        observed = json.loads(await asyncio.to_thread((tmp_path / "cli-observation.json").read_text, encoding="utf-8"))
        observed_origin = await asyncio.to_thread(Path(observed["runtime_origin"]).resolve)
        assert observed_origin == await asyncio.to_thread(Path(orket.__file__).resolve)
        authority = await asyncio.to_thread(read_authority, tmp_path)
        assert_cli_truth(case, stdout.decode("utf-8"), authority)
        assert not await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").exists)
        if processes:
            await assert_stopped(processes, tmp_path / "children")
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, tmp_path / "children")
        await asyncio.to_thread(stop_observed, processes)
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(output, 5)
