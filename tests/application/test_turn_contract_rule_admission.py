"""Decision and scope contracts through the public validator; no tool execution claim."""
import json
from copy import deepcopy

import pytest

from orket.core.domain.execution import ExecutionTurn, ToolCall
from tests.application.test_turn_contract_validator import _observation, _role, _validator

pytestmark = pytest.mark.contract


def _decision(**changes):
    return {"recommendation": "monolith", "confidence": 0.8, "evidence": {key: True for key in (
        "estimated_domains", "external_integrations", "independent_scaling_needs", "deployment_complexity",
        "team_parallelism", "operational_maturity")}, **changes}


def _turn(*calls, content=""):
    return ExecutionTurn(role="developer", issue_id="decision", timestamp=None, content=content, tool_calls=list(calls))


@pytest.mark.parametrize("changes,context", [
    ({}, {"architecture_decision_path": ""}),
    ({"recommendation": "unknown"}, {}),
    ({}, {"architecture_forced_pattern": "microservices"}),
    ({"frontend_framework": "unknown"}, {}),
    ({"frontend_framework": "vue"}, {"frontend_framework_forced": "react"}),
    ({"confidence": "invalid"}, {}), ({"confidence": " "}, {}), ({"confidence": []}, {}),
    ({"confidence": -0.1}, {}), ({"confidence": 1.1}, {}), ({"evidence": []}, {}), ({"evidence": {}}, {}),
])
def test_architecture_refusal_surfaces_in_complete_contract_diagnostics(tmp_path, changes, context):
    turn = _turn(ToolCall("write_file", {"path": "agent_output/design.txt", "content": json.dumps(_decision(**changes))}))
    context = {"architecture_decision_required": True, **context}
    before = deepcopy((turn, context))
    validator = _validator(tmp_path)
    assert not validator.meets_architecture_decision_contract(turn, context)
    violations = validator.collect_contract_violations(turn, _role(), context, _observation())
    assert any(item["reason"] == "architecture_decision_contract_not_met" for item in violations)
    assert (turn, context) == before


@pytest.mark.parametrize("content", [None, [], "invalid", "[]"])
def test_required_decision_must_be_a_parseable_object_at_the_selected_path(tmp_path, content):
    validator = _validator(tmp_path)
    context = {"architecture_decision_required": True}
    ignored = [ToolCall("read_file", {"path": "agent_output/design.txt"}),
               ToolCall("write_file", {"path": "other.txt", "content": json.dumps(_decision())})]
    assert not validator.meets_architecture_decision_contract(_turn(*ignored), context)
    assert not validator.meets_architecture_decision_contract(
        _turn(*ignored, ToolCall("write_file", {"path": "agent_output/design.txt", "content": content})), context)


def test_numeric_string_and_empty_pattern_allowlist_preserve_admission(tmp_path):
    turn = _turn(ToolCall("write_file", {"path": "agent_output/design.txt",
        "content": json.dumps(_decision(confidence=" 0.75 "))}))
    assert _validator(tmp_path).meets_architecture_decision_contract(turn,
        {"architecture_decision_required": True, "architecture_allowed_patterns": [" "]})


def test_legacy_decision_recovery_still_requires_all_evidence_keys(tmp_path):
    validator = _validator(tmp_path)
    wrapped = "legacy " + json.dumps(_decision(frontend_framework="vue"))
    assert validator.parse_architecture_decision_payload(wrapped) == _decision(frontend_framework="vue")
    assert validator.parse_architecture_decision_payload(wrapped.replace('"team_parallelism"', '"omitted"')) is None
    assert validator.parse_architecture_decision_payload("[]") is None


def test_scope_budgets_grounding_and_interface_diagnostics_remain_distinct(tmp_path):
    validator = _validator(tmp_path)
    turn = _turn(ToolCall("write_file", {"path": "created.txt", "content": "data"}),
        ToolCall("read_file", {"path": "created.txt"}), ToolCall("read_file", {"path": "absent.txt"}),
        ToolCall("get_issue_context", {"section": "absent-section"}), ToolCall("undeclared", {}),
        content="Maybe this is a forbidden claim.")
    scope = {"workspace": ["existing.txt"], "active_context": ["active"], "passive_context": ["passive"],
        "archived_context": ["archived"], "max_workspace_items": 0, "max_active_context_items": 0,
        "max_passive_context_items": 0, "max_archived_context_items": 0, "max_total_context_items": 2,
        "strict_grounding": True, "forbidden_phrases": ["forbidden claim", "not present"],
        "declared_interfaces": ["write_file", "read_file", "get_issue_context"]}
    result = validator.hallucination_scope_diagnostics(turn, {"verification_scope": scope})
    assert [item["rule_id"] for item in result["violations"]] == ["HALLUCINATION." + suffix for suffix in [
        "WORKSPACE_BUDGET_EXCEEDED", "ACTIVE_CONTEXT_BUDGET_EXCEEDED", "PASSIVE_CONTEXT_BUDGET_EXCEEDED",
        "ARCHIVED_CONTEXT_BUDGET_EXCEEDED", "TOTAL_CONTEXT_BUDGET_EXCEEDED", "FILE_NOT_FOUND",
        "CONTEXT_NOT_PROVIDED", "API_NOT_DECLARED", "INVENTED_DETAIL", "CONTRADICTION"]]
    assert result["violations"][5]["evidence"] == "absent.txt"
    assert result["violations"][8]["evidence"] == "Maybe"


def test_security_scope_handles_empty_paths_and_explicit_disable(tmp_path):
    validator = _validator(tmp_path)
    turn = _turn(ToolCall("read_file", {"path": ""}), ToolCall("write_file", {"path": "../escape"}))
    active = validator.security_scope_diagnostics(turn, {"verification_scope": {}})
    assert [item["rule_id"] for item in active["violations"]] == ["SECURITY.PATH_TRAVERSAL"]
    assert validator.security_scope_diagnostics(turn,
        {"verification_scope": {"enforce_path_hardening": False}}) == {
            "scope": {"enforce_path_hardening": False}, "violations": []}


@pytest.mark.parametrize("content", ['{"unrelated":', '{"tool": bad}', "plain prose"])
def test_tool_only_output_does_not_accept_unrelated_or_balanced_invalid_json(tmp_path, content):
    turn = _turn(ToolCall("write_file", {"path": "out.txt", "content": "ok"}), content=content)
    result = _validator(tmp_path).consistency_scope_diagnostics(turn,
        {"verification_scope": {"consistency_tool_calls_only": True}})
    assert [item["rule_id"] for item in result["violations"]] == ["CONSISTENCY.OUTPUT_FORMAT"]
