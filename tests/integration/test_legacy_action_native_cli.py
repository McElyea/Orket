"""Public native CLI owns actual legacy engines before returning failure or interruption."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import orket
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from tests.integration.test_driver_native_cli_lifetime import collect_output, wait_marker
from tests.runtime.test_extension_manager import _init_test_extension_repo

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]


def source_repository(root):
    source = root / "extension-source"
    source.mkdir()
    _init_test_extension_repo(source)
    manifest = json.loads((source / "orket_extension.json").read_text(encoding="utf-8"))
    module = source / (manifest["module"] + ".py")
    value = module.read_text(encoding="utf-8")
    assert value.count("actions=(),") == 1
    module.write_text(value.replace("actions=(),",
        "actions=() if input_config.get('seed') == 0 else (RunAction('run_card', 'missing-card'),),"), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=source, capture_output=True, check=True, timeout=10)
    subprocess.run(["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "action fixture"],
                   cwd=source, capture_output=True, check=True, timeout=10)
    return source


async def install(source, root, env):
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "orket.cli", "runtime", "extensions", "install", str(source), cwd=root, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    output = asyncio.create_task(collect_output(process))
    try:
        stdout, stderr = await asyncio.wait_for(asyncio.shield(output), 30)
        assert process.returncode == 0 and b"Installed extension:" in stdout, (stdout, stderr)
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(output, 5)


@pytest.mark.parametrize("case", ["empty", "missing", "signal-construction", "close-failure"])
async def test_native_legacy_action_cli_closes_engine_before_exit(tmp_path, case):
    source = await asyncio.to_thread(source_repository, tmp_path)
    harness = (await asyncio.to_thread(Path(__file__).resolve)).parents[2]
    env = dict(os.environ, PYTHONPATH=str(harness), ORKET_DISABLE_SANDBOX="1", ORKET_RELIABLE_MODE="false",
               ORKET_DURABLE_ROOT=str(tmp_path / ".orket/durable"), ORKET_EXTENSIONS_CATALOG=str(tmp_path / "catalog.json"))
    env.pop("PYTEST_CURRENT_TEST", None)
    await install(source, tmp_path, env)
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tests.helpers.legacy_action_cli_worker", str(tmp_path), case, cwd=tmp_path, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    output = asyncio.create_task(collect_output(process))
    try:
        if case == "signal-construction":
            await wait_marker(tmp_path / "engine-entered", process, output)
            await asyncio.to_thread((tmp_path / "interrupt-now").touch)
            await wait_marker(tmp_path / "interrupt-issued", process, output)
            await asyncio.sleep(.08)
            assert process.returncode is None and not await asyncio.to_thread((tmp_path / "cli-returned").exists)
            await asyncio.to_thread((tmp_path / "engine-release").touch)
        stdout, stderr = await asyncio.wait_for(asyncio.shield(output), 30)
        await asyncio.to_thread((tmp_path / "cli-stdout.log").write_bytes, stdout)
        await asyncio.to_thread((tmp_path / "cli-stderr.log").write_bytes, stderr)
        expected = 0 if case == "empty" else 130 if case == "signal-construction" else 1
        assert process.returncode == expected, (stdout, stderr)
        receipt = json.loads(await asyncio.to_thread((tmp_path / "cli-observation.json").read_text, encoding="utf-8"))
        assert receipt["engines_closed"] == receipt["pipelines_closed"] == ([] if case == "empty" else [True])
        assert receipt["returncode"] == expected and len(receipt["run_ids"]) == 1
        assert (b"Executed workload:" in stdout) is (case == "empty")
        assert await asyncio.to_thread(Path(receipt["runtime_origin"]).resolve) == await asyncio.to_thread(Path(orket.__file__).resolve)
        await verify_retained_outcome(tmp_path, receipt["run_ids"][0], case)
    finally:
        await asyncio.to_thread((tmp_path / "engine-release").touch)
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(output, 5)


async def verify_retained_outcome(root, run_id, case):
    database = root / ".orket/durable/db/control_plane_records.sqlite3"
    executions, records = AsyncControlPlaneExecutionRepository(database), AsyncControlPlaneRecordRepository(database)
    run = await executions.get_run_record(run_id=run_id)
    final = await records.get_final_truth(run_id=run_id)
    if case == "signal-construction":
        assert run.lifecycle_state.value == "executing" and final is None
    else:
        assert run.lifecycle_state.value == ("completed" if case == "empty" else "failed_terminal")
        assert final is not None and final.result_class.value == ("success" if case == "empty" else "failed")
