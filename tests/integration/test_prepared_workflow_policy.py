"""Layer: integration. Prepared inputs must match actual canonical config admission."""
import json

import pytest

from examples.stored_workflows.prepare import prepare
from orket.runtime.config.config_loader import ConfigLoader

pytestmark = pytest.mark.integration


def test_preparation_updates_loaded_modular_policy_and_captures_real_organization(tmp_path):
    project = tmp_path / "isolated"
    prepare(project, "sanity_test", "selected-model")
    loaded = ConfigLoader(project).load_organization()
    assert loaded.process_rules["disable_runtime_verifier"] is True
    seed = json.loads((project / "workspace/agent_output/organization.json").read_text())
    assert seed == {"name": loaded.name}
    epic = json.loads((project / "model/core/epics/sanity_test.json").read_text())
    expected = epic["issues"][0]["params"]["completion_acceptance"]["cases"][0]["expected_text"]
    assert f"Organization: {loaded.name}" in expected
    assert epic["issues"][0]["params"]["turn_contract"]["required_write_paths"] == ["agent_output/sanity_receipt.md"]
