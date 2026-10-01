"""Native fault injection around the actual process writer's sole start attempt."""
from __future__ import annotations

import asyncio
import threading


class WriterStartHold:
    def __init__(self, phase, kind):
        self.phase = phase
        self.failure = None if kind == "success" else {
            "RuntimeError": RuntimeError, "OSError": OSError, "SystemExit": SystemExit,
            "KeyboardInterrupt": KeyboardInterrupt, "CancelledError": asyncio.CancelledError,
        }[kind]("controlled writer startup failure")
        if self.failure is not None:
            self.failure.__cause__ = LookupError("original startup cause")
            self.failure.__context__ = ValueError("original startup context")
        self.original = threading.Thread.start
        self.entered, self.release, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.thread = None
        self.worker_ident = None
        self.calls = self.real_starts = 0
        self.expired = False

    def start(self, thread):
        if thread.name != "orket-log-writer":
            return self.original(thread)
        self.calls += 1
        self.thread = thread
        self.worker_ident = threading.get_ident()
        if self.phase == "after":
            self.original(thread)
            self.real_starts += 1
            assert thread.is_alive() and thread.ident is not None
        self.entered.set()
        try:
            self.expired = not self.release.wait(5)
            assert not self.expired, "startup hold was not independently released"
            if self.failure is not None:
                raise self.failure
            if self.phase == "before":
                self.original(thread)
                self.real_starts += 1
        finally:
            self.finished.set()

    def install(self, monkeypatch):
        monkeypatch.setattr(threading.Thread, "start", lambda thread: self.start(thread))
