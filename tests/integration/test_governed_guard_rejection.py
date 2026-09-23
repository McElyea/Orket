"""Layer: integration. Governed rejection carries diagnostics through real final storage."""
from __future__ import annotations

import json

import pytest

from orket.application.services.card_completion_turn_service import prepare_card_completion_turn
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.toolbox import ToolBox
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.records import IssueRecord
from orket.core.domain.state_machine import StateMachine
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.helpers.card_completion import completion_components
from tests.helpers.turn_artifacts import artifact_test_utc_now

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
REJECTION = {'rationale': 'Declared acceptance is missing.', 'violations': ['No acceptance plan'],
             'remediation_actions': ['Admit objective-specific acceptance before completion.']}


class GuardModel:
    def __init__(self, case='valid'):
        self.case = case

    async def complete(self, messages):
        payload = {**REJECTION}
        if self.case in {'rationale', 'violations', 'remediation_actions'}:
            payload[self.case] = '' if self.case == 'rationale' else []
        elif self.case == 'wrong_type':
            payload['violations'] = 'A string is not a list of concrete violations'
        args = {'status': 'blocked', 'wait_reason': 'input', 'guard_review': payload}
        if self.case == 'missing':
            args.pop('guard_review')
        elif self.case == 'null':
            args['guard_review'] = None
        calls = [{'tool': 'update_issue_status', 'args': args}]
        if self.case == 'duplicate':
            calls.append({'tool': 'update_issue_status', 'args': {**args, 'guard_review': {}}})
        return {'content': json.dumps({'content': '', 'tool_calls': calls}), 'raw': {'total_tokens': 1}}


# Layer: integration
@pytest.mark.parametrize('case', ['valid', 'missing', 'null', 'rationale', 'violations',
                                  'remediation_actions', 'wrong_type', 'duplicate'])
async def test_governed_guard_rejection_persists_blocked_with_no_completion_receipt(tmp_path, case):
    workspace = tmp_path / 'workspace'
    repo, service = completion_components(tmp_path / 'cards.db', workspace)
    record = IssueRecord(id='card', summary='An unadmitted objective', seat='integrity_guard',
                         session_id='session', status=CardStatus.AWAITING_GUARD_REVIEW)
    await repo.save(record)
    context = {'session_id': 'session', 'issue_id': record.id, 'turn_index': 1,
               'current_status': 'awaiting_guard_review', 'role': 'integrity_guard', 'roles': ['integrity_guard'],
               'required_action_tools': ['update_issue_status'], 'required_statuses': ['done', 'blocked'],
               'stage_gate_mode': 'review_required', 'protocol_governed_enabled': True,
               'runtime_verifier_ok': True}
    system_prompt = await prepare_card_completion_turn(service=service, cards=repo, context=context,
                                                       card_id=record.id, session_id='session',
                                                       seat_name='integrity_guard', turn_index=1)
    gate = ToolGate(organization=None, workspace_root=workspace)
    toolbox = ToolBox(None, str(workspace), [], db_path=repo.db_path, cards_repo=repo, tool_gate=gate)
    role = RoleConfig(id='guard', summary='integrity_guard', description='Review acceptance', tools=['update_issue_status'])
    result = await TurnExecutor(StateMachine(), gate, workspace, utc_now=artifact_test_utc_now).execute_turn(
        IssueConfig.model_validate(record.model_dump()), role, GuardModel(case), toolbox, context, system_prompt=system_prompt)
    stored = await repo.get_by_id(record.id)
    if case == 'valid':
        assert result.success, result.error
        assert result.turn.content == ''
        assert result.turn.tool_calls[0].args['guard_review'] == REJECTION
        assert stored.status == CardStatus.BLOCKED
    else:
        assert not result.success and 'guard rejection payload contract' in result.error
        assert stored.status == CardStatus.AWAITING_GUARD_REVIEW
        assert await repo.get_card_history(record.id) == []
    assert stored.completion_ref is None
    assert await repo.read_completion_receipt(record.id) is None
