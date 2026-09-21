"""Canonical native CLI with real stdin/HTTP clients and explicit fault controls."""
import asyncio
import builtins
import signal
import sys
from pathlib import Path

import pytest

import orket
import orket.interfaces.cli as cli_module
from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.cli import main as cli_main
from orket.driver import OrketDriver
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


async def interrupt(root, caller, case):
    for _ in range(600):
        if await asyncio.to_thread((root / "interrupt-now").exists):
            if case == "signal-eof":
                signal.raise_signal(signal.SIGINT)
            else:
                caller.cancel()
                await asyncio.sleep(0)
                caller.cancel()
            await asyncio.to_thread((root / "interrupt-issued").touch)
            return
        await asyncio.sleep(.025)
    raise RuntimeError("Parent never requested driver interruption")


def configure(patch, root, case):
    drivers, engines = [], []
    original_init, original_close = OrketDriver.__init__, LocalModelProvider.close
    original_input, original_run, original_engine = builtins.input, cli_module.run_cli, cli_module.OrchestrationEngine

    def construct(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        drivers.append(self)

    def engine(*args, **kwargs):
        owner = original_engine(*args, **kwargs)
        engines.append(owner)
        return owner

    def read(prompt):
        (root / "input-entered").touch()
        return original_input(prompt)

    async def close(self):
        await original_close(self)
        if case == "close-failure":
            raise OSError("Injected native CLI transport-close failure")

    async def run(*args, **kwargs):
        watcher = (asyncio.create_task(interrupt(root, asyncio.current_task(), case))
                   if case.startswith(("cancel-", "signal-")) else None)
        try:
            return await original_run(*args, **kwargs)
        finally:
            if watcher is not None:
                if not watcher.done():
                    watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            await asyncio.to_thread((root / "cli-returned").touch)

    patch.setattr(OrketDriver, "__init__", construct)
    patch.setattr(LocalModelProvider, "close", close)
    patch.setattr(builtins, "input", read)
    patch.setattr(cli_module, "run_cli", run)
    patch.setattr(cli_module, "OrchestrationEngine", engine)
    return drivers, engines


def main():
    root, case = Path(sys.argv[1]), sys.argv[2]
    assert root.is_absolute() and case in {"quit", "eof", "cancel-eof", "cancel-line", "signal-eof", "close-failure"}
    with pytest.MonkeyPatch.context() as patch:
        drivers, engines = configure(patch, root, case)
        code = cli_main(["runtime", "--workspace", str(root / "workspace")])
    write_payload_with_diff_ledger(root / "cli-observation.json", {
        "path": "primary", "proof": "native canonical CLI with actual pipe/HTTP-client effects and controlled responses",
        "case": case, "returncode": code, "runtime_origin": orket.__file__,
        "providers_closed": [owner.provider.client.is_closed for owner in drivers],
        "engines_closed": [owner._closed for owner in engines],
    })
    return code


if __name__ == "__main__":
    raise SystemExit(main())
