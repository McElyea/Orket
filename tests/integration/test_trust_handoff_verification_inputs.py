"""Integration: queued package identity and native/CLI verifier boundaries stay explicit."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.application.services.trust_handoff_verifier import verify_trust_handoff_package
from tests.helpers.log_process_receipts import process_readback
from tests.helpers.runtime_verification_hold import wait_entered
from tests.helpers.trust_handoff_ownership import (
    RUN_ID,
    PackageProbe,
    assert_pending_authority,
    emit_package,
    prepare_handoff,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("rejected", [False, True])
async def test_queued_relative_package_keeps_admission_root_and_declared_path(tmp_path, monkeypatch, rejected):
    package, _submitted, execution, events = await prepare_handoff(tmp_path, rejected=rejected, package_ref="package")
    alternate = tmp_path / "later/package"
    await asyncio.to_thread(emit_package, alternate, rejected=not rejected)
    monkeypatch.chdir(package.parent)
    probe = PackageProbe(monkeypatch, package, "resolve")
    task = asyncio.create_task(execution.start_if_ready(RUN_ID))
    try:
        await wait_entered(probe)
        monkeypatch.chdir(alternate.parent)
        probe.release.set()
        result = await task
        report, = probe.reports
        assert report["result"] == ("rejected" if rejected else "accepted")
        probe.assert_closed()
        assert result.status == ("completed" if rejected else "queued")
        rows = await events.list_for_run(RUN_ID)
        assert [event.event_type for event in rows] == (["run_submitted", "trust_handoff_rejected", "run_completed"]
                                                       if rejected else ["run_submitted", "trust_handoff_verified"])
        assert rows[1].payload["package_path"] == "package"
    finally:
        await probe.cleanup(task)


@pytest.mark.skipif(os.name != "nt", reason="Windows drive-relative path semantics")
async def test_drive_relative_handoff_refuses_without_verification_authority(tmp_path):
    _package, _submitted, execution, events = await prepare_handoff(tmp_path, package_ref=tmp_path.drive + "package")
    with pytest.raises(ValueError, match="E_PROCESS_DRIVE_RELATIVE_PATH_UNSUPPORTED"):
        await execution.start_if_ready(RUN_ID)
    await assert_pending_authority(execution, events)


async def test_sync_verifier_refuses_loop_before_package_io(tmp_path, monkeypatch):
    package, _submitted, _execution, _events = await prepare_handoff(tmp_path)
    calls = []
    original = Path.resolve

    def observe(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", observe)
    with pytest.raises(RuntimeError, match="E_TRUST_HANDOFF_VERIFICATION_REQUIRES_NATIVE_CONTEXT"):
        verify_trust_handoff_package(package)
    assert calls == []


async def _native_cli(script, arguments, record_property):
    result = await execute_owned_command(argv=[sys.executable, str(ROOT / "scripts/proof" / script), *arguments], cwd=ROOT,
        environment=dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONDONTWRITEBYTECODE="1"),
        timeout_seconds=20, input_data=None, stop=asyncio.Event(), output_limit_bytes=256 * 1024)
    assert result.reason == "completed" and result.cleanup_confirmed and result.capture_complete
    identities = {pid: None for pid in (result.command_pid, result.supervisor_pid, result.transport_pid) if pid is not None}
    observed = await asyncio.to_thread(process_readback, identities)
    assert observed and all(row["status"] in {"absent", "reused"} for row in observed.values())
    record_property("trust_cli_lifetime", json.dumps({"lifetime": result.lifetime(), "returncode": result.returncode,
                                                     "processes": observed}))
    return result


@pytest.mark.parametrize("rejected", [False, True])
async def test_real_offline_verifier_cli_keeps_report_and_exit(tmp_path, record_property, rejected):
    package, _submitted, _execution, _events = await prepare_handoff(tmp_path, rejected=rejected)
    expected = await asyncio.to_thread(verify_trust_handoff_package, package)
    output = tmp_path / "offline-report.json"
    result = await _native_cli("verify_trust_handoff_envelope.py",
        ["--package", str(package), "--out", str(output), "--json"], record_property)
    assert result.returncode == int(rejected), (result.stdout, result.stderr)
    persisted = json.loads(await asyncio.to_thread(output.read_text, encoding="utf-8"))
    assert persisted == json.loads(result.stdout)
    assert {key: value for key, value in persisted.items() if key != "diff_ledger"} == expected
    entry, = persisted["diff_ledger"]
    assert entry["diff"]["initial_write"] is True


async def test_real_corruption_cli_retains_all_existing_rejection_controls(tmp_path, record_property):
    package, _submitted, _execution, _events = await prepare_handoff(tmp_path)
    output = tmp_path / "corruption-report.json"
    result = await _native_cli("run_trust_handoff_corruption_suite.py",
        ["--base", str(package), "--out", str(output), "--json"], record_property)
    assert result.returncode == 0, (result.stdout, result.stderr)
    persisted = json.loads(await asyncio.to_thread(output.read_text, encoding="utf-8"))
    assert persisted == json.loads(result.stdout)
    assert persisted["base_result"] == persisted["result"] == "accepted"
    assert persisted["implemented_count"] == 23 and persisted["report_conformance_count"] == 1
    assert persisted["failed_count"] == persisted["accepted_corruption_count"] == 0
    assert len(persisted["rows"]) == 24 and all(row["status"] == "pass" for row in persisted["rows"])
    assert not await asyncio.to_thread((package.parent / ".trust_handoff_corruption_tmp").exists)
