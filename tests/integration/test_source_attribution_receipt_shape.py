"""Layer: integration. Real receipt files cannot verify synthesis without evidence."""
import asyncio
import json

import pytest

from orket.runtime.execution.phase_c_runtime_truth import (
    SOURCE_ATTRIBUTION_RECEIPT_PATH,
    collect_source_attribution_facts,
    resolve_source_attribution_gate_failure_reason,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
VALID = {'claims': [{'claim_id': 'c1', 'claim': 'supported', 'source_ids': ['s1']}],
         'sources': [{'source_id': 's1', 'title': 'source', 'uri': 'fixture:source', 'kind': 'fixture'}]}


@pytest.mark.parametrize('payload', [None, [], 42, 'text', {}, VALID], ids=['null', 'list', 'number', 'string', 'empty-object', 'valid'])
async def test_receipt_requires_claim_and_source_evidence(tmp_path, payload):
    target = tmp_path / SOURCE_ATTRIBUTION_RECEIPT_PATH
    await asyncio.to_thread(target.parent.mkdir, parents=True)
    await asyncio.to_thread(target.write_text, json.dumps(payload), encoding='utf-8')
    result = await collect_source_attribution_facts(workspace=tmp_path, policy={'source_attribution_mode': 'required'})
    if payload == VALID:
        assert result['synthesis_status'] == 'verified'
        assert result['claim_count'] == result['source_count'] == 1
        assert resolve_source_attribution_gate_failure_reason(result) is None
    else:
        assert result['synthesis_status'] == 'blocked'
        assert result['missing_requirements']
        assert resolve_source_attribution_gate_failure_reason(result) in result['missing_requirements']
