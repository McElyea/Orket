"""Layer: integration. Full packet-2 collection owns receipt inputs and native handles."""
import asyncio
import json
import threading
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.runtime.execution.phase_c_runtime_truth import SOURCE_ATTRIBUTION_RECEIPT_PATH, collect_phase_c_packet2_facts
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_async_file_native_lifetime import hold_native_open, observe_native_operation
from tests.integration.test_direct_metadata_inputs import hold_receipt_open

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def packet_files(workspace, operation_id):
    receipt = workspace / 'observability/run/ISSUE/001_coder/protocol_receipts.log'
    artifact = workspace / 'agent_output/result.txt'
    await asyncio.to_thread(receipt.parent.mkdir, parents=True)
    await asyncio.to_thread(artifact.parent.mkdir, parents=True)
    await asyncio.to_thread(artifact.write_text, operation_id, encoding='utf-8')
    row = {'tool': 'write_file', 'operation_id': operation_id, 'receipt_seq': 1,
           'tool_args': {'path': 'agent_output/result.txt'}, 'execution_result': {'ok': True, 'path': 'agent_output/result.txt'}}
    await asyncio.to_thread(receipt.write_text, json.dumps(row) + '\n', encoding='utf-8')
    return receipt


async def test_packet2_captures_root_policy_and_provenance_before_receipt_read(tmp_path, monkeypatch, record_property):
    original, changed = tmp_path / 'original', tmp_path / 'changed'
    target = await packet_files(original / 'workspace', 'original-write')
    await packet_files(changed / 'workspace', 'changed-write')
    monkeypatch.chdir(original)
    entered, release, finished = hold_receipt_open(monkeypatch, original, target)
    policy = {'source_attribution_mode': 'optional'}
    entry = {'artifact_path': SOURCE_ATTRIBUTION_RECEIPT_PATH, 'artifact_type': 'json', 'generator': 'fixture',
             'generator_version': '1', 'source_hash': 'sha256:fixture', 'produced_at': '2036-03-05T12:00:00Z',
             'truth_classification': 'direct', 'operation_id': 'original-provenance'}
    task = asyncio.create_task(collect_phase_c_packet2_facts(workspace=Path('workspace'), run_id='run',
        cards_repo=AsyncCardRepository(tmp_path / 'cards.sqlite3'), policy=policy, artifact_provenance_facts={'artifacts': [entry]}))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        policy['source_attribution_mode'] = 'required'
        entry['operation_id'] = 'changed-provenance'
        monkeypatch.chdir(changed)
        release.set()
        result = await asyncio.wait_for(task, 5)
        assert result['narration_to_effect_audit']['entries'][0]['operation_id'] == 'original-write'
        assert result['source_attribution']['mode'] == 'optional'
        assert result['source_attribution']['receipt_operation_id'] == 'original-provenance'
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert finished.is_set()


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_packet2_receipt_handle_is_owned_until_interrupted_return(tmp_path, monkeypatch, record_property, stop):
    target = await packet_files(tmp_path / 'workspace', 'fixture-write')
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[])
    hold_native_open(monkeypatch, target, state, failure=False)
    operation = partial(collect_phase_c_packet2_facts, workspace=tmp_path / 'workspace', run_id='run',
                        cards_repo=AsyncCardRepository(tmp_path / 'cards.sqlite3'))
    await observe_native_operation(SimpleNamespace(invoke=operation), 'invoke', [], tmp_path, state, stop, 'adapter', record_property)
