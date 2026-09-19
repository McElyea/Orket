"""Unversioned history cannot establish that an interrupted turn is pre-effect."""
import aiosqlite
import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.governed_turn_tool_approval_continuation_service import (
    read_approval_execution,
    stop_approval_execution,
)
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.services.turn_tool_control_plane_support import digest
from orket.application.services.turn_tool_recovery_transaction import recover_pre_effect_attempt_atomic
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_executor_control_plane import write_turn_checkpoint_and_publish_if_needed
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_governed_agent_terminal_history import logical_state
from tests.integration.test_turn_executor_control_plane import _context, _issue, _Model, _role, _Toolbox
from tests.integration.test_turn_recovery_transaction import INPUTS, unfinished_turn

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures('deterministic_turn_clock')]
REFUSAL = 'dispatch contract'


async def change_declaration(control, run_id, case):
    """Deliberate retained-state controls; actual old-wheel history has separate live proof."""
    run = await control.execution_repository.get_run_record(run_id=run_id)
    snapshot = await control.publication.repository.get_resolved_configuration_snapshot(
        snapshot_id=run.configuration_snapshot_id)
    payload = dict(snapshot.configuration_payload)
    if case == 'unversioned':
        payload.pop('dispatch_contract', None)
    elif case == 'unsupported':
        payload['dispatch_contract'] = 'turn_tool.dispatch_intent.v999'
    elif case == 'payload-drift':
        payload['proposal_hash'] = 'changed-after-admission'
    changes = {'configuration_payload': payload}
    if case in {'unversioned', 'unsupported'}:
        changes['snapshot_digest'] = digest(payload)
        run = run.model_copy(update={'configuration_digest': digest(payload)})
    if case == 'binding-drift':
        changes['snapshot_digest'] = 'sha256:incorrect'
    snapshot = snapshot.model_copy(update=changes)
    async with aiosqlite.connect(control.execution_repository.db_path) as connection:
        if case == 'missing-snapshot':
            await connection.execute('DELETE FROM resolved_configuration_snapshots WHERE snapshot_id=?',
                                     (snapshot.snapshot_id,))
        else:
            await connection.execute('UPDATE resolved_configuration_snapshots SET payload_json=? WHERE snapshot_id=?',
                                     (snapshot.model_dump_json(), snapshot.snapshot_id))
        await connection.execute('UPDATE control_plane_runs SET payload_json=? WHERE run_id=?',
                                 (run.model_dump_json(), run.run_id))
        await connection.commit()
    return run, await control.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)


async def attempt_mutation(control, run, attempt, operation):
    if operation == 'begin':
        return await control.begin_execution(**INPUTS, resume_mode=True)
    if operation == 'preflight':
        return await control.publish_preflight_failure(**INPUTS, violation_reasons=['policy rejection'])
    if operation in {'prepare', 'observe'}:
        inputs = dict(run_id=run.run_id, attempt_id=attempt.attempt_id, step_id='new-step',
                      tool_name='write_file', tool_args={'path': 'out.txt', 'content': 'new'},
                      binding=None, operation_id='new-operation')
        if operation == 'prepare':
            return await control.prepare_dispatch(**inputs)
        return await control.publish_step_result(**inputs, result={'ok': True}, replayed=False)
    if operation == 'finalize':
        return await control.finalize_execution(run_id=run.run_id, attempt_id=attempt.attempt_id,
            authoritative_result_ref='claimed:success', violation_reasons=[], executed_step_count=0)
    shared = dict(transactions=control.transactions, publication=control.publication)
    if operation == 'approval-read':
        return await read_approval_execution(**shared, target=run.run_id)
    if operation == 'approval-stop':
        return await stop_approval_execution(**shared, run=run, attempt=attempt,
            authoritative_result_ref='approval:denied', violation_reasons=['denied'])
    assert operation == 'recovery'
    return await recover_pre_effect_attempt_atomic(**shared, run=run, current_attempt=attempt)


@pytest.mark.parametrize('operation', ['begin', 'preflight', 'prepare', 'observe', 'finalize',
                                      'approval-read', 'approval-stop', 'recovery'])
# Layer: integration
async def test_unversioned_turn_refuses_mutation_without_rewriting_history(tmp_path, operation):
    control, run_id = await unfinished_turn(tmp_path, observed=False)
    run, attempt = await change_declaration(control, run_id, 'unversioned')
    before = await logical_state(control.execution_repository.db_path)
    with pytest.raises(ValueError if operation not in {'approval-read', 'approval-stop'} else RuntimeError,
                       match=REFUSAL):
        await attempt_mutation(control, run, attempt, operation)
    assert await logical_state(control.execution_repository.db_path) == before


@pytest.mark.parametrize('case', ['unversioned', 'unsupported', 'payload-drift', 'binding-drift', 'missing-snapshot'])
@pytest.mark.parametrize('resume_mode', [False, True])
# Layer: integration
async def test_turn_refuses_unbound_dispatch_contract_before_model_and_tool(tmp_path, case, resume_mode):
    control, run_id = await unfinished_turn(tmp_path, observed=False)
    await change_declaration(control, run_id, case)
    before = await logical_state(control.execution_repository.db_path)
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=tmp_path),
                            workspace=tmp_path, control_plane_service=control)
    model, tool = _Model(), _Toolbox()
    result = await executor.execute_turn(_issue(), _role(), model, tool, _context(resume_mode=resume_mode))
    assert not result.success and REFUSAL in result.error
    assert model.calls == tool.calls == 0
    assert await logical_state(control.execution_repository.db_path) == before
    assert (tmp_path / 'agent_output/out.txt').read_text() == 'observed'


# Layer: integration
async def test_fresh_turn_binds_dispatch_contract_and_retains_pre_effect_recovery(tmp_path):
    control = build_turn_tool_control_plane_service(tmp_path / 'control_plane.sqlite3')
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=tmp_path),
                            workspace=tmp_path, control_plane_service=control)
    turn = ExecutionTurn(timestamp=None, role='developer', issue_id='ISSUE-1', content='', tool_calls=[
        ToolCall(tool='write_file', args={'path': 'agent_output/out.txt', 'content': 'new'})])
    await write_turn_checkpoint_and_publish_if_needed(executor=executor, turn=turn, context=_context(), prompt_hash='prompt')
    run_id = 'turn-tool-run:run-1:ISSUE-1:developer:0001'
    run = await control.execution_repository.get_run_record(run_id=run_id)
    snapshot = await control.publication.repository.get_resolved_configuration_snapshot(
        snapshot_id=run.configuration_snapshot_id)
    assert snapshot.configuration_payload['dispatch_contract'] == 'turn_tool.dispatch_intent.v1'
    assert digest(snapshot.configuration_payload) == snapshot.snapshot_digest == run.configuration_digest
    resumed, attempt = await control.begin_execution(**INPUTS, resume_mode=True)
    assert resumed.run_id == run_id and attempt.attempt_id == run.current_attempt_id
    assert attempt.attempt_state.value == 'attempt_executing'
    assert not (tmp_path / 'agent_output/out.txt').exists()


@pytest.mark.parametrize('corrupt_reference', [False, True])
# Layer: integration
async def test_completed_unversioned_turn_reads_without_repair_or_dispatch(tmp_path, corrupt_reference):
    control = build_turn_tool_control_plane_service(tmp_path / 'control_plane.sqlite3')
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=tmp_path),
                            workspace=tmp_path, control_plane_service=control)

    class PhysicalTool(_Toolbox):
        async def execute(self, tool_name, args, context=None):
            await AsyncFileTools(tmp_path).write_file(args['path'], args['content'])
            return await super().execute(tool_name, args, context)

    first = await executor.execute_turn(_issue(), _role(), _Model(), PhysicalTool(), _context())
    assert first.success and (tmp_path / 'agent_output/out.txt').read_text() == 'ok'
    run_id = 'turn-tool-run:run-1:ISSUE-1:developer:0001'
    run, _ = await change_declaration(control, run_id, 'unversioned')
    if corrupt_reference:
        await control.execution_repository.save_run_record(
            record=run.model_copy(update={'final_truth_record_id': 'wrong-truth-reference'}))
    before = await logical_state(control.execution_repository.db_path)
    model, tool = _Model(), PhysicalTool()
    result = await executor.execute_turn(_issue(), _role(), model, tool, _context(resume_mode=True))
    assert result.success is not corrupt_reference
    assert model.calls == tool.calls == 0
    assert await logical_state(control.execution_repository.db_path) == before
