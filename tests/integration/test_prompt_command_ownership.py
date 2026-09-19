"""Actual prompt commands must bind their asset scope, time and publication."""
import asyncio
import json
import threading

import pytest

from orket.adapters.storage.prompt_asset_store import PromptAssetStore
from orket.application.services.prompt_asset_service import PromptAssetService
from tests.application.test_prompts_cli import _seed_assets
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_prompt_id_cannot_write_outside_its_asset_directory(tmp_path):
    await asyncio.to_thread(_seed_assets, tmp_path)
    outside = tmp_path / 'outside.json'
    original = '{"prompt_metadata":{"version":"1","status":"candidate"}}'
    await asyncio.to_thread(outside.write_text, original, encoding='utf-8')
    code, output, error = await child(tmp_path, [
        '-m', 'orket.interfaces.prompts_cli', '--root', str(tmp_path),
        'deprecate', '--id', 'role.../../../outside', '--apply',
    ])
    assert code != 0, output + error
    assert 'E_PROMPT_ASSET_NAME' in error
    assert await asyncio.to_thread(outside.read_text, encoding='utf-8') == original


async def test_prompt_sla_uses_supplied_date_for_the_published_renewal(tmp_path):
    await asyncio.to_thread(_seed_assets, tmp_path)
    target = tmp_path / 'model/core/roles/architect.json'
    payload = json.loads(await asyncio.to_thread(target.read_text, encoding='utf-8'))
    payload['prompt_metadata'].update(status='candidate', updated_at='2019-01-01')
    await asyncio.to_thread(target.write_text, json.dumps(payload), encoding='utf-8')
    code, output, error = await child(tmp_path, [
        '-m', 'orket.interfaces.prompts_cli', '--root', str(tmp_path),
        'enforce-sla', '--as-of', '2020-02-03', '--renew', 'role.architect', '--apply',
    ])
    assert code == 0, output + error
    assert json.loads(output)['renew_count'] == 1
    observed = json.loads(await asyncio.to_thread(target.read_text, encoding='utf-8'))['prompt_metadata']
    assert observed['updated_at'] == observed['changelog'][-1]['date'] == '2020-02-03'


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_prompt_worker_retains_native_owner_through_interruption(tmp_path, monkeypatch, stop):
    await asyncio.to_thread(_seed_assets, tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = PromptAssetStore.write

    def held(store, path, payload):
        entered.set()
        assert release.wait(15)
        original(store, path, payload)

    monkeypatch.setattr(PromptAssetStore, 'write', held)
    service = PromptAssetService(tmp_path)
    command = service.execute('update', prompt_id='role.architect', mode='deprecate', apply_changes=True)
    request = asyncio.create_task(asyncio.wait_for(command, 0.05) if stop == 'timeout' else command)
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        responsiveness_start = asyncio.get_running_loop().time()
        await asyncio.sleep(0.01)
        assert asyncio.get_running_loop().time() - responsiveness_start < 0.5
        if stop == 'cancel':
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        code, output, error = await child(tmp_path, ['-m', 'orket.interfaces.prompts_cli', '--root', str(tmp_path),
                                                    'deprecate', '--id', 'role.architect', '--apply'])
        assert code != 0 and 'DRIVER_RESOURCE_UNCERTAIN:owner_busy' in error, output + error
        assert not request.done()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert isinstance(result, asyncio.CancelledError if stop == 'cancel' else TimeoutError)
        observed = await service.execute('show', prompt_id='role.architect')
        assert observed['payload']['prompt_metadata']['status'] == 'deprecated'
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)


async def test_prompt_captures_report_before_worker_and_refuses_late_authority(tmp_path, monkeypatch):
    await asyncio.to_thread(_seed_assets, tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = PromptAssetStore.__init__

    def held(store, root):
        entered.set()
        assert release.wait(10)
        original(store, root)

    monkeypatch.setattr(PromptAssetStore, '__init__', held)
    report = {'pass': False, 'blockers': [{'code': 'original-refusal'}]}
    request = asyncio.create_task(PromptAssetService(tmp_path).execute('update', prompt_id='role.architect',
        mode='promote', status='stable', promotion_report=report, apply_changes=True))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        responsiveness_start = asyncio.get_running_loop().time()
        await asyncio.sleep(0.01)
        assert asyncio.get_running_loop().time() - responsiveness_start < 0.5
        report.update({'pass': True, 'blockers': []})
        release.set()
        with pytest.raises(ValueError, match='original-refusal'):
            await asyncio.wait_for(request, 3)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)


async def test_prompt_readback_failure_is_not_success(tmp_path, monkeypatch):
    await asyncio.to_thread(_seed_assets, tmp_path)
    target = tmp_path / 'model/core/roles/architect.json'
    original = type(target).read_bytes

    def corrupt_after_publish(path):
        raw = original(path)
        if path == target and json.loads(raw)['prompt_metadata']['status'] == 'deprecated':
            return b'corrupt readback'
        return raw

    monkeypatch.setattr(type(target), 'read_bytes', corrupt_after_publish)
    with pytest.raises(OSError, match='E_FILE_WRITE_UNVERIFIED'):
        await PromptAssetService(tmp_path).execute('update', prompt_id='role.architect',
                                                 mode='deprecate', apply_changes=True)
    # Replacement happened; a failed acknowledgement does not imply rollback.
    assert json.loads(await asyncio.to_thread(original, target))['prompt_metadata']['status'] == 'deprecated'


async def test_sla_rejects_filename_identity_drift_before_any_updates(tmp_path):
    await asyncio.to_thread(_seed_assets, tmp_path)
    target = tmp_path / 'model/core/roles/architect.json'
    payload = json.loads(await asyncio.to_thread(target.read_bytes))
    payload['prompt_metadata'].update(id='dialect.generic', status='candidate', updated_at='2000-01-01')
    await asyncio.to_thread(target.write_text, json.dumps(payload), encoding='utf-8')
    other = tmp_path / 'model/core/dialects/generic.json'
    before = await asyncio.to_thread(other.read_bytes)
    with pytest.raises(ValueError, match='E_PROMPT_METADATA_ID_MISMATCH'):
        await PromptAssetService(tmp_path).execute('enforce_sla', as_of='2020-02-03', apply_changes=True)
    assert await asyncio.to_thread(other.read_bytes) == before
