"""Layer: integration. A strict model fixture traverses the real engine and publication."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.adapters.llm.local_model_provider import ModelResponse
from orket.orchestration.engine import OrchestrationEngine
from orket.schema import CardStatus
from tests.integration.test_governed_guard_rejection import REJECTION
from tests.integration.test_system_acceptance_flow import _build_assets, _patch_provider
from tests.turn_prompt_utils import extract_turn_prompt_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class GovernedRejectingProvider:
    async def complete(self, messages):
        context = extract_turn_prompt_context(messages)
        guard = context['role'] in {'integrity_guard', 'verifier_seat'}
        if guard:
            calls = [{'tool': 'read_file', 'args': {'path': path}}
                     for path in context.get('required_read_paths', [])
                     if path not in context.get('missing_required_read_paths', [])]
            calls.append({'tool': 'update_issue_status', 'args': {
                'status': 'blocked', 'wait_reason': 'input', 'guard_review': REJECTION}})
        else:
            calls = [{'tool': 'write_file', 'args': {'path': 'agent_output/acceptance.txt', 'content': 'ok'}},
                     {'tool': 'write_file', 'args': {'path': 'agent_output/main.py', 'content': "print('ok')\n"}},
                     {'tool': 'update_issue_status', 'args': {'status': 'code_review'}}]
        return ModelResponse(content=json.dumps({'content': '', 'tool_calls': calls}),
                             raw={'model': 'dummy', 'total_tokens': 1})


# Layer: integration
async def test_governed_rejection_reaches_guard_events_and_published_epic_truth(tmp_path, monkeypatch, caplog):
    await asyncio.to_thread(_build_assets, tmp_path, with_guard=True, epic_id='governed_reject')
    # Leave the objective unadmitted to prove that support success cannot supply acceptance.
    epic_path = tmp_path / 'model/core/epics/governed_reject.json'
    epic = json.loads(await asyncio.to_thread(epic_path.read_text, encoding='utf-8'))
    epic['issues'][0]['params'] = {}
    await asyncio.to_thread(epic_path.write_text, json.dumps(epic), encoding='utf-8')
    _patch_provider(monkeypatch, GovernedRejectingProvider())
    monkeypatch.setenv('ORKET_PROTOCOL_GOVERNED_ENABLED', 'true')
    async with OrchestrationEngine.open(tmp_path / 'workspace', department='core',
                                 db_path=str(tmp_path / 'cards.db'), config_root=tmp_path) as engine:
        try:
            result = await engine.run_card('governed_reject')
            record = await engine.cards.get_by_id('ISSUE-A')
            assert record.status == CardStatus.BLOCKED and record.completion_ref is None
            assert not result.succeeded and result.observation == 'published'
            assert result.final_truth.result_class.value != 'success'
            events = [item.orket_record for item in caplog.records if hasattr(item, 'orket_record')]
            reviews = [item for item in events if item['event'] == 'guard_review_payload']
            assert len(reviews) == 1 and reviews[0]['data']['payload'] == REJECTION
            assert not any(item['event'] == 'guard_payload_invalid' for item in events)
            assert any(item['event'] == 'guard_rejected' for item in events)
            support = [item for item in events if item['event'] == 'runtime_verifier_completed']
            assert support and all(item['data']['ok'] for item in support)
        finally:
            await engine.close()
