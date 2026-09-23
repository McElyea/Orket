"""Layer: integration. Each packet-2 borrowed input is fixed before receipt observation."""
import asyncio
from pathlib import Path

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.runtime.execution.phase_c_runtime_truth import SOURCE_ATTRIBUTION_RECEIPT_PATH, collect_phase_c_packet2_facts
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_direct_metadata_inputs import hold_receipt_open
from tests.integration.test_packet2_capture_lifetime import packet_files

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('field', ['root', 'policy', 'provenance'])
@pytest.mark.parametrize('mutate', [False, True], ids=['unchanged', 'caller-mutation'])
async def test_packet2_retains_each_input_independently(tmp_path, monkeypatch, record_property, field, mutate):
    original, changed = tmp_path / 'original', tmp_path / 'changed'
    target = await packet_files(original / 'workspace', 'original-write')
    await packet_files(changed / 'workspace', 'changed-write')
    monkeypatch.chdir(original)
    entered, release, finished = hold_receipt_open(monkeypatch, original, target)
    policy = {'source_attribution_mode': 'optional'}
    entry = {'artifact_path': SOURCE_ATTRIBUTION_RECEIPT_PATH, 'artifact_type': 'json', 'generator': 'fixture',
             'generator_version': '1', 'source_hash': 'sha256:fixture', 'produced_at': '2036-03-05T12:00:00Z',
             'truth_classification': 'direct', 'operation_id': 'original-provenance',
             'control_plane_run_id': 'original-run', 'control_plane_step_id': 'original-step'}
    provenance = {'artifacts': [entry]}
    task = asyncio.create_task(collect_phase_c_packet2_facts(workspace=Path('workspace'), run_id='run',
        cards_repo=AsyncCardRepository(tmp_path / 'cards.sqlite3'), policy=policy, artifact_provenance_facts=provenance))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        if mutate and field == 'root':
            monkeypatch.chdir(changed)
        elif mutate and field == 'policy':
            policy.update(source_attribution_mode='required', high_stakes=True)
        elif mutate:
            entry.update(operation_id='changed-provenance', control_plane_run_id='changed-run')
            provenance['artifacts'].clear()
        release.set()
        result = await asyncio.wait_for(task, 5)
        attribution = result['source_attribution']
        assert result['narration_to_effect_audit']['entries'][0]['operation_id'] == 'original-write'
        assert attribution['mode'] == 'optional' and attribution['high_stakes'] is False
        assert attribution['synthesis_status'] == 'optional_unverified'
        assert attribution['receipt_operation_id'] == 'original-provenance'
        assert attribution['control_plane_run_id'] == 'original-run'
        assert attribution['control_plane_step_id'] == 'original-step'
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert finished.is_set()
