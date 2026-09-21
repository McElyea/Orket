"""Explicit execution identity inputs and strict recommendation contract."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.execution_policy_input_service import capture_execution_identifiers
from orket.decision_nodes.builtins import DefaultExecutionRuntimeStrategyNode

pytestmark = pytest.mark.contract
PUBLISHED_DEFAULTS = json.loads((Path(__file__).parents[1] / "fixtures/execution_policy_v050.json").read_text())["cases"]


@pytest.mark.parametrize("collection", [False, True])
@pytest.mark.parametrize("field", ["session_id", "build_id"])
@pytest.mark.parametrize("value", [None, "", 1, True, [], {}])
def test_invalid_selected_identity_is_refused(collection, field, value):
    node = DefaultExecutionRuntimeStrategyNode()
    method = ("select_epic_collection_session_id" if collection else "select_run_id") if field == "session_id" else (
        "select_epic_collection_build_id" if collection else "select_epic_build_id")
    calls = []
    def select(*args):
        calls.append(args)
        return value
    setattr(node, method, select)
    with pytest.raises(ValueError, match="E_EXECUTION_POLICY_INVALID_" + field.upper()):
        capture_execution_identifiers(node, SimpleNamespace(create_session_id=lambda: "generated"),
            name="My Epic", session_id="selected-session", build_id=None, collection=collection)
    assert len(calls) == 1


@pytest.mark.parametrize("collection", [False, True])
@pytest.mark.parametrize("session_id", [None, "", "explicit-session"])
@pytest.mark.parametrize("build_id", [None, "", "explicit-build"])
def test_default_capture_observes_only_missing_session_and_preserves_overrides(collection, session_id, build_id):
    calls = []
    def observe():
        calls.append("session")
        return "generated-session"
    selected = capture_execution_identifiers(DefaultExecutionRuntimeStrategyNode(), SimpleNamespace(create_session_id=observe),
        name="My Epic", session_id=session_id, build_id=build_id, collection=collection)
    prefix = "epic-collection-build-" if collection else "build-"
    assert selected == (session_id or "generated-session", build_id or prefix + "my_epic")
    assert calls == ([] if session_id else ["session"])


def test_selected_id_whitespace_is_preserved_and_string_subclass_is_refused():
    class Derived(str):
        pass
    node = DefaultExecutionRuntimeStrategyNode()
    inputs = SimpleNamespace(create_session_id=lambda: "generated")
    assert capture_execution_identifiers(node, inputs, name="Epic", session_id=" ", build_id=" ") == (" ", " ")
    node.select_run_id = lambda value: Derived(value)
    with pytest.raises(ValueError, match="INVALID_SESSION_ID"):
        capture_execution_identifiers(node, inputs, name="Epic", session_id="session", build_id=None)


@pytest.mark.parametrize("case", PUBLISHED_DEFAULTS)
def test_defaults_match_published_v050(case):
    selected = capture_execution_identifiers(DefaultExecutionRuntimeStrategyNode(),
        SimpleNamespace(create_session_id=lambda: "generated-session"),
        **{key: value for key, value in case.items() if key != "result"})
    assert list(selected) == case["result"]
