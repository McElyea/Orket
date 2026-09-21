"""Runtime input collection retains independent snapshots and real settings locations."""
from __future__ import annotations

import asyncio
import json

import pytest

import orket.settings as settings
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('settings_bound,preferences_bound', [(False, False), (False, True), (True, False), (True, True)])
async def test_runtime_settings_capture_keeps_selected_sources(tmp_path, monkeypatch, settings_bound, preferences_bound):
    first, second, rotated = tmp_path / 'settings.json', tmp_path / 'preferences.json', tmp_path / 'rotated'
    await asyncio.to_thread(first.write_text, json.dumps({'selection': {'value': 'disk'}}), encoding='utf-8')
    await asyncio.to_thread(second.write_text, json.dumps({'theme': 'disk'}), encoding='utf-8')
    await asyncio.to_thread(rotated.mkdir)
    settings.set_settings_file(first)
    settings.set_preferences_file(second)
    supplied = {'selection': {'value': 'bound'}}
    settings.set_runtime_settings_context(user_settings=supplied if settings_bound else None,
        user_preferences={'theme': 'bound'} if preferences_bound else None)
    monkeypatch.chdir(tmp_path)
    environment = {'SETTING_CAPTURE': 'original'}
    entered, release = asyncio.Event(), asyncio.Event()
    worker = settings.run_owned_thread

    async def held_worker(operation, *, label):
        entered.set()
        await release.wait()
        return await worker(operation, label=label)

    monkeypatch.setattr(settings, 'run_owned_thread', held_worker)
    task = asyncio.create_task(RuntimeConstructionInputs.capture_async(environment=environment))
    try:
        if settings_bound and preferences_bound:
            captured = await asyncio.wait_for(task, 5)
            assert not entered.is_set()
        else:
            await asyncio.wait_for(entered.wait(), 5)
        supplied['selection']['value'] = 'caller mutation'
        environment['SETTING_CAPTURE'] = 'rotated'
        monkeypatch.chdir(rotated)
        settings.set_settings_file(rotated / 'settings.json')
        settings.set_preferences_file(rotated / 'preferences.json')
        settings.set_runtime_settings_context(user_settings={'selection': {'value': 'rotated'}},
            user_preferences={'theme': 'rotated'})
        release.set()
        captured = await asyncio.wait_for(task, 5)
        assert captured.invocation_root == tmp_path and dict(captured.environment) == {'SETTING_CAPTURE': 'original'}
        expected = 'bound' if settings_bound else 'disk'
        assert captured.user_settings() == {'selection': {'value': expected}}
        assert captured.user_preferences()['theme'] == ('bound' if preferences_bound else 'disk')
        exported = captured.user_settings()
        exported['selection']['value'] = 'consumer mutation'
        assert captured.user_settings()['selection']['value'] == expected
        assert await asyncio.to_thread(lambda: list(rotated.iterdir())) == []
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize('document', ['settings', 'preferences'])
async def test_runtime_settings_capture_refuses_malformed_selected_files(tmp_path, document):
    first, second = tmp_path / 'settings.json', tmp_path / 'preferences.json'
    await asyncio.to_thread(first.write_text, '{broken' if document == 'settings' else '{}', encoding='utf-8')
    await asyncio.to_thread(second.write_text, '{broken' if document == 'preferences' else '{}', encoding='utf-8')
    settings.set_settings_file(first)
    settings.set_preferences_file(second)
    with pytest.raises(ValueError):
        await RuntimeConstructionInputs.capture_async(environment={})
    selected = first if document == 'settings' else second
    assert await asyncio.to_thread(selected.read_text, encoding='utf-8') == '{broken'
