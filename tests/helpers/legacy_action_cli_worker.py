"""Native canonical CLI with transparent engine observation and explicit fault controls."""
import asyncio
import sys
import time
from pathlib import Path

import pytest

import orket
import orket.extensions.runtime as runtime_module
import orket.interfaces.cli as cli_module
from orket.application.services.extension_workload_control_plane_service import ExtensionWorkloadControlPlaneService
from orket.cli import main as cli_main
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.driver_cli_lifetime_worker import interrupt


def hold_construction(root):
    (root / "engine-entered").touch()
    deadline = time.monotonic() + 10
    while not (root / "engine-release").exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("Parent did not release the admitted legacy engine")
        time.sleep(.01)


def configure(patch, root, case):
    owners, run_ids = [], []
    original_engine, original_run = runtime_module.OrchestrationEngine, cli_module.run_cli
    original_begin = ExtensionWorkloadControlPlaneService.begin_execution

    def construct(*args, **kwargs):
        owner = original_engine(*args, **kwargs)
        owners.append(owner)
        original_close = owner.close

        async def close():
            await original_close()
            if case == "close-failure":
                await asyncio.to_thread((root / "absent-close-input").read_bytes)

        patch.setattr(owner, "close", close)
        if case == "signal-construction":
            hold_construction(root)
        return owner

    async def begin(self, **kwargs):
        result = await original_begin(self, **kwargs)
        run_ids.append(result.run.run_id)
        return result

    async def run(*args, **kwargs):
        watcher = (asyncio.create_task(interrupt(root, asyncio.current_task(), "signal-eof"))
                   if case == "signal-construction" else None)
        try:
            return await original_run(*args, **kwargs)
        finally:
            if watcher is not None:
                if not watcher.done():
                    watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            await asyncio.to_thread((root / "cli-returned").touch)

    patch.setattr(runtime_module, "OrchestrationEngine", construct)
    patch.setattr(ExtensionWorkloadControlPlaneService, "begin_execution", begin)
    patch.setattr(cli_module, "run_cli", run)
    return owners, run_ids


def main():
    root, case = Path(sys.argv[1]), sys.argv[2]
    assert root.is_absolute() and case in {"empty", "missing", "signal-construction", "close-failure"}
    with pytest.MonkeyPatch.context() as patch:
        owners, run_ids = configure(patch, root, case)
        code = cli_main(["runtime", "run", "mystery_v1", "--seed", "0" if case == "empty" else "1",
                         "--workspace", str(root / "workspace")])
    write_payload_with_diff_ledger(root / "cli-observation.json", {
        "path": "primary", "proof": "canonical native CLI, installed legacy Git source, real runtime refusal and cleanup",
        "case": case, "returncode": code, "runtime_origin": orket.__file__, "run_ids": run_ids,
        "engines_closed": [owner._closed for owner in owners],
        "pipelines_closed": [owner._pipeline._closed for owner in owners],
        "scope": "No inference or successful action completion claim; empty plan is a separate zero-action control.",
    })
    return code


if __name__ == "__main__":
    raise SystemExit(main())
