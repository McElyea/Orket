from __future__ import annotations

from orket.application.workflows.turn_tool_dispatcher_support import (
    determinism_violation_for_result,
    tool_policy_violation,
)


# Layer: unit
def test_tool_policy_violation_rejects_ring_not_allowed() -> None:
    violation = tool_policy_violation(
        tool_name="write_file",
        binding={"ring": "compatibility", "capability_profile": "workspace", "determinism_class": "workspace"},
        context={},
    )
    assert violation is not None
    assert "E_RING_POLICY_VIOLATION" in violation


# Layer: unit
def test_tool_policy_violation_rejects_capability_profile_not_allowed() -> None:
    violation = tool_policy_violation(
        tool_name="write_file",
        binding={"ring": "core", "capability_profile": "external", "determinism_class": "workspace"},
        context={"allowed_capability_profiles": ["workspace"]},
    )
    assert violation is not None
    assert "E_CAPABILITY_VIOLATION" in violation


# Layer: unit
def test_tool_policy_violation_rejects_determinism_class_more_nondeterministic_than_run() -> None:
    violation = tool_policy_violation(
        tool_name="write_file",
        binding={"ring": "core", "capability_profile": "workspace", "determinism_class": "external"},
        context={"run_determinism_class": "workspace"},
    )
    assert violation is not None
    assert "E_DETERMINISM_POLICY_VIOLATION" in violation


# Layer: unit
def test_tool_policy_violation_rejects_tool_to_tool_invocation_boundary() -> None:
    violation = tool_policy_violation(
        tool_name="write_file",
        binding={"ring": "core", "capability_profile": "workspace", "determinism_class": "workspace"},
        context={"invoked_from_tool": True},
    )
    assert violation is not None
    assert "E_TOOL_INVOCATION_BOUNDARY" in violation


# Layer: unit
def test_tool_policy_violation_accepts_default_core_workspace_policy() -> None:
    violation = tool_policy_violation(
        tool_name="write_file",
        binding={"ring": "core", "capability_profile": "workspace", "determinism_class": "workspace"},
        context={},
    )
    assert violation is None


# Layer: unit
def test_determinism_violation_for_result_flags_declared_pure_side_effecting_tool() -> None:
    violation = determinism_violation_for_result(
        tool_name="write_file",
        binding={"determinism_class": "pure"},
        result={"ok": True},
    )
    assert violation is not None
    assert "E_DETERMINISM_VIOLATION" in violation


# Layer: unit
def test_determinism_violation_for_result_allows_pure_without_side_effect_signals() -> None:
    violation = determinism_violation_for_result(
        tool_name="read_file",
        binding={"determinism_class": "pure"},
        result={"ok": True},
    )
    assert violation is None
