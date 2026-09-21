"""Real native resources behind the runtime's supported injected cleanup ports."""
import asyncio
import sqlite3
from functools import partial

from orket.adapters.execution.owned_io import run_owned_thread
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.execution.execution_pipeline import ExecutionPipeline


class NativeCleanupPort:
    """A close transaction can fail before its native connection is released."""

    def __init__(self, path, *, failure=False, hold=None):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("CREATE TABLE cleanup_marker (value INTEGER)")
        self.connection.commit()
        self.failure, self.hold = failure, hold
        self.closed, self.attempts = False, 0
        self.errors = []

    def close(self):
        if self.closed:
            return
        self.attempts += 1
        if self.hold is not None:
            self.hold.entered.set()
            if not self.hold.release.wait(5):
                raise TimeoutError("Native cleanup release was not observed")
        if self.failure:
            try:
                self.connection.execute("INSERT INTO absent_cleanup_table VALUES (1)")
            except sqlite3.OperationalError as exc:
                self.errors.append(exc)
                raise
        self.connection.close()
        self.closed = True

    def observe_closed(self):
        try:
            self.connection.execute("SELECT 42")
        except sqlite3.ProgrammingError as exc:
            assert "closed" in str(exc).lower()
            return True
        return False


class AsyncCleanupPort(NativeCleanupPort):
    async def aclose(self):
        # The fixture owns real worker completion. Caller-side cleanup must retain it.
        await run_owned_thread(super().close, label="fixture-native-sqlite-close")


async def create_cleanup_runtime(root, kind, ports):
    runtime_type = OrchestrationEngine if kind == "engine" else ExecutionPipeline
    runtime = await run_owned_thread(partial(runtime_type, root / "workspace", config_root=root,
        db_path=str(root / "runtime.sqlite3"), run_ledger_repo=ports[0], success_repo=ports[1],
        snapshots_repo=ports[2], sessions_repo=ports[3]), label="cleanup-runtime-construction")
    return runtime, runtime.runtime_context if kind == "context" else runtime


async def release_cleanup_runtime(runtime, ports):
    for port in ports:
        port.failure = False
        if port.hold is not None:
            port.hold.release.set()
    try:
        if runtime is not None:
            await runtime.close()
    finally:
        for port in ports:
            await asyncio.to_thread(NativeCleanupPort.close, port)


def exception_leaves(error):
    if isinstance(error, BaseExceptionGroup):
        return [leaf for child in error.exceptions for leaf in exception_leaves(child)]
    return [error]
