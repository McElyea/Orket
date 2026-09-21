"""Contract: compare candidate selection with independently published .54 runner outcomes."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.runtime.execution.gitea_state_loop import GiteaStateLoopRunner
from tests.helpers.gitea_loop_inputs import construction_inputs

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]
REFERENCE = json.loads((Path(__file__).parents[1] / 'fixtures/gitea_loop_limits_v054.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', REFERENCE['cases'], ids=lambda case: case['id'])
async def test_published_gitea_limit_outcomes(tmp_path, case):
    async def forbidden(_card):
        raise AssertionError('Limit selection must not dispatch a workload')

    runner = GiteaStateLoopRunner(state_backend_mode='gitea',
        organization=SimpleNamespace(process_rules=case['rules']), run_card=forbidden,
        construction_inputs=construction_inputs(tmp_path, environment=case['environment'], settings=case['settings']))
    assert await runner._resolve_limits(**case['explicit']) == case['result']
