"""Immutable sandbox facts and default-output parity against the published .48 core."""
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from orket.application.services.sandbox_policy_input_service import capture_sandbox_compose, render_sandbox_compose
from orket.core.domain.sandbox import Sandbox
from orket.decision_nodes.builtins import DefaultSandboxPolicyNode

pytestmark = pytest.mark.contract


@pytest.fixture(scope="module")
def reference():
    return json.loads((Path(__file__).parents[1]/"fixtures/sandbox_policy_v048.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", range(10))
def test_default_outputs_match_published_installed_core(reference, case):
    row = reference["cases"][case]
    sandbox = Sandbox.model_validate(row["sandbox"])
    inputs = capture_sandbox_compose(sandbox)
    node = DefaultSandboxPolicyNode()
    tokens = reference["tokens"]
    calls = {"database": lambda: node.get_database_url(inputs.tech_stack, inputs.ports, tokens["database"]),
             "compose": lambda: render_sandbox_compose(node, sandbox, tokens["database"], tokens["admin"])}
    for name, call in calls.items():
        expected = row[name]
        if expected["kind"] == "text":
            assert hashlib.sha256(call().encode("utf-8")).hexdigest() == expected["sha256"]
        else:
            with pytest.raises(ValueError, match="Unsupported tech stack"):
                call()


def test_compose_input_is_deeply_detached_without_runtime_handles(reference):
    sandbox = Sandbox.model_validate(reference["cases"][0]["sandbox"])
    inputs = capture_sandbox_compose(sandbox)
    sandbox.ports.api = 9999
    sandbox.rock_id = "replacement"
    assert inputs.ports.api == 8001 and inputs.rock_id == "reference"
    assert not hasattr(inputs, "workspace_path") and not hasattr(inputs, "container_ids")
    with pytest.raises(ValidationError, match="frozen_instance"):
        inputs.ports.api = 9999
    with pytest.raises(ValidationError, match="frozen_instance"):
        inputs.rock_id = "replacement"


@pytest.mark.parametrize("proposal", [None, {}, [], 3])
def test_non_text_compose_recommendations_are_refused(reference, proposal):
    class Proposal:
        def generate_compose_file(self, **kwargs):
            return proposal
    sandbox = Sandbox.model_validate(reference["cases"][0]["sandbox"])
    with pytest.raises(ValueError, match="E_SANDBOX_POLICY_INVALID_COMPOSE_TEXT"):
        render_sandbox_compose(Proposal(), sandbox, "synthetic-db", "synthetic-admin")
