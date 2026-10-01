"""Integration: actual CLI conflicts/lease refusal use their captured logging selection."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.observability.logging_context import selected_logging
from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.gitea_state_models import CardSnapshot, LeaseInfo, encode_snapshot
from orket.logging import settle_log_write_frontier
from scripts.gitea import reconcile_state_backends as reconciliation
from scripts.gitea import run_gitea_state_worker_coordinator as coordinator
from tests.application.test_run_gitea_state_worker_coordinator_script import _args
from tests.helpers.gitea_http_observation import observe_resources
from tests.helpers.log_process_receipts import process_readback
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_failure_diagnostic_refusals import _selected_pythonpath
from tests.integration.test_gitea_http_cli_ownership import prepare

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _response(kind, case):
    card_id = "2" if case == "missing_sqlite" else "1"
    lease = LeaseInfo(owner_id="another-worker", acquired_at="2026-01-01T00:00:00+00:00",
                      expires_at="2999-01-01T00:00:00+00:00", epoch=7)
    snapshot = CardSnapshot(card_id=card_id, state="blocked" if case == "mismatch" else "ready",
                            version=3, lease=lease if kind == "coordinator" else LeaseInfo())
    issue = {"number": int(card_id), "body": "missing snapshot" if case == "missing_gitea" else encode_snapshot(snapshot)}

    async def respond(request):
        method, target, _ = request[0].split()
        assert method == "GET", "the refused/conflicting flow must not mutate remote state"
        path = urlsplit(target).path
        assert path in {"/api/v1/repos/fixture-owner/fixture-repo/issues",
                        f"/api/v1/repos/fixture-owner/fixture-repo/issues/{card_id}"}
        return 200, [issue] if kind == "coordinator" and path.endswith("/issues") else issue

    return respond


def _stage_script(root, kind):
    module = coordinator if kind == "coordinator" else reconciliation
    source = Path(module.__file__)
    project = root / "copied-project"
    script = project / "scripts/gitea" / source.name
    script.parent.mkdir(parents=True)
    data = source.read_bytes()
    script.write_bytes(data)
    # Execute the exact current script bytes from an isolated project layout.
    # Its original PROJECT_ROOT derivation remains live and cannot write source logs.
    assert hashlib.sha256(script.read_bytes()).digest() == hashlib.sha256(data).digest()
    return script, hashlib.sha256(data).hexdigest()


async def _native_cli(root, kind, arguments, record_property):
    script, digest = await asyncio.to_thread(_stage_script, root, kind)
    temporary = root / "native-temp"
    await asyncio.to_thread(temporary.mkdir)
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONDONTWRITEBYTECODE="1",
        TMP=str(temporary), TEMP=str(temporary), PYTHONPATH=await asyncio.to_thread(_selected_pythonpath))
    argv = [sys.executable, str(script), *arguments]
    result = await execute_owned_command(argv=argv, cwd=root, environment=environment, timeout_seconds=25,
        input_data=None, stop=asyncio.Event(), output_limit_bytes=256 * 1024)
    record_property("cli_observation", json.dumps({"script_sha256": digest, "argv": argv,
        "lifetime": result.lifetime(), "stdout": result.stdout.decode(errors="replace"),
        "stderr": result.stderr.decode(errors="replace")}))
    assert result.reason == "completed" and result.cleanup_confirmed and result.capture_complete, result.lifetime()
    identities = {pid: None for pid in (result.command_pid, result.supervisor_pid, result.transport_pid) if pid is not None}
    observed = await asyncio.to_thread(process_readback, identities)
    record_property("cli_process_readback", json.dumps(observed))
    assert observed and all(row["status"] in {"absent", "reused"} for row in observed.values())
    assert await asyncio.to_thread(lambda: hashlib.sha256(script.read_bytes()).hexdigest()) == digest
    return result


async def _read_json(path):
    return json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))


async def _configure(root, monkeypatch, address, *, mode="legacy_default"):
    database = await prepare(root, monkeypatch, address)
    monkeypatch.setenv("ORKET_TIMEZONE", "MST")
    monkeypatch.setenv("ORKET_LOGGING_MISSING_CONTEXT_MODE", mode)
    monkeypatch.setenv("ORKET_LOG_QUEUE_MAX", "10000")
    return database


@pytest.mark.parametrize("case,require_clean", [
    ("mismatch", False), ("mismatch", True), ("missing_sqlite", True),
    ("missing_gitea", False), ("matching", True),
])
async def test_native_reconciliation_reports_real_backend_conflicts(tmp_path, monkeypatch, record_property, case, require_clean):
    async with observed_http_server(_response("reconciliation", case)) as server:
        database = await _configure(tmp_path, monkeypatch, server[0])
        output = tmp_path / "report.json"
        card_id = "2" if case == "missing_sqlite" else "1"
        arguments = ["--card-id", card_id, "--out", str(output)] + (["--require-clean"] if require_clean else [])
        result = await _native_cli(tmp_path, "reconciliation", arguments, record_property)
        conflict = case != "matching"
        assert b"E_LOGGING_PREPARATION_REQUIRED" not in result.stdout + result.stderr
        assert result.returncode == int(conflict and require_clean), (result.stdout, result.stderr)
        payload = await _read_json(output)
        assert json.loads(result.stdout) == payload and "diff_ledger" in payload
        assert payload["ok"] is (not conflict) and payload["authority_policy"] == "halt_and_alert"
        assert payload["checked_count"] == 1 and payload["conflict_count"] == int(conflict)
        assert payload["rows"][0]["card_id"] == card_id
        if conflict:
            expected = {"mismatch": "state_mismatch", "missing_sqlite": "missing_sqlite",
                        "missing_gitea": "missing_gitea"}[case]
            assert payload["conflicts"][0]["conflict_type"] == expected
        else:
            assert payload["conflicts"] == []
        cards = AsyncCardRepository(database)
        assert (await cards.get_by_id("1")).status.value == "ready" and await cards.get_by_id("2") is None
        assert len(server[1]) == 1 and server[1][0][0].startswith("GET ")


@pytest.mark.parametrize("mode", ["legacy_default", "fail_fast"])
async def test_native_coordinator_retains_live_lease_refusal_policy(tmp_path, monkeypatch, record_property, mode):
    async with observed_http_server(_response("coordinator", "live_lease")) as server:
        database = await _configure(tmp_path, monkeypatch, server[0], mode=mode)
        output = tmp_path / "summary.json"
        arguments = ["--worker-id", "observing-worker", "--allow-mutate", "--max-idle-streak", "1",
                     "--max-iterations", "1", "--summary-out", str(output)]
        result = await _native_cli(tmp_path, "coordinator", arguments, record_property)
        payload = json.loads(result.stdout)
        assert "E_LOGGING_PREPARATION_REQUIRED" not in str(payload), (payload, result.stderr)
        if mode == "fail_fast":
            assert result.returncode == 1 and payload["ready"] is False
            assert "E_LOG_WORKSPACE_REQUIRED" in payload["error"]
            assert not await asyncio.to_thread(output.exists)
        else:
            assert result.returncode == 0
            persisted = await _read_json(output)
            assert "diff_ledger" not in payload
            assert persisted.keys() == payload.keys() | {"diff_ledger"}
            assert {key: persisted[key] for key in payload} == payload
            entry, = persisted["diff_ledger"]
            assert entry["before_digest"] is None and entry["changed"] is True
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            assert entry["after_digest"] == "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            assert entry["diff"]["initial_write"] is True
            assert entry["diff"]["paths_total_previous"] == 0
            assert "major_diff_rollover" not in entry
            assert payload["worker_id"] == "observing-worker"
            summary = payload["summary"]
            assert summary["iterations"] == summary["idle_count"] == 1 and summary["consumed_count"] == 0
            assert summary["stop_reason"] == "max_idle_streak"
        assert (await AsyncCardRepository(database).get_by_id("1")).status.value == "ready"
        assert len(server[1]) == 2 and all(line.startswith("GET ") for line, _ in server[1])


@pytest.mark.parametrize("kind", ["reconciliation", "coordinator"])
async def test_direct_cli_operation_retains_captured_logging_and_restores_caller(tmp_path, monkeypatch, record_property, kind):
    entered, release = asyncio.Event(), asyncio.Event()
    respond = _response(kind, "mismatch" if kind == "reconciliation" else "live_lease")

    async def held(request):
        if not entered.is_set():
            entered.set()
            await asyncio.wait_for(release.wait(), 5)
        return await respond(request)

    contexts = []
    resources, closed = observe_resources(monkeypatch)
    project, later = tmp_path / "project", tmp_path / "later"
    await asyncio.to_thread(later.mkdir)
    monkeypatch.setattr(reconciliation, "PROJECT_ROOT", project)
    async with observed_http_server(held) as server:
        database = await _configure(tmp_path, monkeypatch, server[0])

        async def invoke():
            assert selected_logging(required=False) is None
            try:
                return await (reconciliation._run(["1"]) if kind == "reconciliation" else
                    coordinator._run_loop(_args(worker_id="observing-worker", max_idle_streak=1)))
            finally:
                contexts.append(selected_logging(required=False))

        task = asyncio.create_task(invoke())
        try:
            await asyncio.wait_for(entered.wait(), 5)
            monkeypatch.chdir(later)
            monkeypatch.setenv("ORKET_TIMEZONE", "UTC")
            monkeypatch.setenv("ORKET_LOGGING_MISSING_CONTEXT_MODE", "fail_fast")
            release.set()
            result = await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert contexts == [None] and selected_logging(required=False) is None
        assert len(resources) == 2 and all(item in closed for item in resources) and resources[-1].is_closed
        await run_owned_thread(settle_log_write_frontier, label="gitea-cli-test-optional-frontier")
        log_root = project if kind == "reconciliation" else tmp_path / "workspace/default"
        records = (await asyncio.to_thread((log_root / "orket.log").read_text, encoding="utf-8")).splitlines()
        event = "state_reconciliation_conflict" if kind == "reconciliation" else "lease_acquisition_failed"
        observed = [json.loads(line) for line in records if json.loads(line)["event"] == event]
        assert len(observed) == 1 and observed[0]["timestamp"].endswith("-07:00")
        assert not await asyncio.to_thread((later / "workspace").exists)
        assert (await AsyncCardRepository(database).get_by_id("1")).status.value == "ready"
        assert result["conflict_count"] == 1 if kind == "reconciliation" else result["summary"]["consumed_count"] == 0
        assert all(line.startswith("GET ") for line, _ in server[1])
        record_property("captured_logging", json.dumps({"kind": kind, "record": observed[0], "context_restored": True}))
