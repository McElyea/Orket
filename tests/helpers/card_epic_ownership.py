"""Finite native SQLite holds; real connections still execute and close."""
from __future__ import annotations

import sqlite3
import threading
from types import SimpleNamespace


def hold_sqlite(monkeypatch, database, phase):
    original_connect = sqlite3.connect
    targets = {str(database), database.as_uri()}
    hold = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
        thread=None, expired=False, connections=[], closed=[], commits=0)

    def run(name, operation):
        if name == "commit":
            hold.commits += 1
        selected = name == phase and (phase != "commit" or hold.commits == 2)
        if not selected or hold.entered.is_set():
            return operation()
        hold.thread = threading.get_ident()
        hold.entered.set()
        try:
            hold.expired = not hold.release.wait(5)
            assert not hold.expired, "SQLite native operation was not released"
            return operation()
        finally:
            hold.finished.set()

    class NativeConnection(sqlite3.Connection):
        def commit(self):
            return run("commit", super().commit)

        def rollback(self):
            return run("rollback", super().rollback)

        def close(self):
            result = run("close", super().close)
            hold.closed.append(id(self))
            return result

    def connect(path, *args, **kwargs):
        if str(path).split("?")[0] not in targets:
            return original_connect(path, *args, **kwargs)
        kwargs["factory"] = NativeConnection
        connection = original_connect(path, *args, **kwargs)
        hold.connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    return hold
