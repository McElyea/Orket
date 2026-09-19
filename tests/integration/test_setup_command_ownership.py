"""Real interactive setup refuses invalid admission before creating project state."""
import asyncio
import json
import threading

import pytest

from orket.adapters.storage.setup_project_store import SetupProjectStore
from orket.application.services.setup_service import SetupService
from orket.application.services.user_settings_service import SettingsLocation
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WIZARD = ['-m', 'orket.interfaces.setup_cli']


async def test_setup_refuses_unknown_profile_before_initialization_claim(tmp_path):
    code, output, error = await child(tmp_path, WIZARD,
                                       input_text='Acme\nVision\nEthos\nworkspace\nmodel\nunknown-profile\n')
    assert code != 0, output + error
    assert 'E_MODULE_PROFILE_UNKNOWN' in error
    assert 'Initialization complete' not in output
    assert not await asyncio.to_thread((tmp_path / 'config/organization.json').exists)
    assert not await asyncio.to_thread((tmp_path / 'model').exists)


async def test_setup_healthy_control_publishes_organization_and_profile(tmp_path):
    selected_settings = tmp_path / '.orket/durable/config/user_settings.json'
    await asyncio.to_thread(selected_settings.parent.mkdir, parents=True)
    await asyncio.to_thread(selected_settings.write_text, json.dumps({'unrelated': {'keep': 1},
                                                                     'module_profile': 'api-runtime'}), encoding='utf-8')
    code, output, error = await child(tmp_path, WIZARD,
                                       input_text='Acme\nVision\nEthos\nworkspace\nmodel\ndeveloper-local\n')
    assert code == 0 and 'Initialization complete' in output, output + error
    config = json.loads(await asyncio.to_thread((tmp_path / 'config/organization.json').read_text, encoding='utf-8'))
    settings = json.loads(await asyncio.to_thread((tmp_path / '.orket/durable/config/user_settings.json').read_text,
                                                 encoding='utf-8'))
    assert config['name'] == 'Acme' and settings['module_profile'] == 'developer-local'
    assert settings['unrelated'] == {'keep': 1}


async def test_setup_reports_partial_failure_after_organization_before_settings(tmp_path):
    preferences = tmp_path / '.orket/durable/config/preferences.json'
    await asyncio.to_thread(preferences.parent.mkdir, parents=True)
    await asyncio.to_thread(preferences.write_text, 'malformed preferences', encoding='utf-8')
    code, output, error = await child(tmp_path, WIZARD,
                                    input_text='Acme\nVision\nEthos\nworkspace\nmodel\ndeveloper-local\n')
    assert code != 0 and 'Initialization failed' in error, output + error
    assert 'Initialization complete' not in output
    config = json.loads(await asyncio.to_thread((tmp_path / 'config/organization.json').read_bytes))
    assert config['name'] == 'Acme'
    assert not await asyncio.to_thread((preferences.parent / 'user_settings.json').exists)


async def test_setup_write_refusal_returns_failure_without_completion_claim(tmp_path):
    await asyncio.to_thread((tmp_path / 'workspace').write_text, 'occupied', encoding='utf-8')
    code, output, error = await child(tmp_path, WIZARD,
                                    input_text='Acme\nVision\nEthos\nworkspace\nmodel\ndeveloper-local\n')
    assert code != 0 and 'Initialization failed' in error, output + error
    assert 'Initialization complete' not in output
    assert not await asyncio.to_thread((tmp_path / 'config/organization.json').exists)


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_setup_retains_captured_inputs_and_owner_until_worker_finishes(tmp_path, monkeypatch, stop):
    entered, release = threading.Event(), threading.Event()
    original = SetupProjectStore.publish

    def held(store, *args, **kwargs):
        entered.set()
        assert release.wait(15)
        return original(store, *args, **kwargs)

    monkeypatch.setattr(SetupProjectStore, 'publish', held)
    choices = dict(name='Captured', vision='Vision', ethos='Ethos', workspace='workspace', model='model',
                   module_profile='developer-local')
    service = SetupService(tmp_path, SettingsLocation(tmp_path, '.orket/durable'))
    command = service.initialize(choices)
    request = asyncio.create_task(asyncio.wait_for(command, 0.05) if stop == 'timeout' else command)
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        responsiveness_start = asyncio.get_running_loop().time()
        await asyncio.sleep(0.01)
        assert asyncio.get_running_loop().time() - responsiveness_start < 0.5
        choices.update(name='Late', module_profile='engine-only', workspace='late')
        if stop == 'cancel':
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        code, output, error = await child(tmp_path, WIZARD,
                                        input_text='Other\nVision\nEthos\nworkspace\nmodel\nengine-only\n')
        assert code != 0 and 'E_SETUP_UNCERTAIN:owner_busy' in error, output + error
        assert 'Initialization complete' not in output and not request.done()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert isinstance(result, asyncio.CancelledError if stop == 'cancel' else TimeoutError)
        config = json.loads(await asyncio.to_thread((tmp_path / 'config/organization.json').read_bytes))
        settings = json.loads(await asyncio.to_thread((tmp_path / '.orket/durable/config/user_settings.json').read_bytes))
        assert config['name'] == 'Captured' and settings['module_profile'] == 'developer-local'
        assert not await asyncio.to_thread((tmp_path / 'late').exists)
        assert (await service.initialize({**choices, 'name': 'Retry'}))['module_profile'] == 'engine-only'
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)


async def test_setup_org_readback_failure_prevents_profile_update(tmp_path, monkeypatch):
    target = tmp_path / 'config/organization.json'
    original = type(target).read_bytes

    def wrong_readback(path):
        return b'wrong readback' if path == target else original(path)

    monkeypatch.setattr(type(target), 'read_bytes', wrong_readback)
    with pytest.raises(OSError, match='E_SETUP_ORGANIZATION_UNVERIFIED'):
        await SetupService(tmp_path, SettingsLocation(tmp_path, '.orket/durable')).initialize(
            dict(name='Acme', vision='Vision', ethos='Ethos', workspace='workspace', model='model',
                 module_profile='developer-local'))
    assert json.loads(await asyncio.to_thread(original, target))['name'] == 'Acme'
    assert not await asyncio.to_thread((tmp_path / '.orket/durable/config/user_settings.json').exists)
