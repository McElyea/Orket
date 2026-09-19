"""Supplied prompt evidence must not be replaced by coercion or caller mutation."""
from copy import deepcopy
from datetime import date

import pytest

from orket.core.contracts.prompt_assets import prepare_prompt_metadata

pytestmark = pytest.mark.contract


@pytest.mark.parametrize('report', [{'pass': 'false'}, {'pass': 1}, [], False])
def test_promotion_requires_explicit_true_in_a_supplied_object(report):
    payload = {'prompt_metadata': {'id': 'role.architect', 'version': '1', 'status': 'candidate'}}
    before = deepcopy(payload)
    with pytest.raises(ValueError):
        prepare_prompt_metadata(payload, prompt_id='role.architect', mode='promote', status='stable',
                                as_of=date(2000, 1, 2), promotion_report=report)
    assert payload == before


def test_metadata_transition_preserves_input_and_uses_one_supplied_date():
    payload = {'prompt_metadata': {'id': 'role.architect', 'version': '1', 'status': 'candidate',
                                  'lineage': {'parent': '0'}, 'changelog': [{'version': '1'}]}}
    before = deepcopy(payload)
    updated, result = prepare_prompt_metadata(payload, prompt_id='role.architect', mode='promote', status='stable',
                                             as_of=date(2000, 1, 2), promotion_report={'pass': True})
    assert payload == before
    metadata = updated['prompt_metadata']
    assert metadata['updated_at'] == metadata['changelog'][-1]['date'] == '2000-01-02'
    payload['prompt_metadata']['lineage']['parent'] = 'late'
    payload['prompt_metadata']['changelog'].clear()
    assert metadata['lineage']['parent'] == '0' and len(metadata['changelog']) == 2
    assert result['after'] == {'version': '1', 'status': 'stable'}
