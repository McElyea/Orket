"""Layer: integration. Guard-rejection rows retain one clock and publisher owner."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.orchestrator_turn_success_handler import OrchestratorTurnSuccessHandler
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.core.domain.execution import ExecutionTurn
from orket.core.domain.records import IssueRecord
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus, IssueConfig
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_EXPECTED_TIME = datetime(2046, 2, 3, 4, 5, 6, tzinfo=UTC)


class _RecordingInputs(RuntimeInputService):
    def __init__(self, start: datetime = _EXPECTED_TIME) -> None:
        self.current = start
        self.observations: list[datetime] = []

    def utc_now(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        self.observations.append(value)
        return value


def _case(pipeline, tmp_path: Path, clock: _RecordingInputs):
    orchestrator = pipeline.orchestrator
    b_pending_path = tmp_path / "pending-b.sqlite3"
    b_control_path = tmp_path / "control-b.sqlite3"
    b_pending = AsyncPendingGateRepository(b_pending_path)
    b_repository = AsyncControlPlaneRecordRepository(b_control_path)
    b_publisher = ToolApprovalControlPlaneReservationService(
        publication=ControlPlanePublicationService(repository=b_repository)
    )
    return SimpleNamespace(
        orchestrator=orchestrator,
        clock=clock,
        b_clock=_RecordingInputs(_EXPECTED_TIME + timedelta(days=1)),
        a_pending=orchestrator.pending_gates,
        a_publisher=orchestrator.tool_approval_control_plane_reservation,
        a_pending_path=Path(orchestrator.pending_gates.db_path),
        a_control_path=Path(orchestrator.control_plane_repository.db_path),
        b_pending=b_pending,
        b_publisher=b_publisher,
        b_repository=b_repository,
        b_pending_path=b_pending_path,
        b_control_path=b_control_path,
    )


async def _physical(path: Path) -> dict[str, object]:
    resolved = await asyncio.to_thread(path.resolve)
    exists = await asyncio.to_thread(resolved.exists)
    if not exists:
        return {"path": str(resolved), "exists": False, "size": 0, "sha256": None}
    payload = await asyncio.to_thread(resolved.read_bytes)
    return {
        "path": str(resolved),
        "exists": True,
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def _request(orchestrator, *, session_id: str = "guard-session") -> str:
    return await orchestrator._create_pending_gate_request(
        run_id=session_id,
        issue_id="GUARD-1",
        seat_name="integrity_guard",
        reason="missing_rationale",
        payload={"rationale": "", "violations": [], "remediation_actions": ["Fix it"]},
        issue=IssueConfig(id="GUARD-1", seat="integrity_guard", summary="Guard review"),
        turn_status=CardStatus.AWAITING_GUARD_REVIEW,
    )


def _hold_after_real_row(repository, monkeypatch):
    original = repository.create_request
    state = SimpleNamespace(entered=asyncio.Event(), release=asyncio.Event())

    async def held(**kwargs):  # type: ignore[no-untyped-def]
        request_id = await original(**kwargs)
        state.entered.set()
        await state.release.wait()
        return request_id

    monkeypatch.setattr(repository, "create_request", held)
    return state


@asynccontextmanager
async def _joined_request(coro, release: asyncio.Event):
    task = asyncio.create_task(coro)
    timer = asyncio.get_running_loop().call_later(5, release.set)
    primary_error = None
    try:
        yield task
    except BaseException as error:
        primary_error = error
        raise
    finally:
        release.set()
        timer.cancel()
        try:
            settled = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            if primary_error is None and settled and isinstance(settled[0], BaseException):
                raise settled[0]
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Guard request cleanup also failed: {error!r}")


async def _observe(case, *, session_id: str, request_id: str | None = None) -> dict[str, object]:
    rows = await case.a_pending.list_requests(session_id=session_id, status="pending")
    resolved_id = request_id or (str(rows[0]["request_id"]) if rows else "")
    a_physical = await _physical(case.a_control_path)
    a_reservation = None
    if resolved_id and bool(a_physical["exists"]):
        a_reservation = await case.a_publisher.publication.repository.get_latest_reservation_record(
            reservation_id=f"approval-reservation:{resolved_id}"
        )
    b_physical = await _physical(case.b_control_path)
    b_reservation = None
    if resolved_id and bool(b_physical["exists"]):
        b_reservation = await case.b_repository.get_latest_reservation_record(
            reservation_id=f"approval-reservation:{resolved_id}"
        )
    return {
        "rows": rows,
        "request_id": resolved_id,
        "a_reservation": None if a_reservation is None else a_reservation.model_dump(mode="json"),
        "b_reservation": None if b_reservation is None else b_reservation.model_dump(mode="json"),
        "clock": [value.isoformat() for value in case.clock.observations],
        "b_clock": [value.isoformat() for value in case.b_clock.observations],
        "physical": {
            "a_pending": await _physical(case.a_pending_path),
            "a_control": a_physical,
            "b_pending": await _physical(case.b_pending_path),
            "b_control": b_physical,
        },
    }


def _record(record_property, name: str, value: object) -> None:
    record_property(name, json.dumps(value, sort_keys=True, default=str))


def _assert_pending_row(observation: dict[str, object]) -> dict[str, object]:
    rows = observation["rows"]
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert (row["session_id"], row["issue_id"], row["seat_name"]) == (
        "guard-session", "GUARD-1", "integrity_guard")
    assert row["request_type"] == "guard_rejection_payload"
    assert row["reason"] == "missing_rationale" and row["gate_mode"] == "review_required"
    assert row["created_at"] == row["updated_at"]
    return row


@pytest.mark.parametrize("admitted", ["publisher-a", "publisher-none"])
async def test_guard_request_retains_admitted_owners_after_real_pending_row(
    test_root, workspace, db_path, tmp_path, monkeypatch, record_property, admitted,
) -> None:
    clock = _RecordingInputs()
    async with ExecutionPipeline.open(
        workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock,
    ) as pipeline:
        case = _case(pipeline, tmp_path, clock)
        owner = case.a_publisher if admitted == "publisher-a" else None
        case.orchestrator.tool_approval_control_plane_reservation = owner
        hold = _hold_after_real_row(case.a_pending, monkeypatch)
        clock.current = _EXPECTED_TIME
        clock.observations.clear()
        before = {name: await _physical(path) for name, path in {
            "a_pending": case.a_pending_path, "a_control": case.a_control_path,
            "b_pending": case.b_pending_path, "b_control": case.b_control_path}.items()}
        try:
            async with _joined_request(_request(case.orchestrator), hold.release) as task:
                await asyncio.wait_for(hold.entered.wait(), 5)
                await responsive_sqlite(tmp_path / f"responsive-{admitted}.sqlite3",
                    lambda key, value: record_property(f"{admitted}_{key}", value))
                case.orchestrator.turn_clock = case.b_clock.utc_now
                case.orchestrator.pending_gates = case.b_pending
                case.orchestrator.tool_approval_control_plane_reservation = case.b_publisher
                hold.release.set()
                request_id = await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            case.orchestrator.turn_clock = clock.utc_now
            case.orchestrator.pending_gates = case.a_pending
            case.orchestrator.tool_approval_control_plane_reservation = case.a_publisher
        observation = await _observe(case, session_id="guard-session", request_id=request_id)
        _record(record_property, f"held_{admitted}_before", before)
        _record(record_property, f"held_{admitted}_observation", observation)
        row = _assert_pending_row(observation)
        assert observation["clock"] == [_EXPECTED_TIME.isoformat()] and observation["b_clock"] == []
        assert row["created_at"] == _EXPECTED_TIME.isoformat()
        reservation = observation["a_reservation"]
        if owner is None:
            assert reservation is None
        else:
            assert reservation is not None
            assert reservation["creation_timestamp"] == row["created_at"]
        assert observation["b_reservation"] is None
        assert observation["physical"]["b_pending"]["exists"] is False
        assert observation["physical"]["b_control"]["exists"] is False


@pytest.mark.parametrize("publisher_enabled", [True, False], ids=["publisher-a", "publisher-none"])
async def test_guard_request_healthy_real_sqlite_control(
    test_root, workspace, db_path, tmp_path, record_property, publisher_enabled,
) -> None:
    clock = _RecordingInputs()
    async with ExecutionPipeline.open(
        workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock,
    ) as pipeline:
        case = _case(pipeline, tmp_path, clock)
        if not publisher_enabled:
            case.orchestrator.tool_approval_control_plane_reservation = None
        before = {"pending": await _physical(case.a_pending_path),
                  "control": await _physical(case.a_control_path)}
        clock.current = _EXPECTED_TIME
        clock.observations.clear()
        request_id = await _request(case.orchestrator)
        observation = await _observe(case, session_id="guard-session", request_id=request_id)
        _record(record_property, f"healthy_{publisher_enabled}_before", before)
        _record(record_property, f"healthy_{publisher_enabled}_observation", observation)
        row = _assert_pending_row(observation)
        reservation = observation["a_reservation"]
        assert (reservation is not None) is publisher_enabled
        if reservation is not None:
            assert reservation["creation_timestamp"] == row["created_at"]
            assert reservation["holder_ref"] == f"approval-request:{request_id}"
        assert observation["physical"]["a_pending"]["size"] > 0
        assert observation["physical"]["b_pending"]["exists"] is False
        assert observation["physical"]["b_control"]["exists"] is False


@pytest.mark.parametrize("malformed", ["missing-method", "none-method"])
async def test_guard_request_persists_row_before_malformed_publisher_failure(
    test_root, workspace, db_path, tmp_path, record_property, malformed,
) -> None:
    clock = _RecordingInputs()
    async with ExecutionPipeline.open(
        workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock,
    ) as pipeline:
        case = _case(pipeline, tmp_path, clock)
        publisher = SimpleNamespace()
        expected_error = AttributeError
        if malformed == "none-method":
            publisher.publish_pending_guard_review_hold = None
            expected_error = TypeError
        case.orchestrator.tool_approval_control_plane_reservation = publisher
        before = {
            "pending": await _physical(case.a_pending_path),
            "control": await _physical(case.a_control_path),
        }
        clock.current = _EXPECTED_TIME
        clock.observations.clear()
        captured_error = None
        try:
            await _request(case.orchestrator)
        except (AttributeError, TypeError) as error:
            captured_error = error
        observation = await _observe(case, session_id="guard-session")
        error_observation = None if captured_error is None else {
            "type": type(captured_error).__name__, "message": str(captured_error)}
        _record(record_property, f"malformed_{malformed}_before", before)
        _record(record_property, f"malformed_{malformed}_observation", observation)
        _record(record_property, f"malformed_{malformed}_error", error_observation)
        row = _assert_pending_row(observation)
        assert isinstance(captured_error, expected_error)
        assert "publish_pending_guard_review_hold" in str(captured_error) or "callable" in str(captured_error)
        assert observation["clock"] == [_EXPECTED_TIME.isoformat()]
        assert row["created_at"] == _EXPECTED_TIME.isoformat()
        assert observation["a_reservation"] is None and observation["b_reservation"] is None
        assert observation["physical"]["a_pending"]["size"] > 0
        assert observation["physical"]["b_pending"]["exists"] is False
        assert observation["physical"]["b_control"]["exists"] is False


async def test_public_guard_success_uses_selected_clock_for_request_and_hold(
    test_root, workspace, db_path, tmp_path, record_property,
) -> None:
    clock = _RecordingInputs()
    async with ExecutionPipeline.open(
        workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock,
    ) as pipeline:
        case = _case(pipeline, tmp_path, clock)
        issue = IssueConfig(id="GUARD-1", seat="integrity_guard", summary="Guard review")
        assert issue.name is not None
        await pipeline.async_cards.save(IssueRecord(
            id=issue.id, summary=issue.name, seat=issue.seat,
            status=CardStatus.GUARD_REJECTED, build_id="guard-build"))
        failures = []

        async def capture_failure(*args, **kwargs):  # type: ignore[no-untyped-def]
            failures.append((args, kwargs))

        orchestrator = case.orchestrator
        handler = OrchestratorTurnSuccessHandler(
            workspace_root=orchestrator.workspace, transcript=[], async_cards=pipeline.async_cards,
            memory=orchestrator.memory, evaluator_node=orchestrator.evaluator_node,
            issue_control_plane=orchestrator.issue_control_plane,
            request_issue_transition=orchestrator._request_issue_transition,
            trigger_sandbox=orchestrator._trigger_sandbox,
            is_sandbox_disabled=orchestrator._is_sandbox_disabled,
            save_checkpoint=orchestrator._save_checkpoint,
            create_pending_gate_request=orchestrator._create_pending_gate_request,
            validate_guard_rejection_payload=orchestrator._validate_guard_rejection_payload,
            extract_guard_review_payload=orchestrator._extract_guard_review_payload,
            resolve_guard_event=orchestrator._resolve_guard_event,
            handle_failure=capture_failure,
        )
        turn = ExecutionTurn(timestamp=None, role="integrity_guard", issue_id=issue.id,
            content=json.dumps({"rationale": "", "violations": [], "remediation_actions": ["Fix it"]}))
        clock.current = _EXPECTED_TIME
        clock.observations.clear()
        await handler.handle(issue=issue, result=SimpleNamespace(turn=turn), provider=None,
            run_id="guard-session", seat_name="integrity_guard", roles_to_load=["integrity_guard"],
            turn_index=1, turn_status=CardStatus.AWAITING_GUARD_REVIEW, is_guard_turn=True,
            is_review_turn=True, epic=None, team=None, env=None, active_build="guard-build", context={})
        observation = await _observe(case, session_id="guard-session")
        _record(record_property, "public_guard_observation", observation)
        _record(record_property, "public_guard_failures", failures)
        row = _assert_pending_row(observation)
        assert observation["clock"] == [_EXPECTED_TIME.isoformat()]
        assert row["created_at"] == _EXPECTED_TIME.isoformat()
        assert observation["a_reservation"]["creation_timestamp"] == row["created_at"]
        assert observation["physical"]["a_pending"]["size"] > 0
        assert observation["physical"]["a_control"]["size"] > 0
        assert len(failures) == 1


async def test_guard_request_reservation_failure_keeps_durable_pending_prefix(
    test_root, workspace, db_path, tmp_path, monkeypatch, record_property,
) -> None:
    clock = _RecordingInputs()
    async with ExecutionPipeline.open(
        workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock,
    ) as pipeline:
        case = _case(pipeline, tmp_path, clock)
        save_attempts = []

        async def fail_reservation(*, record):  # type: ignore[no-untyped-def]
            save_attempts.append(record.model_dump(mode="json"))
            raise sqlite3.OperationalError("controlled reservation persistence failure")

        monkeypatch.setattr(
            case.a_publisher.publication.repository, "save_reservation_record", fail_reservation)
        before = await _physical(case.a_pending_path)
        clock.current = _EXPECTED_TIME
        clock.observations.clear()
        with pytest.raises(sqlite3.OperationalError, match="controlled reservation persistence failure"):
            await _request(case.orchestrator)
        observation = await _observe(case, session_id="guard-session")
        _record(record_property, "reservation_fault_before", before)
        _record(record_property, "reservation_fault_observation", observation)
        _record(record_property, "reservation_fault_save_attempts", save_attempts)
        row = _assert_pending_row(observation)
        assert observation["clock"] == [_EXPECTED_TIME.isoformat()]
        assert row["created_at"] == _EXPECTED_TIME.isoformat()
        assert len(save_attempts) == 1
        assert observation["a_reservation"] is None
        assert observation["physical"]["a_pending"]["size"] > 0
