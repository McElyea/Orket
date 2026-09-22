"""Actual HTTP-client ownership with controlled settings and an empty ready queue."""
import pytest

import orket.runtime.execution.gitea_state_loop as loop_module

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('observation', ['transport_close', 'environment_capture'])
async def test_empty_loop_captures_limits_and_closes_actual_transport(tmp_path, monkeypatch, observation):
    monkeypatch.chdir(tmp_path)
    for key, value in {
        'ORKET_STATE_BACKEND_MODE': 'gitea', 'ORKET_ENABLE_GITEA_STATE_PILOT': '1',
        'ORKET_GITEA_URL': 'http://127.0.0.1:1', 'ORKET_GITEA_TOKEN': 'unused-controlled-token',
        'ORKET_GITEA_OWNER': 'clock-owner', 'ORKET_GITEA_REPO': 'clock-repo',
        'ORKET_GITEA_WORKER_MAX_ITERATIONS': '2', 'ORKET_DURABLE_ROOT': str(tmp_path / 'durable'),
    }.items():
        monkeypatch.setenv(key, value)
    created = []
    fetches = []
    adapter_type = loop_module.GiteaStateAdapter
    adapter_factory = loop_module.create_gitea_state_adapter

    def capture_adapter(**values):
        adapter = adapter_factory(**values)
        created.append(adapter)
        return adapter

    async def observed_settings():
        if observation == 'environment_capture':
            monkeypatch.setenv('ORKET_GITEA_WORKER_MAX_ITERATIONS', '99')
        return {}

    async def forbidden_work(_card):
        raise AssertionError('An empty ready queue must not start remote work')

    async def empty_queue(_adapter, *, limit):
        fetches.append(limit)
        return []

    monkeypatch.setattr(loop_module, 'create_gitea_state_adapter', capture_adapter)
    monkeypatch.setattr(adapter_type, 'fetch_ready_cards', empty_queue)
    monkeypatch.setattr(loop_module, 'load_user_settings_async', observed_settings)
    try:
        result = await loop_module.run_gitea_state_loop(state_backend_mode='gitea', organization=None,
            run_card=forbidden_work, worker_id='clock-worker', max_duration_seconds=30, max_idle_streak=1)
        assert result['summary']['iterations'] == 1 and len(created) == 1 and fetches == [5]
        if observation == 'transport_close':
            assert created[0].http._client.is_closed
        else:
            assert result['max_iterations'] == 2
    finally:
        for adapter in created:
            await adapter.close()
