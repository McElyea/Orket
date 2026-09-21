"""Public runtime construction accepts bound settings with independently persisted preferences."""
import asyncio
import json

import pytest

import orket.runtime.execution.execution_pipeline as pipeline_module
from orket.settings import set_preferences_file, set_runtime_settings_context
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.integration.test_epic_completion_publication import accept_publication_card

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('preferences', ['bound', 'persisted'])
async def test_public_runtime_preserves_independent_preference_bootstrap(
    test_root, workspace, db_path, monkeypatch, preferences,
):
    await asyncio.to_thread(_write_epic_assets, test_root, 'publication_epic')
    preference_path = test_root / 'selected-preferences.json'
    await asyncio.to_thread(preference_path.write_text, json.dumps({'theme': 'selected'}), encoding='utf-8')
    set_preferences_file(preference_path)
    set_runtime_settings_context(user_settings={}, user_preferences={'theme': 'selected'} if preferences == 'bound' else None)
    factory, owners = pipeline_module.ExecutionPipeline, []

    def construct(*args, **kwargs):
        kwargs.update(config_root=test_root, db_path=db_path)
        owner = factory(*args, **kwargs)
        owners.append(owner)

        async def workload(**_kwargs):
            await accept_publication_card(owner, owner.workspace)

        owner.orchestrator.execute_epic = workload
        return owner

    monkeypatch.setattr(pipeline_module, 'ExecutionPipeline', construct)
    try:
        result = await pipeline_module.orchestrate_card('publication_epic', workspace,
            session_id='preference-context', build_id='preference-build')
        assert result.succeeded and len(owners) == 1 and owners[0]._closed
    finally:
        for owner in owners:
            await owner.close()
