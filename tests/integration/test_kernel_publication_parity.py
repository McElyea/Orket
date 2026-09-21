"""Compare actual candidate publication with independently retained published outputs."""
import json
from pathlib import Path

import pytest

from tests.helpers.kernel_publication_scenarios import observe_kernel_publication

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
CASES = json.loads((Path(__file__).parents[1] / 'fixtures/kernel_publication_v056.json').read_text(encoding='utf-8'))['cases']


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
async def test_published_kernel_publication_outcomes(tmp_path, case):
    assert await observe_kernel_publication(case, tmp_path / 'kernel.sqlite3') == case['observed']
