"""Contract: compact packets retain supplied authority and avoid invented facts."""
from copy import deepcopy

import pytest

from orket.runtime.config.compact_turn_packet import compact_turn_messages, is_compact_turn_packet

pytestmark = pytest.mark.contract


def _render(context, messages=None):
    result = compact_turn_messages(messages or [], runtime_context=context)
    assert result.applied and result.compacted_message_count == 2
    assert [message["role"] for message in result.messages] == ["system", "user"]
    return result.messages[1]["content"]


def test_fallback_packet_retains_declared_constraints_and_verifier_limits():
    packet = _render({
        "role": "reviewer", "execution_profile": "governed", "current_status": "ready",
        "required_action_tools": ["write_file", "update_issue_status"], "required_statuses": ["done"],
        "required_read_paths": ["input.txt"], "required_write_paths": ["out.txt"],
        "available_tools": ["write_file", "update_issue_status"],
        "dependency_context": {"dependency_count": 2, "depends_on": ["A", "B"],
                               "unresolved_dependencies": ["B"], "dependency_statuses": {"A": "done"}},
        "artifact_contract": {"kind": "text", "primary_output": "out.txt", "semantic_checks": [
            {"path": "out.txt", "label": "report", "must_contain": ["approved"],
             "must_not_contain": ["placeholder"]}, {"label": "appendix"}, {}]},
        "runtime_verifier_ok": True,
        "runtime_verifier_contract": {"commands": [["python", "verify.py"],
            {"cwd": "checks", "argv": ["python", "contract.py"]}], "expect_json_stdout": True,
            "json_assertions": [{"path": "ok", "op": "eq", "value": True}]},
        "scenario_truth": {"scenario_id": "scenario-a", "expected_terminal_status": "done",
                           "blocked_issue_policy": {"blocked_implies_run_failure": True,
                                                    "allowed_issue_ids": ["B"]}},
        "required_comment_min_length": 20, "required_comment_contains": ["evidence"],
        "architecture_decision_required": True, "architecture_forced_pattern": "monolith",
        "frontend_framework_forced": "none",
    })
    expected = [
        "- execution_profile: governed", "- required tools: write_file, update_issue_status",
        "- allowed statuses: done", "- required read paths: input.txt", "- required write paths: out.txt",
        "- primary output: out.txt", "- dependency_count: 2", "- depends_on: A, B",
        "- unresolved_dependencies: B", "- dependency_statuses: A=done",
        "Artifact Checks:\n- out.txt (report)\n  must contain: approved\n  must not contain: placeholder\n- appendix\n- artifact",
        "support verifier: no reported errors; this does not establish accepted completion",
        "cwd=.: python verify.py", "cwd=checks: python contract.py", "stdout must be valid JSON",
        "ok eq True", "- scenario_id: scenario-a", "- expected_terminal_status: done",
        "- blocked implies run failure", "- blocked allowed only for: B",
        "- minimum comment length: 20", "- required comment tokens: evidence",
        "agent_output/design.txt", "- recommendation must be one of: monolith, microservices",
        "- recommendation must equal: monolith", "- frontend_framework must equal: none",
    ]
    for text in expected:
        assert text in packet


@pytest.mark.parametrize("status,wording", [
    (True, "no reported errors; this does not establish accepted completion"),
    (False, "reported errors; consult declared acceptance and diagnostics"),
    (None, None),
])
@pytest.mark.parametrize("contract", [None, {}, {"commands": []}])
def test_verifier_observation_does_not_invent_commands_or_completion(status, wording, contract):
    packet = _render({"artifact_contract": {"kind": "text"}, "runtime_verifier_ok": status,
                      "runtime_verifier_contract": contract})
    assert ("Runtime Verification:" in packet) is (wording is not None)
    if wording:
        assert wording in packet
    assert "verifier commands:" not in packet and "stdout assertions:" not in packet


def test_incomplete_optional_metadata_does_not_create_actionable_constraints():
    packet = _render({
        "role": " ", "required_statuses": "done", "available_tools": [None, "", " read_file "],
        "dependency_context": {"dependency_statuses": {" ": "done"}},
        "artifact_contract": {"kind": "text", "semantic_checks": [None, "untrusted"]},
        "runtime_verifier_contract": {"commands": [None, {"argv": "echo injected"}, [], [" "],
                                                   {"cwd": " ", "argv": ["echo", "verified"]}],
                                      "json_assertions": [None, {}, {"path": "ok"},
                                                          {"path": "value", "op": "exists"}]},
        "scenario_truth": {"blocked_issue_policy": "untrusted"},
        "required_comment_contains": [None, " "]})
    assert "- role: unknown" in packet and "- available tools: read_file" in packet
    assert "- dependency_count: 0" in packet
    for absent in ("Artifact Checks:", "Scenario Constraints:", "Review Comment Rules:",
                   "dependency_statuses:", "allowed statuses:", "echo injected"):
        assert absent not in packet
    assert "cwd=.: echo verified" in packet and "value exists None" in packet


@pytest.mark.parametrize("field", ["artifact_contract", "dependency_context", "scenario_truth"])
@pytest.mark.parametrize("value", [None, [], "untrusted", {}])
def test_absent_optional_contracts_do_not_invent_sections(field, value):
    packet = _render({field: value})
    for title in ("Artifact Checks:", "Dependency Context:", "Scenario Constraints:", "Runtime Verification:"):
        assert title not in packet


@pytest.mark.parametrize("prefix,title,context", [
    ("Artifact Semantic Contract", "Artifact Checks", {"artifact_contract": {"kind": "text",
        "semantic_checks": [{"path": "fallback.txt"}]}}),
    ("Scenario Truth Contract", "Scenario Constraints", {"scenario_truth": {"scenario_id": "fallback"}}),
    ("Runtime Verifier Contract", "Runtime Verification", {"artifact_contract": {"kind": "text"},
        "runtime_verifier_contract": {"commands": [["fallback"]]}}),
    ("Comment Contract", "Review Comment Rules", {"required_comment_contains": ["fallback"]}),
    ("Architecture Decision Contract", "Architecture Contract", {"architecture_decision_required": True,
        "architecture_decision_path": "fallback"}),
])
def test_explicit_contract_message_precedes_context_fallback(prefix, title, context):
    packet = _render(context, [{"role": "system", "content": "initial"},
                               {"role": "user", "content": prefix + ":\nSupplied authority"}])
    assert title + ":\nSupplied authority" in packet
    assert "fallback" not in packet


@pytest.mark.parametrize("enabled", [True, False])
def test_verifier_gate_applies_to_explicit_messages(enabled):
    packet = _render({"artifact_contract": {"kind": "text"}, "runtime_verifier_enabled": enabled},
                     [{"role": "user", "content": "Runtime Verifier Contract:\nverify-before-finish"}])
    assert ("verify-before-finish" in packet) is enabled


def test_packet_preserves_system_sections_without_cross_section_spill():
    packet = _render({}, [{"role": "system", "content":
        "Identity\n\nPROJECT CONTEXT (PAST DECISIONS):\nUse retained decision\n\nPATCH:\nFix A\n\n"
        "Declared card acceptance:\nRun receipt required"}])
    assert "Project Context:\nUse retained decision\n\nPatch:\nFix A\n\nDeclared card acceptance:\nRun receipt required" in packet
    empty = _render({}, [{"role": "system", "content": "PATCH:\n\n\nDeclared card acceptance:\n"}])
    assert "Patch:" not in empty and "Declared card acceptance:" not in empty


@pytest.mark.parametrize("blocked", [True, False])
def test_packet_retains_required_rules_once_and_only_admitted_blocked_status(blocked):
    rules = ["- You must include all required tool calls in this same response.",
             "- A response containing only get_issue_context/add_issue_comment is invalid.",
             "- If you choose status=blocked, include wait_reason: resource|dependency|review|input|system.",
             "- Empty or placeholder content for required write_file paths is invalid.",
             "- When writing Python source through write_file, prefer single-quoted literals to keep the JSON payload valid."]
    messages = [{"role": "user", "content": "Turn Success Contract:\n" + "\n".join(rules + rules + ["unknown hint"])},
                {"role": "user", "content": "Write Path Contract:\n- Use workspace-relative paths exactly as listed.\nignored"},
                {"role": "user", "content": "Read Path Contract:\n- Do not use placeholder or absolute paths outside the workspace.\nignored"}]
    packet = _render({"required_statuses": ["blocked"] if blocked else ["done"]}, messages)
    for rule in rules:
        assert packet.count(rule) == (int(blocked) if "status=blocked" in rule else 1)
    assert "- Use workspace-relative write paths exactly as listed." in packet
    assert "unknown hint" not in packet and "ignored" not in packet


def test_compaction_is_idempotent_and_does_not_mutate_input():
    messages = [{"role": "user", "content": "Issue A: implement"}]
    before = deepcopy(messages)
    first = compact_turn_messages(messages, runtime_context={})
    assert messages == before and first.source_message_count == 1
    assert is_compact_turn_packet(first.messages)
    second = compact_turn_messages(first.messages, runtime_context={"role": "different"})
    assert not second.applied and second.messages == first.messages
    assert second.messages is not first.messages
    assert second.source_message_count == second.compacted_message_count == 2


def test_architecture_and_comment_constraints_allow_independent_optional_fields():
    packet = _render({"architecture_decision_required": True, "architecture_decision_path": "decision.json",
                      "architecture_allowed_patterns": ["modular"], "required_comment_contains": ["proof"]})
    assert "decision.json" in packet and "- recommendation must be one of: modular" in packet
    assert "must equal:" not in packet and "minimum comment length" not in packet
    assert "- required comment tokens: proof" in packet
    packet = _render({"required_comment_min_length": 5, "scenario_truth": {"scenario_id": "S"},
                      "artifact_contract": {"semantic_checks": [{"path": "out.txt"}]}})
    assert "- minimum comment length: 5" in packet and "required comment tokens:" not in packet
    assert "Scenario Constraints:\n- scenario_id: S" in packet and "Artifact Checks:\n- out.txt" in packet
