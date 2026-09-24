"""Fixtures for observing session snapshot clock and destination ownership."""
from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import aiosqlite

from orket.adapters.storage.async_repositories import AsyncSnapshotRepository
from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository
from orket.application.services.epic_publication_service import EpicPublicationService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.control_plane_models import RunRecord
from orket.core.contracts.epic_publication import EpicPublicationPlan
from orket.core.domain import RunState
from tests.helpers.kernel_state_probe import responsive_sqlite

__test__ = False

STAMP = "2046-03-04T05:06:07+00:00"


class RecordingClock(RuntimeInputService):
    def __init__(self) -> None:
        self.current = datetime.fromisoformat(STAMP)
        self.observations: list[str] = []

    def utc_now(self) -> datetime:
        self.observations.append(self.current.isoformat())
        return self.current


class HeldPublicationRepository:
    def __init__(self, owner: SQLiteEpicPublicationRepository) -> None:
        self.owner = owner
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.expired = False

    @asynccontextmanager
    async def transaction(self, session_id: str):
        self.entered.set()
        try:
            await asyncio.wait_for(self.release.wait(), timeout=5)
        except TimeoutError:
            self.expired = True
        async with self.owner.transaction(session_id) as transaction:
            yield transaction


class _Ledger:
    def __init__(self, session_id: str) -> None:
        self.row: dict[str, Any] = {
            "session_id": session_id,
            "status": "running",
            "failure_reason": None,
            "failure_class": None,
            "summary_json": {},
            "artifact_json": {},
        }

    async def get_run(self, session_id: str) -> dict[str, Any] | None:
        return dict(self.row) if self.row["session_id"] == session_id else None

    async def finalize_run(self, **values: Any) -> None:
        self.row.update(values)
        self.row["summary_json"] = dict(values["summary"])
        self.row["artifact_json"] = dict(values["artifacts"])


class _Sessions:
    def __init__(self, session_id: str) -> None:
        self.rows = {session_id: {"status": "Started", "transcript": None}}

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.rows.get(session_id)
        return dict(row) if row is not None else None

    async def complete_session(self, session_id: str, status: str, transcript: list[dict[str, Any]]) -> None:
        self.rows[session_id] = {"status": status, "transcript": json.dumps(transcript)}


class _Success:
    async def get(self, _session_id: str) -> None:
        return None

    async def record_success(self, **_values: Any) -> None:
        raise AssertionError("incomplete historical plan must not publish success")


class _ControlPlane:
    def __init__(self, run: RunRecord) -> None:
        self.run = run
        self.execution_repository = self
        self.publication = SimpleNamespace(repository=self)

    async def finalize_execution(self, **_values: Any) -> tuple[RunRecord, None]:
        return self.run, None

    async def get_run_record(self, *, run_id: str) -> RunRecord | None:
        return self.run if run_id == self.run.run_id else None

    async def get_final_truth(self, *, run_id: str) -> None:
        assert run_id == self.run.run_id
        return None


def historical_plan(session_id: str) -> EpicPublicationPlan:
    run = _run_record(session_id)
    return EpicPublicationPlan(
        session_id=session_id,
        request={"build_id": "snapshot-build", "epic": {"name": "snapshot-epic", "issues": []}},
        ledger={
            "session_id": session_id,
            "status": "incomplete",
            "failure_reason": None,
            "failure_class": None,
            "summary": {},
            "artifacts": {"control_plane_run_record": run.model_dump(mode="json")},
            "finalized_at": STAMP,
        },
        transcript=[{"role": "coder", "issue": "ISSUE-1", "content": "retained"}],
        snapshot={"epic": {"name": "snapshot-epic"}, "team": {"name": "standard"},
                  "env": {"name": "standard"}, "build_id": "snapshot-build"},
    )


def publication_state(plan: EpicPublicationPlan) -> SimpleNamespace:
    return SimpleNamespace(
        sessions=_Sessions(plan.session_id),
        success=_Success(),
        ledger=_Ledger(plan.session_id),
        control_plane=_ControlPlane(_run_record(plan.session_id)),
    )


def publication_service(repository: Any, snapshots: AsyncSnapshotRepository,
                        state: SimpleNamespace, root: Path) -> EpicPublicationService:
    return EpicPublicationService(
        repository=repository,
        cards=SimpleNamespace(),
        sessions=state.sessions,
        snapshots=snapshots,
        success=state.success,
        ledger=state.ledger,
        control_plane=state.control_plane,
        scope={"workspace": str(root)},
    )


async def initialize_snapshot_stores(root: Path) -> tuple[AsyncSnapshotRepository, AsyncSnapshotRepository]:
    await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True)
    first = AsyncSnapshotRepository(root / "snapshot-a.db")
    second = AsyncSnapshotRepository(root / "snapshot-b.db")
    await first.record("seed-a", {"seed": "a"}, [])
    await second.record("seed-b", {"seed": "b"}, [])
    return first, second


async def wait_for_lock_waiter(lock: asyncio.Lock) -> None:
    deadline = asyncio.get_running_loop().time() + 1
    while asyncio.get_running_loop().time() < deadline:
        if any(not waiter.done() for waiter in (lock._waiters or ())):
            return
        await asyncio.sleep(0.001)
    raise TimeoutError("snapshot repository record did not wait on its owned lock")


async def _drain_case_tasks(tasks: tuple[asyncio.Task[Any], ...], operation: asyncio.Task[Any],
                            primary_error: BaseException | None) -> dict[str, bool]:
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=10)
    except BaseException as cleanup_error:
        if primary_error is None:
            raise
        primary_error.add_note(
            f"session snapshot probe cleanup failed: {type(cleanup_error).__name__}: {cleanup_error}"
        )
    return {"task_done": operation.done(), "drained": all(task.done() for task in tasks)}


async def run_repository_path_case(root: Path, *, mutate: bool, record_property: Any,
                                   mutate_inputs: bool = False) -> dict[str, Any]:
    first, second = await initialize_snapshot_stores(root)
    before = await snapshot_observation(first, second, "target", operations=["stores_initialized"])
    original_path = first.db_path
    config: dict[str, Any] = {"value": "captured-a"}
    logs: list[dict[str, Any]] = []
    if mutate_inputs:
        config["nested"] = {"label": "original"}
        logs.append({"event": "original", "nested": {"count": 1}})
    borrowed_before = json.loads(json.dumps({"config": config, "logs": logs}))
    operations = ["stores_initialized"]
    watchdog_state = SimpleNamespace(expired=False)
    await first._lock.acquire()
    watchdog = asyncio.create_task(_release_lock(first._lock, watchdog_state))
    task = asyncio.create_task(first.record("target", config, logs))
    hold_active = False
    primary_error: BaseException | None = None
    try:
        await wait_for_lock_waiter(first._lock)
        hold_active = first._lock.locked() and not watchdog_state.expired
        operations.append("record_waiting_on_a_lock")
        await responsive_sqlite(root / "responsive.db", record_property)
        operations.append("responsive_sqlite_complete")
        if mutate_inputs:
            config["nested"]["label"] = "changed"
            logs[0]["nested"]["count"] = 2
            operations.append("borrowed_inputs_changed")
        if mutate:
            first.db_path = second.db_path
            operations.append("db_path_changed_to_b")
        if first._lock.locked():
            first._lock.release()
            operations.append("a_lock_released")
        else:
            operations.append("watchdog_released_a_lock")
        await asyncio.wait_for(task, timeout=5)
        operations.append("record_complete")
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        first.db_path = original_path
        if first._lock.locked():
            first._lock.release()
        watchdog.cancel()
        cleanup = await _drain_case_tasks((watchdog, task), task, primary_error)
    after = await snapshot_observation(first, second, "target", operations=operations)
    return {"before": before, "after": after,
            "borrowed": {"before": borrowed_before,
                         "after": json.loads(json.dumps({"config": config, "logs": logs}))},
            "cleanup": cleanup,
            "hold": {"active_before_responsive_probe": hold_active,
                     "watchdog_expired": bool(watchdog_state.expired)}}


async def run_publication_case(root: Path, *, route: str, mutate: bool,
                               record_property: Any) -> dict[str, Any]:
    first, second = await initialize_snapshot_stores(root)
    plan = historical_plan("historical-session")
    state = publication_state(plan)
    journal = SQLiteEpicPublicationRepository(root / "publication.db")
    if route == "recover":
        await publication_service(journal, first, state, root).publish(plan)
    before = await snapshot_observation(first, second, plan.session_id, operations=["stores_initialized"])
    journal_before = await publication_journal_observation(journal, plan.session_id)
    held = HeldPublicationRepository(journal)
    service = publication_service(held, first, state, root)
    operation = service.publish(plan) if route == "publish" else service.recover(plan.session_id, plan.request)
    task = asyncio.create_task(operation)
    operations = [route + "_started"]
    result, error = None, None
    hold_active = False
    primary_error: BaseException | None = None
    try:
        await asyncio.wait_for(held.entered.wait(), timeout=1)
        hold_active = held.entered.is_set() and not held.release.is_set() and not held.expired
        operations.append("journal_boundary_held")
        await responsive_sqlite(root / "responsive.db", record_property)
        operations.append("responsive_sqlite_complete")
        if mutate:
            service.snapshots = second
            operations.append("publisher_changed_to_b")
        held.release.set()
        operations.append("journal_boundary_released")
        try:
            result = await asyncio.wait_for(task, timeout=5)
        except ValueError as exc:  # Captured so physical evidence precedes the defect assertion.
            error = {"type": type(exc).__name__, "message": str(exc)}
        operations.append("operation_settled")
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        held.release.set()
        if not task.done():
            task.cancel()
        cleanup = await _drain_case_tasks((task,), task, primary_error)
    after = await snapshot_observation(first, second, plan.session_id, operations=operations)
    return {
        "route": route,
        "mutated": mutate,
        "hold": {"active_before_responsive_probe": hold_active, "watchdog_expired": held.expired},
        "error": error,
        "cleanup": cleanup,
        "result": None if result is None else result.model_dump(mode="json"),
        "expected_snapshot": plan.snapshot,
        "before": before,
        "after": after,
        "journal": {"before": journal_before,
                    "after": await publication_journal_observation(journal, plan.session_id)},
    }


async def snapshot_observation(first: AsyncSnapshotRepository, second: AsyncSnapshotRepository,
                               session_id: str, *, operations: list[str]) -> dict[str, Any]:
    first_path, second_path = Path(first.db_path), Path(second.db_path)
    return {
        "operations": list(operations),
        "a_row": await read_snapshot_row(first_path, session_id),
        "b_row": await read_snapshot_row(second_path, session_id),
        "seed_rows": {"a": await read_snapshot_row(first_path, "seed-a"),
                      "b": await read_snapshot_row(second_path, "seed-b")},
        "physical": {"a": await physical_file(first_path), "b": await physical_file(second_path)},
    }


async def publication_journal_observation(repository: SQLiteEpicPublicationRepository,
                                          session_id: str) -> dict[str, Any]:
    path = repository.db_path
    physical = await physical_file(path)
    if not physical["exists"]:
        return {"physical": physical, "phase": None, "outcome_present": False}
    async with aiosqlite.connect(path) as connection:
        publication = await (await connection.execute(
            "SELECT payload FROM epic_publications WHERE session_id = ?", (session_id,)
        )).fetchone()
        outcome = await (await connection.execute(
            "SELECT 1 FROM epic_workload_outcomes WHERE session_id = ?", (session_id,)
        )).fetchone()
    phase = None if publication is None else json.loads(publication[0]).get("phase")
    return {"physical": await physical_file(path), "phase": phase,
            "outcome_present": outcome is not None}


async def read_snapshot_row(path: Path, session_id: str) -> dict[str, Any] | None:
    if not await asyncio.to_thread(path.is_file):
        return None
    async with aiosqlite.connect(path) as connection:
        connection.row_factory = aiosqlite.Row
        table = await (await connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_snapshots'"
        )).fetchone()
        if table is None:
            return None
        row = await (await connection.execute(
            "SELECT * FROM session_snapshots WHERE session_id = ?", (session_id,)
        )).fetchone()
    return dict(row) if row is not None else None


async def physical_file(path: Path) -> dict[str, Any]:
    resolved = await asyncio.to_thread(path.resolve)
    exists = await asyncio.to_thread(resolved.is_file)
    if not exists:
        return {"path": str(resolved), "exists": False, "size": 0, "sha256": None}
    data = await asyncio.to_thread(resolved.read_bytes)
    return {"path": str(resolved), "exists": True, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def decoded_config(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return json.loads(row["config_json"]) if row is not None else None


def _run_record(session_id: str) -> RunRecord:
    return RunRecord(
        run_id="control-plane:" + session_id,
        workload_id="snapshot-workload",
        workload_version="v1",
        policy_snapshot_id="policy:snapshot",
        policy_digest="sha256:policy",
        configuration_snapshot_id="configuration:snapshot",
        configuration_digest="sha256:configuration",
        creation_timestamp=STAMP,
        admission_decision_receipt_ref="admission:snapshot",
        lifecycle_state=RunState.WAITING_ON_OBSERVATION,
    )


async def _release_lock(lock: asyncio.Lock, state: SimpleNamespace) -> None:
    await asyncio.sleep(5)
    state.expired = True
    if lock.locked():
        lock.release()
