"""Layer: integration. Real acceptance evidence must govern both prompt representations."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.application.services.card_completion_turn_service import prepare_card_completion_turn
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.helpers.card_completion import completion_components, completion_definition, write_completion_source

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("case", ["no_plan", "empty", "syntax_only", "wrong_behavior", "accepted"])
# Layer: integration
async def test_guard_prompt_uses_retained_acceptance_instead_of_legacy_success(tmp_path, compact, case):
    workspace = tmp_path / 'workspace'
    await asyncio.to_thread(workspace.mkdir)
    repo, service = completion_components(tmp_path / 'cards.db', workspace)
    sources = {'syntax_only': 'answer = 42\n', 'wrong_behavior': "print('{}')\n"}
    if case != 'empty':
        if case in sources:
            await write_completion_source(workspace, sources[case])
        else:
            await write_completion_source(workspace)
    params = {} if case == 'no_plan' else {'completion_acceptance': completion_definition().model_dump(mode='json')}
    record = IssueRecord(id='card', summary='Increment integers', seat='integrity_guard',
                         status=CardStatus.CODE_REVIEW, params=params)
    await repo.save(record)
    legacy = await RuntimeVerifier(workspace).verify()
    assert legacy.ok
    context = {'issue_id': record.id, 'role': 'integrity_guard', 'current_status': 'code_review',
               'stage_gate_mode': 'review_required', 'required_action_tools': ['update_issue_status'],
               'required_statuses': ['done', 'blocked'], 'runtime_verifier_ok': legacy.ok,
               'compact_turn_packet_enabled': compact}
    declared = await prepare_card_completion_turn(service=service, cards=repo, context=context, card_id=record.id,
                                                  session_id='session', seat_name='integrity_guard', turn_index=1)
    role = RoleConfig(id='guard', summary='integrity_guard', description='Review declared acceptance',
                      tools=['update_issue_status'])
    messages = await MessageBuilder(workspace).prepare_messages(
        issue=IssueConfig.model_validate(record.model_dump()), role=role, context=context,
        system_prompt='Review the current acceptance evidence.' + declared)
    rendered = '\n\n'.join(message['content'] for message in messages)
    assert 'If runtime verifier passed and no concrete defect is present, choose status=done' not in rendered
    decision = context['card_completion_decision']
    payload = json.JSONDecoder().raw_decode(rendered.split('Declared card acceptance:\n', 1)[1])[0]
    assert payload['state'] == decision.state.value
    assert payload['policy_ref'] == decision.policy_ref and payload['plan_digest'] == decision.plan_digest
    assert payload['evidence_refs'] == list(decision.evidence_refs)
    assert 'Support checks alone cannot authorize successful completion' in rendered
    assert 'second JSON object' not in rendered
    assert "put guard_review inside that call's args" in rendered
    assert (payload['state'] == 'acceptance_satisfied') is (case == 'accepted')
    if case != 'accepted':
        assert decision.diagnostics or decision.missing_criteria
        assert 'choose blocked when it is an allowed status' in rendered
    assert (await repo.get_by_id(record.id)).status == CardStatus.CODE_REVIEW
