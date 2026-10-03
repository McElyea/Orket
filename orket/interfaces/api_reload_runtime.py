"""Reload the API through cooperative worker shutdown instead of console broadcasts."""
from __future__ import annotations

import asyncio
import logging
import multiprocessing
import signal
from contextlib import suppress
from multiprocessing.context import SpawnProcess
from multiprocessing.synchronize import Event
from pathlib import Path
from socket import socket
from types import FrameType
from typing import TYPE_CHECKING

import uvicorn
from uvicorn._subprocess import get_subprocess
from uvicorn.server import HANDLED_SIGNALS

if TYPE_CHECKING:
    # Both runtime-selected reload strategies implement this canonical base.
    from uvicorn.supervisors.basereload import BaseReload as ChangeReload
else:
    from uvicorn.supervisors import ChangeReload

LOGGER = logging.getLogger("uvicorn.error")


class _ReloadServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, stop: Event) -> None:
        super().__init__(config)
        self._stop = stop
        self._signal_stop = False

    def run(self, sockets: list[socket] | None = None) -> None:
        # This server runs only in the dedicated reload worker. Keep cooperative
        # handlers through the serving loop, including Uvicorn restoration.
        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.handle_exit)
        try:
            super().run(sockets=sockets)
        finally:
            # CPython resets callable handlers to OS defaults during interpreter
            # teardown. Native ignore survives that teardown; the parent still
            # joins this dedicated worker and rejects every nonzero finalizer exit.
            for sig in HANDLED_SIGNALS:
                signal.signal(sig, signal.SIG_IGN)

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        # A signal may interrupt the shared Event's non-reentrant lock.
        # Latch locally; the serving task observes the request without locking here.
        self._signal_stop = True

    async def serve(self, sockets: list[socket] | None = None) -> None:
        async def observe_stop() -> None:
            # Older supported Uvicorn versions skip shutdown when should_exit is
            # set during startup. Finish startup before requesting its normal close.
            # A process-shared Event cannot be replaced by a loop-local asyncio.Event.
            while not self.started or not (self._signal_stop or self._stop.is_set()):  # noqa: ASYNC110
                await asyncio.sleep(0.05)
            self.should_exit = True

        observation = asyncio.create_task(observe_stop(), name="api-reload-stop")
        try:
            await super().serve(sockets=sockets)
            if self.lifespan.should_exit:
                raise RuntimeError("E_API_RELOAD_LIFESPAN_FAILED: see the worker's lifespan error")
        finally:
            observation.cancel()
            with suppress(asyncio.CancelledError):
                await observation


class _ReloadSupervisor(ChangeReload):
    def __init__(self, config: uvicorn.Config, server: _ReloadServer, sockets: list[socket], stop: Event) -> None:
        super().__init__(config, target=server.run, sockets=sockets)
        self._stop, self._closed = stop, False
        self._signal_stop = False

    def signal_handler(self, sig: int, frame: FrameType | None) -> None:
        # The inherited handler acquires the same Event lock used by pause().
        # Only latch here; publish to the watcher event from ordinary control flow.
        self._signal_stop = True

    def pause(self) -> None:
        if self._signal_stop:
            self.should_exit.set()
        super().pause()
        if self._signal_stop:
            self.should_exit.set()
            raise StopIteration()

    def _stop_worker(self) -> None:
        self._stop.set()
        process: SpawnProcess | None = getattr(self, "process", None)
        if process is not None and process.pid is not None:
            process.join()

    def restart(self) -> None:
        self._stop_worker()
        self._check_worker_success()
        if self._signal_stop or self.should_exit.is_set():
            return
        self._stop.clear()
        self.process = get_subprocess(config=self.config, target=self.target, sockets=self.sockets)
        self.process.start()

    def should_restart(self) -> list[Path] | None:
        changes = super().should_restart()
        process: SpawnProcess | None = getattr(self, "process", None)
        if process is not None and process.exitcode is not None:
            raise RuntimeError(f"E_API_RELOAD_WORKER_EXIT: {process.exitcode}")
        return changes

    def _check_worker_success(self) -> None:
        process: SpawnProcess | None = getattr(self, "process", None)
        if process is not None and process.exitcode not in (None, 0):
            raise RuntimeError(f"E_API_RELOAD_WORKER_FAILED: {process.exitcode}")

    def shutdown(self) -> None:
        if self._closed:
            return
        self.should_exit.set()
        self._stop_worker()
        for listener in self.sockets:
            listener.close()
        self._closed = True
        LOGGER.info("Stopping reloader process [%s]", self.pid)
        self._check_worker_success()


def run_reloading_api_server(app: str, *, host: str, port: int, reload_excludes: list[str]) -> None:
    """Own one spawned worker at a time; native cleanup has no hard-stop deadline."""
    config = uvicorn.Config(app, host=host, port=port, reload=True, reload_excludes=reload_excludes, lifespan="on")
    stop = multiprocessing.get_context("spawn").Event()
    server = _ReloadServer(config, stop)
    listener = config.bind_socket()
    try:
        supervisor = _ReloadSupervisor(config, server, [listener], stop)
        try:
            supervisor.run()
        finally:
            supervisor.shutdown()
    finally:
        listener.close()
