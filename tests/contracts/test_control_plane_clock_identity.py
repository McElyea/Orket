"""Published identity formatting and explicit clock input contracts."""
import json
from pathlib import Path

import pytest

from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneService
from orket.application.services.extension_workload_control_plane_service import ExtensionWorkloadControlPlaneService
from orket.extensions.workload_executor_support import control_plane_identity

pytestmark = pytest.mark.contract
REFERENCE = json.loads((Path(__file__).parents[1] / 'fixtures/control_plane_identities_v053.json').read_text())


@pytest.mark.parametrize('case', REFERENCE['cases'], ids=lambda case: case['id'])
def test_selected_timestamp_retains_published_identity_format(case):
    assert CardsEpicControlPlaneService.run_id_for(**case['cards']) == case['cards_result']
    assert ExtensionWorkloadControlPlaneService.run_id_for(**case['extension']) == case['extension_result']
    inputs = dict(case['extension'])
    timestamp = inputs.pop('creation_timestamp')
    observations = []

    def selected_clock():
        observations.append(timestamp)
        return timestamp

    assert control_plane_identity(**inputs, utc_now=selected_clock) == (timestamp, case['extension_result'])
    assert observations == [timestamp]


def test_identity_clock_failure_propagates_without_fallback():
    def unavailable():
        raise ValueError('clock-unavailable')

    with pytest.raises(ValueError, match='clock-unavailable'):
        control_plane_identity(extension_id='extension', workload_id='workload', input_identity='input', utc_now=unavailable)
