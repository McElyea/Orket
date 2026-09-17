"""Core contracts require explicit values and cannot manufacture effect claims."""

import itertools
import json
from dataclasses import FrozenInstanceError, replace

import pytest
from pydantic import ValidationError

from orket.core.domain.failure_reporter import FailureReporter, PolicyViolationReport
from orket.core.domain.reconciler import StructuralAsset, StructuralReconciler
from orket.core.policies.tool_gate import FileWriteFacts
from orket.core.policies.tool_gate import ToolGate as ToolGatePolicy
from tests.helpers.core_effect_fixtures import BOARD_ASSETS, TIMESTAMP

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "violation,kind",
    [
        ("illegal transition", "state_transition"),
        ("tool blocked", "tool_gate"),
        ("structural mismatch", "structural"),
        ("unknown failure", "governance"),
    ],
)
def test_failure_values_preserve_explicit_time_and_classification(violation, kind):
    """Layer: contract. The same explicit inputs produce the same serialized failure value."""
    inputs = dict(timestamp=TIMESTAMP, session_id="run", card_id="card", violation=violation, roles=("dev",))
    first = FailureReporter.build_report(**inputs)
    assert first.timestamp == TIMESTAMP and first.violation_type == kind
    assert first.active_roles == ("dev",)
    assert all(FailureReporter.build_report(**inputs).model_dump_json() == first.model_dump_json() for _ in range(20))
    with pytest.raises(ValidationError):
        first.timestamp = "changed"


def test_failure_timestamp_is_required_input():
    """Layer: contract. Missing time cannot silently select an ambient clock."""
    with pytest.raises(ValidationError, match="timestamp"):
        PolicyViolationReport(
            session_id="run", card_id="card", violation_type="governance", detail="x", remedy_suggestion="x"
        )


def test_reconciliation_is_order_independent_and_keeps_input_values_unchanged():
    """Layer: contract. A fixed snapshot produces one deterministic two-target plan."""
    expected = StructuralReconciler.plan(BOARD_ASSETS)
    assert not expected.problems
    assert len(expected.writes) == 2 and len(expected.adoptions) == 2
    for assets in itertools.permutations(BOARD_ASSETS):
        assert StructuralReconciler.plan(assets) == expected
    targets = {w.relative_path: json.loads(w.content) for w in expected.writes}
    assert targets["core/rocks/run_the_business.json"] == {"epics": [{"epic": "product_plan", "department": "product"}]}
    assert targets["core/epics/unplanned_support.json"] == {"issues": [{"id": "orphan", "summary": "Unplanned work"}]}
    assert BOARD_ASSETS[0].content == '{"epics": []}'
    with pytest.raises(FrozenInstanceError):
        BOARD_ASSETS[0].content = "changed"


@pytest.mark.parametrize("kind,content", [("rocks", "{broken"), ("epics", '{"issues": [4]}'), ("issues", "[]")])
def test_invalid_snapshot_has_no_proposed_writes_or_adoptions(kind, content):
    """Layer: contract. Invalid assets cannot yield successful adoption claims."""
    invalid = StructuralAsset("other", kind, "invalid", content)
    plan = StructuralReconciler.plan(BOARD_ASSETS + (invalid,))
    assert plan.problems and not plan.writes and not plan.adoptions


def test_missing_required_target_cannot_be_a_successful_noop():
    """Layer: contract. Existing orphan work with no adoption target is an explicit problem."""
    plan = StructuralReconciler.plan(BOARD_ASSETS[2:])
    assert len(plan.problems) == 2 and not plan.writes and not plan.adoptions


def test_applied_plan_is_idempotent_for_the_same_structural_assets():
    """Layer: contract. Retained linked identities do not produce duplicate adoptions."""
    first = StructuralReconciler.plan(BOARD_ASSETS)
    writes = {w.relative_path: w.content for w in first.writes}
    updated = tuple(replace(a, content=writes.get(a.relative_path, a.content)) for a in BOARD_ASSETS)
    second = StructuralReconciler.plan(updated)
    assert not second.problems and not second.writes and not second.adoptions


def test_duplicate_epic_names_keep_one_deterministic_adoption():
    """Layer: contract. Global epic names retain one adoption regardless of snapshot ordering."""
    assets = BOARD_ASSETS[:2] + (
        StructuralAsset("alpha", "epics", "shared", '{"issues": []}'),
        StructuralAsset("beta", "epics", "shared", '{"issues": []}'),
    )
    expected = StructuralReconciler.plan(assets)
    assert not expected.problems and len(expected.adoptions) == 1
    assert expected.adoptions[0].department == "alpha"
    assert all(StructuralReconciler.plan(order) == expected for order in itertools.permutations(assets))
    writes = {w.relative_path: w.content for w in expected.writes}
    updated = tuple(replace(a, content=writes.get(a.relative_path, a.content)) for a in assets)
    assert not StructuralReconciler.plan(updated).adoptions


def test_core_file_policy_requires_explicit_facts_and_preserves_their_verdict(tmp_path):
    """Layer: contract. Core cannot obtain missing filesystem or validator context on its own."""
    policy = ToolGatePolicy(None)
    args = {"path": "source.py", "content": "value = 1"}
    assert policy.validate("write_file", args, {}, []) == "write_file requires application file-validation facts"
    facts = FileWriteFacts(str(tmp_path / "source.py"), "source.py")
    assert all(policy.validate("write_file", args, {}, [], file_facts=facts) is None for _ in range(20))
    refusal = FileWriteFacts("", "", "Explicit validator refusal")
    assert policy.validate("write_file", args, {}, [], file_facts=refusal) == "Explicit validator refusal"
