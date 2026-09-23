"""A composed turn cannot publish terminal success before releasing its authority."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services import turn_tool_control_plane_closeout as closeout
from orket.application.services import turn_tool_control_plane_service as service_module
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_resource_lifecycle import lease_id_for_run
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain import AttemptState, LeaseStatus, RunState
from orket.core.domain.state_machine import StateMachine
from tests.helpers.turn_artifacts import artifact_test_utc_now
from tests.integration.test_governed_agent_terminal_history import damage_terminal_history, logical_state
from tests.integration.test_turn_executor_control_plane import _context, _issue, _Model, _role, _Toolbox

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
START = '2026-09-14T09:32:48.524400+00:00'
BACKWARD = '2026-09-14T09:32:47.101688+00:00'
FORWARD = '2026-09-14T09:32:49.524400+00:00'
FAULT = 'terminal-publication-interrupted'


class ObservedToolbox(_Toolbox):
    def __init__(self, workspace):
        super().__init__()
        self.files = AsyncFileTools(workspace)

    async def execute(self, tool_name, args, context=None):
        assert tool_name == 'write_file'
        await self.files.write_file(args['path'], args['content'])
        return await super().execute(tool_name, args, context)


def interrupt_closeout(monkeypatch, fault):
    attempt_write = AsyncControlPlaneExecutionRepository.save_attempt_record
    run_write = AsyncControlPlaneExecutionRepository.save_run_record
    lease_write = ControlPlanePublicationService.publish_lease

    async def attempt(repository, *, record):
        if fault == 'attempt' and record.attempt_state is AttemptState.COMPLETED:
            raise RuntimeError(FAULT)
        return await attempt_write(repository, record=record)

    async def run(repository, *, record):
        if fault == 'run' and record.lifecycle_state is RunState.COMPLETED:
            raise RuntimeError(FAULT)
        return await run_write(repository, record=record)

    async def lease(publication, **kwargs):
        if fault == 'lease' and kwargs['status'] is LeaseStatus.RELEASED:
            raise RuntimeError(FAULT)
        return await lease_write(publication, **kwargs)

    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, 'save_attempt_record', attempt)
    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, 'save_run_record', run)
    monkeypatch.setattr(ControlPlanePublicationService, 'publish_lease', lease)


@pytest.mark.parametrize('protocol', [False, True], ids=['ordinary', 'protocol'])
@pytest.mark.parametrize('fault', [None, 'clock', 'attempt', 'run', 'lease'])
# Layer: integration
async def test_turn_terminal_records_and_lease_release_commit_together(tmp_path, monkeypatch, protocol, fault):
    monkeypatch.setattr(service_module, 'utc_now', lambda: START)
    monkeypatch.setattr(closeout, 'utc_now', lambda: BACKWARD if fault == 'clock' else FORWARD)
    interrupt_closeout(monkeypatch, fault)
    control = build_turn_tool_control_plane_service(tmp_path / 'control_plane.sqlite3')
    toolbox = ObservedToolbox(tmp_path)
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=tmp_path),
                            workspace=tmp_path, control_plane_service=control, utc_now=artifact_test_utc_now)
    await executor.execute_turn(_issue(), _role(), _Model(), toolbox, _context(protocol_governed_enabled=protocol))
    run_id = 'turn-tool-run:run-1:ISSUE-1:developer:0001'
    run = await control.execution_repository.get_run_record(run_id=run_id)
    attempt = await control.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    truth = await control.publication.repository.get_final_truth(run_id=run_id)
    lease = await control.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    effects = await control.publication.repository.list_effect_journal_entries(run_id=run_id)
    assert toolbox.calls == 1 and (await AsyncFileTools(tmp_path).read_file('agent_output/out.txt')) == 'ok'
    assert len(effects) == 1 and effects[0].observed_result_ref is not None
    if fault is None:
        assert truth is not None and truth.result_class.value == 'success'
        assert run.lifecycle_state is RunState.COMPLETED and attempt.attempt_state is AttemptState.COMPLETED
        assert lease.status is LeaseStatus.RELEASED
    else:
        assert truth is None and run.final_truth_record_id is None
        assert run.lifecycle_state is RunState.EXECUTING and attempt.attempt_state is AttemptState.EXECUTING
        assert attempt.end_timestamp is None and lease.status is LeaseStatus.ACTIVE


@pytest.mark.parametrize('fault', [None, 'truth', 'run', 'lease'])
# Layer: integration
async def test_preflight_closeout_records_and_release_commit_together(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(service_module, 'utc_now', lambda: START)
    control = build_turn_tool_control_plane_service(tmp_path / 'control_plane.sqlite3')
    inputs = dict(session_id='preflight', issue_id='ISSUE-1', role_name='developer',
                  turn_index=1, proposal_hash='proposal:fixture')
    run, attempt = await control.begin_execution(**inputs)
    monkeypatch.setattr(service_module, 'utc_now', lambda: FORWARD)
    truth_write = ControlPlanePublicationService.publish_final_truth
    run_write = AsyncControlPlaneExecutionRepository.save_run_record
    lease_write = ControlPlanePublicationService.publish_lease

    async def truth(publication, **kwargs):
        if fault == 'truth':
            raise RuntimeError(FAULT)
        return await truth_write(publication, **kwargs)

    async def save_run(repository, *, record):
        if fault == 'run' and record.lifecycle_state is RunState.FAILED_TERMINAL:
            raise RuntimeError(FAULT)
        return await run_write(repository, record=record)

    async def lease(publication, **kwargs):
        if fault == 'lease' and kwargs['status'] is LeaseStatus.RELEASED:
            raise RuntimeError(FAULT)
        return await lease_write(publication, **kwargs)

    monkeypatch.setattr(ControlPlanePublicationService, 'publish_final_truth', truth)
    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, 'save_run_record', save_run)
    monkeypatch.setattr(ControlPlanePublicationService, 'publish_lease', lease)
    if fault is None:
        closed, _ = await control.publish_preflight_failure(**inputs, violation_reasons=['denied'])
        assert closed.lifecycle_state is RunState.FAILED_TERMINAL
        persisted = await control.execution_repository.get_attempt_record(attempt_id=attempt.attempt_id)
        assert persisted.attempt_state is AttemptState.ABANDONED and persisted.recovery_decision_id is None
    else:
        with pytest.raises(RuntimeError, match=FAULT):
            await control.publish_preflight_failure(**inputs, violation_reasons=['denied'])
        assert await control.execution_repository.get_run_record(run_id=run.run_id) == run
        assert await control.execution_repository.get_attempt_record(attempt_id=attempt.attempt_id) == attempt
        assert await control.publication.repository.get_final_truth(run_id=run.run_id) is None
        assert await control.publication.repository.get_recovery_decision(
            decision_id=f'turn-tool-recovery:{run.run_id}:preflight:0001') is None
    retained_lease = await control.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    assert retained_lease.status is (LeaseStatus.RELEASED if fault is None else LeaseStatus.ACTIVE)


@pytest.mark.parametrize('entry', ['finalize', 'preflight'])
@pytest.mark.parametrize('damage', ['unreferenced-truth', 'unfinished-attempt', 'multiple-truths'])
# Layer: integration
async def test_turn_closeout_refuses_conflicting_terminal_history(tmp_path, monkeypatch, entry, damage):
    monkeypatch.setattr(service_module, 'utc_now', lambda: START)
    monkeypatch.setattr(closeout, 'utc_now', lambda: FORWARD)
    control = build_turn_tool_control_plane_service(tmp_path / 'control_plane.sqlite3')
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=tmp_path),
                            workspace=tmp_path, control_plane_service=control, utc_now=artifact_test_utc_now)
    await executor.execute_turn(_issue(), _role(), _Model(), ObservedToolbox(tmp_path), _context())
    run_id = 'turn-tool-run:run-1:ISSUE-1:developer:0001'
    run = await control.execution_repository.get_run_record(run_id=run_id)
    attempt = await control.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    truth = await control.publication.repository.get_final_truth(run_id=run_id)
    assert truth is not None and run.lifecycle_state is RunState.COMPLETED
    await damage_terminal_history(control.execution_repository.db_path,
        SimpleNamespace(run=run, attempt=attempt, final_truth=truth), damage)
    before = await logical_state(control.execution_repository.db_path)
    with pytest.raises(ValueError, match='CONFLICT'):
        if entry == 'finalize':
            await control.finalize_execution(run_id=run_id, attempt_id=attempt.attempt_id,
                authoritative_result_ref=truth.authoritative_result_ref, violation_reasons=[], executed_step_count=1)
        else:
            await control.publish_preflight_failure(session_id='run-1', issue_id='ISSUE-1', role_name='developer',
                turn_index=1, proposal_hash='retained-proposal', violation_reasons=['denied'])
    assert await logical_state(control.execution_repository.db_path) == before
