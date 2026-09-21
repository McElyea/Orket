"""Native CLI exit, HTTP effects and provider teardown under real pipe EOF/signals."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

import orket
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.helpers.odr_provider_server import AUDITOR, provider_server
from tests.integration.test_model_selection_consumers import _environment

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def wait_marker(path, process, output):
    async with asyncio.timeout(15):
        while not await asyncio.to_thread(path.exists):
            if process.returncode is not None:
                pytest.fail(f"CLI exited before {path.name}: {await output}")
            await asyncio.sleep(.025)


async def collect_output(process):
    stdout, stderr = await asyncio.gather(process.stdout.read(), process.stderr.read())
    await process.wait()
    return stdout, stderr


@pytest.mark.parametrize("case", ["quit", "eof", "cancel-eof", "cancel-line", "signal-eof", "close-failure"])
async def test_native_driver_cli_owns_input_and_transport_until_exit(tmp_path, case):
    await asyncio.to_thread(_write_epic_assets, tmp_path, "publication_epic")
    harness = (await asyncio.to_thread(Path(__file__).resolve)).parents[2]
    with provider_server() as (endpoint, calls):
        env = dict(_environment(endpoint), PYTHONPATH=str(harness), ORKET_DISABLE_SANDBOX="1",
                   ORKET_DURABLE_ROOT=str(tmp_path / ".orket/durable"))
        env.pop("PYTEST_CURRENT_TEST", None)
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "tests.helpers.driver_cli_lifetime_worker", str(tmp_path), case,
            cwd=tmp_path, env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        output = asyncio.create_task(collect_output(process))
        try:
            await wait_marker(tmp_path / "input-entered", process, output)
            interrupted = case.startswith(("cancel-", "signal-"))
            if interrupted:
                await asyncio.to_thread((tmp_path / "interrupt-now").touch)
                await wait_marker(tmp_path / "interrupt-issued", process, output)
                await asyncio.sleep(.08)
                assert process.returncode is None and not await asyncio.to_thread((tmp_path / "cli-returned").exists)
            if case == "quit":
                process.stdin.write(b"Explain the system to a curious developer.\nquit\n")
            elif case in {"cancel-line", "close-failure"}:
                process.stdin.write(b"quit\n")
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()
            stdout, stderr = await asyncio.wait_for(asyncio.shield(output), 30)
            await asyncio.to_thread((tmp_path / "cli-stdout.log").write_bytes, stdout)
            await asyncio.to_thread((tmp_path / "cli-stderr.log").write_bytes, stderr)
            expected = 130 if interrupted else 1 if case == "close-failure" else 0
            assert process.returncode == expected, (stdout, stderr)
            receipt = json.loads(await asyncio.to_thread((tmp_path / "cli-observation.json").read_text, encoding="utf-8"))
            assert receipt["providers_closed"] == receipt["engines_closed"] == [True]
            assert receipt["returncode"] == expected
            assert await asyncio.to_thread(Path(receipt["runtime_origin"]).resolve) == await asyncio.to_thread(Path(orket.__file__).resolve)
            posts = [call for call in calls if call[0] == "POST"]
            assert len(posts) == (1 if case == "quit" else 0)
            if case == "quit":
                assert AUDITOR.strip() in stdout.decode("utf-8").replace("\r\n", "\n")
        finally:
            process.stdin.close()
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(output, 5)
