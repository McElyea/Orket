"""Actual turn dispatch must not retry an admitted async asset operation on TypeError."""
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.decision_nodes.builtins import DefaultRouterNode
from orket.schema import CardStatus, EnvironmentConfig
from tests.integration.test_dispatch_input_admission import _dispatch_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_turn_asset_type_error_preserves_single_invocation(tmp_path):
    files = AsyncFileTools(tmp_path)
    await files.write_file('role.json', '{"name":"coder"}')
    repo, issue, team, orchestrator = await _dispatch_context(tmp_path, DefaultRouterNode())
    calls = []

    class Loader:
        async def load_asset_async(self, category, name, model_type):
            assert (category, name) == ('roles', 'coder')
            assert await files.read_file('role.json') == '{"name":"coder"}'
            calls.append('async')
            await files.write_file('observed.txt', 'async operation admitted')
            raise TypeError('admitted async asset failure')

        def load_asset(self, category, name, model_type):
            calls.append('sync')
            raise RuntimeError('duplicate asset invocation')

    orchestrator.loader = Loader()
    with pytest.raises(TypeError, match='admitted async asset failure'):
        await orchestrator._execute_issue_turn(issue, SimpleNamespace(params={}), team,
            EnvironmentConfig(name='test', model='fixture'), 'run', 'build', None, None, None)
    assert calls == ['async']
    assert await files.read_file('observed.txt') == 'async operation admitted'
    assert (await repo.get_by_id(issue.id)).status == CardStatus.IN_PROGRESS
