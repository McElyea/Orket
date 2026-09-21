"""Real authored priorities remain ordered after schema normalization."""
import asyncio
import json

import pytest

from orket.organization_loop import OrganizationLoop
from tests.integration.test_organization_loop_ownership import seed_organization

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def seed_priorities(root, numeric):
    seed_organization(root)
    source = root / 'model/core/epics/publication_epic.json'
    low = source.with_name('a_low.json')
    source.rename(low)
    raw = low.read_bytes()
    for name, identifier, priority in [('a_low', 'LOW', 1.0 if numeric else 'Low'),
                                        ('z_high', 'HIGH', 3.0 if numeric else 'High')]:
        value = json.loads(raw)
        value['id'] = value['name'] = name
        value['issues'][0].update(id=identifier, priority=priority)
        low.with_name(name + '.json').write_text(json.dumps(value), encoding='utf-8')


@pytest.mark.parametrize('numeric', [False, True])
async def test_organization_orders_normalized_priorities(test_root, monkeypatch, numeric):
    await asyncio.to_thread(seed_priorities, test_root, numeric)
    monkeypatch.chdir(test_root)
    owner = await OrganizationLoop.create()
    observed = await asyncio.to_thread(owner._find_next_critical_card)
    assert observed == {'id': 'HIGH', 'weight': 1, 'priority': '3.0', 'dept': 'core'}
