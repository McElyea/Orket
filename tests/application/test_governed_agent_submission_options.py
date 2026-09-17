"""Submission options capture caller-owned collections before execution."""
from dataclasses import FrozenInstanceError

import pytest

from orket.application.services.governed_agent_submission_service import GovernedAgentProviderOptions

pytestmark = pytest.mark.unit


# Layer: unit
def test_provider_options_capture_nested_role_pairs():
    roles = [["planner", "first"]]
    options = GovernedAgentProviderOptions(role_models=roles)
    roles[0][1] = "changed"
    assert options.role_models == (("planner", "first"),)
    with pytest.raises(FrozenInstanceError):
        options.model = "changed"
