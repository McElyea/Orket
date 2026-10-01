"""Real writable SQLite holds for outward initializer and transaction controls."""
from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from functools import partial
from pathlib import Path

import aiosqlite

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.outward_store_transaction import OutwardStoreUnitOfWork
from orket.application.services.outward_run_service import OutwardRunService
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord
from tests.helpers.governed_read_ownership import NativeReadProbe

STORES = {"runs": OutwardRunStore, "approvals": OutwardApprovalStore, "events": OutwardRunEventStore}
TABLES = {"runs": "outward_runs", "approvals": "outward_approval_proposals_v2", "events": "run_events"}
NOW = "2026-09-28T12:00:00+00:00"


class NativeStoreProbe(NativeReadProbe):
    """Reuse finite holds/cleanup while selecting actual writable connection phases."""

    def _selected(self, database):
        return str(database) == str(self.path)

    def _observe_paths(self, monkeypatch):
        def observe(name, original):
            def observed(path, *args, **kwargs):
                call = partial(original, path, *args, **kwargs)
                selected = path == (self.path.parent if name == "mkdir" else self.path)
                if name == "resolve" and path == Path(self.path.name):
                    selected = True
                if selected:
                    self.path_calls.append((name, path))
                return self._pause(call) if selected and self.boundary == name else call()
            return observed

        for name in ("resolve", "mkdir"):
            monkeypatch.setattr(Path, name, observe(name, getattr(Path, name)))

    def _observe_connections(self, monkeypatch):
        original_native, original_async, probe = sqlite3.connect, aiosqlite.connect, self

        class ObservedConnection(sqlite3.Connection):
            closed = False

            def execute(self, sql, *args, **kwargs):
                normalized = " ".join(sql.upper().split())
                matches = {"wal": normalized.startswith("PRAGMA JOURNAL_MODE"),
                    "begin": normalized == "BEGIN IMMEDIATE",
                    "schema": normalized.startswith("CREATE TABLE"),
                    "body": normalized.startswith("INSERT INTO OUTWARD_RUNS")}
                call = partial(super().execute, sql, *args, **kwargs)
                return probe._pause(call) if matches.get(probe.boundary, False) else call()

            def commit(self):
                return probe._pause(super().commit) if probe.boundary == "commit" else super().commit()

            def rollback(self):
                return probe._pause(super().rollback) if probe.boundary == "rollback" else super().rollback()

            def close(self):
                def close_native():
                    result = sqlite3.Connection.close(self)
                    self.closed = True
                    return result
                return probe._pause(close_native) if probe.boundary == "close" else close_native()

        def native(database, *args, **kwargs):
            if not probe._selected(database):
                return original_native(database, *args, **kwargs)
            # Cross-thread access is solely for failed-opening recovery. Tests assert
            # actual worker closure before inherited cleanup may close leaked handles.
            kwargs.update(factory=ObservedConnection, check_same_thread=False)
            connection = original_native(database, *args, **kwargs)
            probe.native.append(connection)
            if probe.boundary == "connect":
                try:
                    return probe._pause(lambda: connection)
                except BaseException:
                    connection.close()
                    raise
            return connection

        def asynchronous(database, *args, **kwargs):
            connection = original_async(database, *args, **kwargs)
            if probe._selected(database):
                probe.connections.append(connection)
            return connection

        monkeypatch.setattr(sqlite3, "connect", native)
        monkeypatch.setattr(aiosqlite, "connect", asynchronous)


def stores_and_service(path):
    stores = {name: constructor(path) for name, constructor in STORES.items()}
    unit = OutwardStoreUnitOfWork(approvals=stores["approvals"], runs=stores["runs"], events=stores["events"])
    service = OutwardRunService(run_store=stores["runs"], event_store=stores["events"], unit_of_work=unit,
        run_id_factory=lambda: "owned-run", utc_now=lambda: NOW)
    return stores, unit, service


async def initialize(stores):
    for name in ("approvals", "runs", "events"):
        await stores[name].ensure_initialized()


def submission():
    return {"run_id": "owned-run", "namespace": "issue:owned", "task":
        {"description": "owned transaction", "instruction": "retain native work"}}


def run_record():
    return OutwardRunRecord(run_id="owned-run", status="queued", namespace="issue:owned", submitted_at=NOW,
        current_turn=0, max_turns=20, task=submission()["task"], policy_overrides={}, execution_generation=1)


def proposal():
    return OutwardApprovalProposal(proposal_id="owned-proposal", run_id="owned-run", namespace="issue:owned",
        tool="read_file", args_preview={}, context_summary="fixture", risk_level="low", submitted_at=NOW,
        expires_at="2026-09-29T12:00:00+00:00")


def event():
    return LedgerEvent(event_id="owned-event", event_type="tool_invoked", run_id="owned-run", turn=0,
        agent_id="fixture", at=NOW, payload={})


async def borrow(store, family, operation, connection):
    value = {"runs": run_record, "approvals": proposal, "events": event}[family]()
    arguments = {"get": "missing", "get_active_by_namespace": "issue:owned", "count_for_run": "owned-run"}
    return await getattr(store, operation)(arguments.get(operation, value), connection=connection)


def _state(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                for name in names if name in set(TABLES.values()) | {"control_plane_runs"}}


async def state(path):
    return await asyncio.to_thread(_state, path)
