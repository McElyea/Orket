"""Contract: artifact review must not acquire an unrelated app design input."""
from types import SimpleNamespace

import pytest

from orket.core.cards_runtime_contract import required_read_paths_for_seat

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("seat", ["code_reviewer", "reviewer"])
def test_artifact_final_review_uses_its_declared_inputs(seat):
    paths = ["agent_output/requirements.txt", "agent_output/main.py"]
    issue = SimpleNamespace(seat=seat, params={"cards_runtime": {
        "execution_profile": "write_artifact_v1",
        "artifact_contract": {"kind": "artifact", "primary_output": paths[-1], "review_read_paths": paths},
    }})
    assert required_read_paths_for_seat(seat_name="integrity_guard", issue=issue) == paths


def test_default_application_final_review_retains_design_and_verification():
    issue = SimpleNamespace(seat="code_reviewer", params={})
    assert required_read_paths_for_seat(seat_name="integrity_guard", issue=issue) == [
        "agent_output/requirements.txt", "agent_output/design.txt", "agent_output/main.py",
        "agent_output/verification/runtime_verification.json",
    ]
