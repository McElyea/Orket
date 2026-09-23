"""Layer: integration. One captured destination owns a composed turn."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_approval_publication import create_pending_tool_approval_request
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]
_RUN_A = "turn-tool-run:session-a:ISSUE-A:developer-a:0003"


class _RecordingClock:
    def __init__(self, published: list[str], source) -> None:
        self.published = published
        self.source = source
        self.observations: list[tuple[datetime, tuple[str, ...]]] = []

    def __call__(self) -> datetime:
        value = self.source()
        self.observations.append((value, tuple(self.published)))
        return value


class _ControlledModel:
    def __init__(self, *, held: bool) -> None:
        self.held = held
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.messages: list[list[dict[str, str]]] = []

    async def complete(self, messages):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.messages.append([dict(row) for row in messages])
        if self.held:
            self.entered.set()
            await asyncio.wait_for(self.release.wait(), 5)
        return {
            "content": (
                '{"content":"","tool_calls":[{"tool":"write_file",'
                '"args":{"path":"agent_output/out.txt","content":"ok"}}]}'
            ),
            "raw": {"total_tokens": 1},
        }


class _EffectToolbox:
    def __init__(self, root: Path) -> None:
        self.files = AsyncFileTools(root)
        self.contexts: list[dict[str, object]] = []
        self.effect_paths: list[str] = []

    async def execute(self, tool_name, args, context=None):  # type: ignore[no-untyped-def]
        captured = {key: context.get(key) for key in ("session_id", "issue_id", "role", "turn_index")}
        self.contexts.append(captured)
        effect = "effects/{session_id}_{issue_id}_{role}_{turn_index}.txt".format(**captured)
        self.effect_paths.append(effect)
        await self.files.write_file(str(args["path"]), str(args.get("content") or ""))
        await self.files.write_file(effect, str(args.get("content") or ""))
        return {"ok": True, "tool": tool_name, "touched_paths": [str(args["path"]), effect]}


def _issue() -> IssueConfig:
    return IssueConfig(id="ISSUE-A", summary="Implement feature", seat="developer-a", status=CardStatus.IN_PROGRESS)


def _role() -> RoleConfig:
    return RoleConfig(id="ROLE-A", summary="developer-a", description="Build code", tools=["write_file"])


def _context(*, compact: bool = False) -> dict[str, object]:
    return {
        "session_id": "session-a", "issue_id": "ISSUE-A", "role": "developer-a",
        "roles": ["developer-a"], "current_status": "in_progress", "selected_model": "controlled",
        "turn_index": 3, "history": [], "protocol_governed_enabled": True,
        "resume_mode": False, "protocol_replay_mode": False,
        "visibility_mode": "read_only", "memory_snapshot_id": "snapshot-a",
        "model_config_id": "model-a", "policy_set_id": "policy-a",
        "run_namespace_scope": "issue:ISSUE-A",
        "compact_turn_packet_enabled": compact,
    }


def _hold_execution_owner(monkeypatch, service):
    original = service.execution_owners.hold
    state = SimpleNamespace(entered=asyncio.Event(), release=asyncio.Event(), keys=[])

    @asynccontextmanager
    async def held(key):  # type: ignore[no-untyped-def]
        state.keys.append(key)
        state.entered.set()
        await asyncio.wait_for(state.release.wait(), 5)
        async with original(key) as reference:
            yield reference

    monkeypatch.setattr(service.execution_owners, "hold", held)
    return state


def _case(tmp_path: Path, monkeypatch, selected_clock, *, held_model: bool, compact: bool = False):
    root = tmp_path / "workspace-a"
    service = build_turn_tool_control_plane_service(tmp_path / "control-plane.sqlite3")
    drift_services = {
        token: build_turn_tool_control_plane_service(tmp_path / f"control-plane-{token.lower()}.sqlite3")
        for token in ("B", "C")
    }
    published: list[str] = []

    def datetime_source() -> datetime:
        return datetime.fromisoformat(selected_clock())

    clock = _RecordingClock(published, datetime_source)
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=root), workspace=root,
        control_plane_service=service, utc_now=clock)
    drift_dispatchers = {
        token: TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=root), workspace=root,
            control_plane_service=drift_service, utc_now=clock).tool_dispatcher
        for token, drift_service in drift_services.items()
    }
    admitted_writer = executor.artifact_writer
    original_write = admitted_writer.write_turn_artifact

    def observed_write(**kwargs):  # type: ignore[no-untyped-def]
        result = original_write(**kwargs)
        published.append(str(kwargs["filename"]))
        return result

    monkeypatch.setattr(admitted_writer, "write_turn_artifact", observed_write)
    return SimpleNamespace(root=root, service=service, drift_services=drift_services,
        dispatcher=executor.tool_dispatcher, drift_dispatchers=drift_dispatchers, executor=executor,
        writer=admitted_writer, owner=_hold_execution_owner(monkeypatch, service), issue=_issue(),
        role=_role(), context=_context(compact=compact), compact=compact,
        model=_ControlledModel(held=held_model), toolbox=_EffectToolbox(root), clock=clock,
        turn_clock=datetime_source, published=published)


def _mutate(case, tmp_path: Path, token: str) -> None:
    lower = token.lower()
    changed_root = tmp_path / f"workspace-{lower}"
    case.issue.id = f"ISSUE-{token}"
    case.role.name = f"developer-{lower}"
    case.role.id = f"ROLE-{token}"
    case.context.update(session_id=f"session-{lower}", issue_id=f"ISSUE-{token}",
                        role=f"developer-{lower}", turn_index=9,
                        run_namespace_scope=f"issue:ISSUE-{token}",
                        resume_mode=False, protocol_replay_mode=True)
    case.writer.workspace = changed_root
    case.executor.artifact_writer = TurnArtifactWriter(changed_root)
    case.dispatcher.control_plane_service = case.drift_services[token]
    case.executor.tool_dispatcher = case.drift_dispatchers[token]


def _turn_dir(case) -> Path:
    return case.root / "observability" / "session-a" / "issue-a" / "003_developer-a"


@asynccontextmanager
async def _turn_task(case):
    task = asyncio.create_task(case.executor.execute_turn(
        case.issue, case.role, case.model, case.toolbox, case.context, system_prompt="SYSTEM"))
    primary_error = None
    try:
        yield task
    except BaseException as error:
        primary_error = error
        raise
    finally:
        case.owner.release.set()
        case.model.release.set()
        try:
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Composed turn cleanup also failed: {error!r}")


async def _json(path: Path):
    return json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))


async def _assert_physical_identity(case, tmp_path: Path, result) -> None:
    directory = _turn_dir(case)
    messages = await _json(directory / "messages.json")
    prompt = "\n".join(str(row.get("content") or "") for row in messages)
    assert "Issue ISSUE-A: Implement feature" in prompt
    if case.compact:
        assert "TURN PACKET:" in prompt and "- role: developer-a" in prompt
        assert '"issue_id": "ISSUE-A"' not in prompt
    else:
        assert '"issue_id": "ISSUE-A"' in prompt and '"seat": "developer-a"' in prompt
    assert "ISSUE-B" not in prompt and "ISSUE-C" not in prompt
    assert "developer-b" not in prompt and "developer-c" not in prompt
    assert case.model.messages == [messages]
    assert result.success and result.turn.issue_id == "ISSUE-A" and result.turn.role == "developer-a"
    expected = ["model_response.txt", "model_response_raw.json", "tool_parser_diagnostics.json",
                "parsed_tool_calls.json", "tool_parser_summary.json", "checkpoint.json",
                "memory_trace.json", "memory_retrieval_trace.json"]
    assert all(await asyncio.gather(*(asyncio.to_thread((directory / name).is_file) for name in expected)))
    trace = await _json(directory / "memory_trace.json")
    assert (trace["run_id"], trace["issue_id"], trace["role_id"]) == ("session-a", "ISSUE-A", "ROLE-A")
    assert {event["role"] for event in trace["events"]} == {"developer-a"}
    for token in ("b", "c"):
        assert not await asyncio.to_thread((tmp_path / f"workspace-{token}" / "observability").exists)
        assert not await asyncio.to_thread((case.root / "observability" / f"session-{token}").exists)


async def _assert_effect_and_control_plane(case) -> None:
    expected_context = {"session_id": "session-a", "issue_id": "ISSUE-A",
                        "role": "developer-a", "turn_index": 3}
    assert case.toolbox.contexts == [expected_context]
    assert case.toolbox.effect_paths == ["effects/session-a_ISSUE-A_developer-a_3.txt"]
    assert await case.toolbox.files.read_file("agent_output/out.txt") == "ok"
    assert await case.toolbox.files.read_file(case.toolbox.effect_paths[0]) == "ok"
    run = await case.service.execution_repository.get_run_record(run_id=_RUN_A)
    assert run is not None and run.namespace_scope == "issue:ISSUE-A" and run.lifecycle_state.value == "completed"
    attempt = await case.service.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    steps = await case.service.execution_repository.list_step_records(attempt_id=run.current_attempt_id)
    checkpoint = await case.service.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{run.current_attempt_id}")
    assert attempt is not None and attempt.run_id == _RUN_A
    assert len(steps) == 1 and steps[0].namespace_scope == "issue:ISSUE-A"
    assert checkpoint is not None and checkpoint.creation_timestamp == case.clock.observations[1][0].isoformat()
    for token in ("B", "C"):
        drifted = f"turn-tool-run:session-{token.lower()}:ISSUE-{token}:developer-{token.lower()}:0009"
        assert await case.service.execution_repository.get_run_record(run_id=drifted) is None


async def _assert_no_drift_control_plane(case) -> None:
    for token, service in case.drift_services.items():
        drifted = f"turn-tool-run:session-{token.lower()}:ISSUE-{token}:developer-{token.lower()}:0009"
        for run_id in (_RUN_A, drifted):
            assert await service.execution_repository.get_run_record(run_id=run_id) is None
            assert await service.publication.repository.list_effect_journal_entries(run_id=run_id) == []


async def _assert_clock_and_checkpoints(case, result) -> None:
    assert len(case.clock.observations) == 2
    assert result.turn.timestamp == case.clock.observations[0][0]
    assert case.clock.observations[0][1][-3:] == (
        "tool_parser_diagnostics.json", "parsed_tool_calls.json", "tool_parser_summary.json")
    directory = _turn_dir(case)
    local = await _json(directory / "checkpoint.json")
    snapshots = await asyncio.to_thread(
        lambda: sorted(directory.glob("control_plane_checkpoint_snapshot_*.json")))
    assert len(snapshots) == 1
    snapshot = await _json(snapshots[0])
    assert local["captured_at"] == snapshot["captured_at"] == case.clock.observations[1][0].isoformat()
    assert (local["run_id"], local["issue_id"], local["role"], local["turn_index"]) == (
        "session-a", "ISSUE-A", "developer-a", 3)
    assert (snapshot["run_id"], snapshot["issue_id"], snapshot["role"], snapshot["turn_index"]) == (
        "session-a", "ISSUE-A", "developer-a", 3)


@pytest.mark.parametrize(
    ("held_model", "compact"),
    [(False, False), (True, False), (True, True)],
    ids=["owner-only", "owner-and-provider", "compact-owner-and-provider"],
)
async def test_composed_turn_keeps_one_destination_across_identity_mutation(
    tmp_path, monkeypatch, record_property, deterministic_turn_clock, held_model, compact,
) -> None:
    case = _case(tmp_path, monkeypatch, deterministic_turn_clock, held_model=held_model, compact=compact)
    async with _turn_task(case) as task:
        await asyncio.wait_for(case.owner.entered.wait(), 5)
        assert case.owner.keys == [_RUN_A]
        await responsive_sqlite(tmp_path / "owner-responsive.sqlite3",
            lambda key, value: record_property(f"owner_{key}", value))
        _mutate(case, tmp_path, "B")
        case.owner.release.set()
        if held_model:
            await asyncio.wait_for(case.model.entered.wait(), 5)
            await responsive_sqlite(tmp_path / "provider-responsive.sqlite3",
                lambda key, value: record_property(f"provider_{key}", value))
            _mutate(case, tmp_path, "C")
            case.model.release.set()
        result = await asyncio.wait_for(asyncio.shield(task), 15)
    await _assert_physical_identity(case, tmp_path, result)
    await _assert_effect_and_control_plane(case)
    await _assert_no_drift_control_plane(case)
    await _assert_clock_and_checkpoints(case, result)


async def test_approval_request_and_hold_keep_captured_destination(
    tmp_path, monkeypatch, record_property, deterministic_turn_clock,
) -> None:
    case = _case(tmp_path, monkeypatch, deterministic_turn_clock, held_model=False)
    pending = AsyncPendingGateRepository(tmp_path / "pending-gates.sqlite3")
    approval_clock_samples: list[datetime] = []

    def approval_clock() -> datetime:
        value = case.turn_clock()
        approval_clock_samples.append(value)
        return value

    approval_owner = SimpleNamespace(pending_gates=pending,
        tool_approval_control_plane_reservation=ToolApprovalControlPlaneReservationService(
            publication=case.service.publication), turn_clock=approval_clock)
    case.context.update(protocol_governed_enabled=False, approval_required_tools=["write_file"],
        stage_gate_mode="approval_required", run_namespace_scope="issue:ISSUE-A")
    case.context["create_pending_gate_request"] = partial(create_pending_tool_approval_request,
        approval_owner, issue_status="in_progress", gate_mode="approval_required")
    async with _turn_task(case) as task:
        await asyncio.wait_for(case.owner.entered.wait(), 5)
        await responsive_sqlite(tmp_path / "approval-responsive.sqlite3", record_property)
        _mutate(case, tmp_path, "B")
        case.owner.release.set()
        result = await asyncio.wait_for(asyncio.shield(task), 15)
    rows = await pending.list_requests(session_id="session-a", status="pending")
    assert not result.success and result.should_retry and case.toolbox.contexts == []
    assert len(rows) == 1 and await pending.list_requests(session_id="session-b") == []
    row, payload = rows[0], rows[0]["payload_json"]
    assert (row["issue_id"], row["seat_name"]) == ("ISSUE-A", "developer-a")
    assert payload["control_plane_target_ref"] == _RUN_A and payload["turn_index"] == 3
    assert len(approval_clock_samples) == 1
    assert row["created_at"] == approval_clock_samples[0].isoformat()
    reservation = await case.service.publication.repository.get_latest_reservation_record(
        reservation_id=f"approval-reservation:{row['request_id']}")
    assert reservation is not None and reservation.holder_ref == _RUN_A
    assert reservation.creation_timestamp == approval_clock_samples[0].isoformat()
    assert "session=session-a" in reservation.target_scope_ref and "issue=ISSUE-A" in reservation.target_scope_ref
    run = await case.service.execution_repository.get_run_record(run_id=_RUN_A)
    assert run is not None and run.lifecycle_state.value == "executing"
    assert await case.service.execution_repository.get_run_record(
        run_id="turn-tool-run:session-b:ISSUE-B:developer-b:0009") is None
    await _assert_no_drift_control_plane(case)
    assert await asyncio.to_thread((_turn_dir(case) / "checkpoint.json").is_file)
    assert not await asyncio.to_thread((tmp_path / "workspace-b" / "observability").exists)
    assert not await asyncio.to_thread((case.root / "observability" / "session-b").exists)


async def test_repeated_cancellation_before_owner_admission_has_no_effects(
    tmp_path, monkeypatch, record_property, deterministic_turn_clock,
) -> None:
    case = _case(tmp_path, monkeypatch, deterministic_turn_clock, held_model=False)
    async with _turn_task(case) as task:
        await asyncio.wait_for(case.owner.entered.wait(), 5)
        assert case.owner.keys == [_RUN_A]
        await responsive_sqlite(tmp_path / "cancel-responsive.sqlite3", record_property)
        _mutate(case, tmp_path, "B")
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)
    assert case.model.calls == 0 and case.toolbox.contexts == [] and case.clock.observations == []
    assert await case.service.execution_repository.get_run_record(run_id=_RUN_A) is None
    await _assert_no_drift_control_plane(case)
    assert not await asyncio.to_thread((case.root / "observability").exists)
    assert not await asyncio.to_thread((tmp_path / "workspace-b" / "observability").exists)
