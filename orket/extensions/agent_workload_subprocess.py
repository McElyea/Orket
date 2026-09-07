from __future__ import annotations

import asyncio
import builtins
import importlib
import inspect
import json
import queue
import sys
import threading
from io import BufferedReader
from pathlib import Path
from typing import cast

from orket.extensions.sdk_workload_subprocess import (
    DeclaredStdlibImportHook,
    _guarded_import,
    _guarded_import_module,
)
from orket.extensions.workload_loader import WorkloadLoader
from orket_extension_sdk import AsyncAgentWorkload, run_agent_workload


class _DaemonStdinReader:
    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._reader = asyncio.StreamReader()
        self._finished = asyncio.Event()
        threading.Thread(target=self._pump, name="orket-agent-stdin", daemon=True).start()

    async def readexactly(self, count: int) -> bytes:
        return await self._reader.readexactly(count)

    async def wait_stopped(self) -> None:
        await asyncio.wait_for(self._finished.wait(), timeout=5)

    def _pump(self) -> None:
        try:
            stdin = cast(BufferedReader, sys.stdin.buffer)
            while chunk := stdin.read1(8192):
                self._loop.call_soon_threadsafe(self._reader.feed_data, chunk)
        except OSError as exc:
            self._loop.call_soon_threadsafe(_finish_input, self._reader, self._finished, exc)
        else:
            self._loop.call_soon_threadsafe(_finish_input, self._reader, self._finished, None)


class _DaemonStdoutWriter:
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._queue: queue.Queue[tuple[bytes, asyncio.AbstractEventLoop, asyncio.Future[None]]] = queue.Queue(1)
        threading.Thread(target=self._pump, name="orket-agent-stdout", daemon=True).start()

    def write(self, value: bytes) -> None:
        self._buffer.extend(value)

    async def drain(self) -> None:
        loop = asyncio.get_running_loop()
        completion: asyncio.Future[None] = loop.create_future()
        self._queue.put_nowait((bytes(self._buffer), loop, completion))
        self._buffer.clear()
        await completion

    def _pump(self) -> None:
        while True:
            value, loop, completion = self._queue.get()
            try:
                sys.stdout.buffer.write(value)
                sys.stdout.buffer.flush()
            except OSError as exc:
                loop.call_soon_threadsafe(_finish_write, completion, exc)
            else:
                loop.call_soon_threadsafe(_finish_write, completion, None)


def _finish_write(completion: asyncio.Future[None], error: OSError | None) -> None:
    if completion.done():
        return
    if error is None:
        completion.set_result(None)
    else:
        completion.set_exception(error)


def _finish_input(
    reader: asyncio.StreamReader,
    finished: asyncio.Event,
    error: OSError | None,
) -> None:
    if error is None:
        reader.feed_eof()
    else:
        reader.set_exception(error)
    finished.set()


def _load_workload(
    *,
    extension_root: Path,
    entrypoint: str,
    allowed_stdlib_modules: set[str],
) -> AsyncAgentWorkload:
    module_name, attr_name = WorkloadLoader.parse_sdk_entrypoint(entrypoint)
    WorkloadLoader.validate_extension_imports(
        extension_root,
        module_name,
        allowed_stdlib_modules=tuple(sorted(allowed_stdlib_modules)),
        enforce_declared_stdlib=True,
    )
    sys.path.insert(0, str(extension_root))
    import_hook = DeclaredStdlibImportHook(
        extension_root=extension_root,
        allowed_stdlib_modules=allowed_stdlib_modules,
    )
    sys.meta_path.insert(0, import_hook)
    builtins.__import__ = _guarded_import(import_hook, builtins.__import__)
    importlib.import_module = _guarded_import_module(import_hook, importlib.import_module)
    module = importlib.import_module(module_name)
    target = getattr(module, attr_name, None)
    if target is None:
        raise ValueError(f"E_SDK_ENTRYPOINT_MISSING: {entrypoint}")
    workload = target() if inspect.isclass(target) else target
    run_method = getattr(workload, "run", None)
    if run_method is None or not callable(run_method) or not inspect.iscoroutinefunction(run_method):
        raise ValueError(f"E_SDK_AGENT_ENTRYPOINT_ASYNC_REQUIRED: {entrypoint}")
    return cast(AsyncAgentWorkload, workload)


async def _run(argv: list[str]) -> int:
    if len(argv) != 3:
        raise ValueError("E_SDK_AGENT_CHILD_ARGUMENTS_INVALID")
    extension_root = await asyncio.to_thread(Path(argv[0]).resolve)
    entrypoint = argv[1]
    allowed_payload = json.loads(argv[2])
    if not isinstance(allowed_payload, list) or not all(isinstance(item, str) for item in allowed_payload):
        raise ValueError("E_SDK_AGENT_CHILD_STDLIB_INVALID")
    workload = await asyncio.to_thread(
        _load_workload,
        extension_root=extension_root,
        entrypoint=entrypoint,
        allowed_stdlib_modules=set(allowed_payload),
    )
    reader = _DaemonStdinReader()
    await run_agent_workload(
        workload,
        cast(asyncio.StreamReader, reader),
        cast(asyncio.StreamWriter, _DaemonStdoutWriter()),
        bootstrap_timeout_seconds=30,
    )
    await reader.wait_stopped()
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(_run(list(sys.argv[1:] if argv is None else argv)))
    except Exception as exc:  # CLI process boundary; stdout must remain protocol-only.
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
