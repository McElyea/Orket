"""
Tests for Tool Gating (Phase 2: Mechanical Enforcement)

Validates that tool calls are intercepted and validated BEFORE execution,
enforcing organizational invariants at the tool level.
"""
import pytest
from pathlib import Path
from orket.services.tool_gate import ToolGate, ToolGateViolation
from orket.schema import OrganizationConfig, CardStatus, WaitReason


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def tool_gate(workspace):
    """Create a ToolGate with no organization (permissive mode)."""
    return ToolGate(organization=None, workspace_root=workspace)


@pytest.fixture
def strict_tool_gate(workspace):
    """Create a ToolGate with strict organizational policy."""
    org = OrganizationConfig(
        name="Test Org",
        vision="Test",
        ethos="Test",
        branding={"design_dos": []},
        architecture={
            "cicd_rules": [],
            "preferred_stack": {},
            "idesign_threshold": 7
        },
        departments=["core"]
    )
    return ToolGate(organization=org, workspace_root=workspace)


# ============================================================================
# File Write Boundary Enforcement
# ============================================================================

def test_write_file_within_workspace_allowed(tool_gate, workspace):
    """Validate that writing within workspace is allowed."""
    result = tool_gate.validate(
        tool_name="write_file",
        args={"path": "test.txt", "content": "Hello"},
        context={},
        roles=["developer"]
    )
    assert result is None, "Should allow writes within workspace"


def test_write_file_absolute_path_within_workspace(tool_gate, workspace):
    """Validate absolute paths within workspace are allowed."""
    file_path = str(workspace / "subdir" / "file.txt")
    result = tool_gate.validate(
        tool_name="write_file",
        args={"path": file_path, "content": "Test"},
        context={},
        roles=["developer"]
    )
    assert result is None, "Should allow absolute paths within workspace"


def test_write_file_escapes_workspace_blocked(tool_gate, workspace):
    """Validate that path traversal outside workspace is blocked."""
    result = tool_gate.validate(
        tool_name="write_file",
        args={"path": "../../../etc/passwd", "content": "Evil"},
        context={},
        roles=["developer"]
    )
    assert result is not None, "Should block path traversal"
    assert "outside workspace" in result.lower()


def test_write_file_missing_path_blocked(tool_gate):
    """Validate that missing path argument is caught."""
    result = tool_gate.validate(
        tool_name="write_file",
        args={"content": "No path provided"},
        context={},
        roles=["developer"]
    )
    assert result is not None
    assert "requires 'path'" in result.lower()


def test_dependency_manifest_write_blocked_for_non_owner_role(workspace):
    org = OrganizationConfig(
        name="Test Org",
        vision="Test",
        ethos="Test",
        branding={"design_dos": []},
        architecture={
            "cicd_rules": [],
            "preferred_stack": {},
            "idesign_threshold": 7
        },
        departments=["core"],
        process_rules={
            "dependency_file_ownership_enabled": True,
            "dependency_managed_files": ["agent_output/dependencies/requirements.txt"],
            "dependency_file_owner_roles": ["dependency_manager"],
        },
    )
    gate = ToolGate(organization=org, workspace_root=workspace)

    result = gate.validate(
        tool_name="write_file",
        args={"path": "agent_output/dependencies/requirements.txt", "content": "httpx==0.28.1"},
        context={"role": "coder"},
        roles=["coder"],
    )
    assert result is not None
    assert "dependency manifest" in result.lower()


def test_dependency_manifest_write_allowed_for_owner_role(workspace):
    org = OrganizationConfig(
        name="Test Org",
        vision="Test",
        ethos="Test",
        branding={"design_dos": []},
        architecture={
            "cicd_rules": [],
            "preferred_stack": {},
            "idesign_threshold": 7
        },
        departments=["core"],
        process_rules={
            "dependency_file_ownership_enabled": True,
            "dependency_managed_files": ["agent_output/dependencies/requirements.txt"],
            "dependency_file_owner_roles": ["dependency_manager"],
        },
    )
    gate = ToolGate(organization=org, workspace_root=workspace)

    result = gate.validate(
        tool_name="write_file",
        args={"path": "agent_output/dependencies/requirements.txt", "content": "httpx==0.28.1"},
        context={"role": "dependency_manager"},
        roles=["dependency_manager"],
    )
    assert result is None


# ============================================================================
# State Transition Enforcement
# ============================================================================

def test_state_change_valid_transition_allowed(strict_tool_gate):
    """Validate that valid state transitions are allowed."""
    result = strict_tool_gate.validate(
        tool_name="update_issue_status",
        args={"status": "in_progress"},
        context={"current_status": "ready"},
        roles=["developer"]
    )
    assert result is None, "Should allow valid transitions"


def test_state_change_invalid_status_blocked(strict_tool_gate):
    """Validate that invalid status values are blocked."""
    result = strict_tool_gate.validate(
        tool_name="update_issue_status",
        args={"status": "invalid_status"},
        context={"current_status": "ready"},
        roles=["developer"]
    )
    assert result is not None
    assert "invalid status" in result.lower()


def test_state_change_missing_status_blocked(strict_tool_gate):
    """Validate that missing status argument is caught."""
    result = strict_tool_gate.validate(
        tool_name="update_issue_status",
        args={},
        context={"current_status": "ready"},
        roles=["developer"]
    )
    assert result is not None
    assert "requires 'status'" in result.lower()


def test_state_change_to_blocked_without_wait_reason_blocked(strict_tool_gate):
    """Validate that transitions to BLOCKED require wait_reason."""
    result = strict_tool_gate.validate(
        tool_name="update_issue_status",
        args={"status": "blocked"},
        context={"current_status": "in_progress"},
        roles=["developer"]
    )
    assert result is not None
    assert "wait_reason" in result.lower()


def test_state_change_to_blocked_with_wait_reason_allowed(strict_tool_gate):
    """Validate that transitions to BLOCKED with wait_reason are allowed."""
    result = strict_tool_gate.validate(
        tool_name="update_issue_status",
        args={"status": "blocked", "wait_reason": WaitReason.DEPENDENCY},
        context={"current_status": "in_progress"},
        roles=["developer"]
    )
    assert result is None, "Should allow blocked with wait_reason"


def test_state_change_to_done_without_integrity_guard_blocked(strict_tool_gate):
    """Validate that only integrity_guard can finalize to DONE."""
    result = strict_tool_gate.validate(
        tool_name="update_issue_status",
        args={"status": "done"},
        context={"current_status": "code_review"},
        roles=["developer"]  # No integrity_guard role
    )
    assert result is not None
    assert "integrity_guard" in result.lower()


def test_state_change_to_done_with_integrity_guard_allowed(strict_tool_gate):
    """Validate that integrity_guard CAN finalize to DONE."""
    result = strict_tool_gate.validate(
        tool_name="update_issue_status",
        args={"status": "done"},
        context={"current_status": "code_review"},
        roles=["integrity_guard"]
    )
    assert result is None, "Should allow integrity_guard to finalize"


# ============================================================================
# Destructive Operation Protection
# ============================================================================

def test_destructive_operation_without_confirm_blocked(tool_gate):
    """Validate that destructive operations require confirmation."""
    result = tool_gate.validate(
        tool_name="delete_file",
        args={"path": "important.txt"},
        context={},
        roles=["developer"]
    )
    assert result is not None
    assert "confirmation" in result.lower()


def test_destructive_operation_with_confirm_allowed(tool_gate):
    """Validate that confirmed destructive operations are allowed."""
    result = tool_gate.validate(
        tool_name="delete_file",
        args={"path": "file.txt", "confirm": True},
        context={},
        roles=["developer"]
    )
    assert result is None, "Should allow confirmed destructive operations"


# ============================================================================
# Issue Creation Validation
# ============================================================================

def test_issue_creation_with_valid_summary_allowed(tool_gate):
    """Validate that issue creation with proper summary is allowed."""
    result = tool_gate.validate(
        tool_name="create_issue",
        args={"summary": "Implement feature X", "description": "Details"},
        context={},
        roles=["developer"]
    )
    assert result is None


def test_issue_creation_with_short_summary_blocked(tool_gate):
    """Validate that issues must have meaningful summaries."""
    result = tool_gate.validate(
        tool_name="create_issue",
        args={"summary": "Fix", "description": "Something"},
        context={},
        roles=["developer"]
    )
    assert result is not None
    assert "at least 5 characters" in result.lower()


# ============================================================================
# Unknown/Ungated Tools
# ============================================================================

def test_unknown_tool_passes_through(tool_gate):
    """Validate that unknown tools pass through without error."""
    result = tool_gate.validate(
        tool_name="unknown_custom_tool",
        args={"foo": "bar"},
        context={},
        roles=["developer"]
    )
    assert result is None, "Unknown tools should pass validation (fail later at execution)"


# ============================================================================
# Integration Test: Multi-Gate Validation
# ============================================================================

def test_multi_gate_validation_blocks_multiple_violations(strict_tool_gate, workspace):
    """Test that gate correctly identifies first violation in a sequence."""
    # This would be blocked due to workspace escape
    result1 = strict_tool_gate.validate(
        "write_file",
        {"path": "../../../evil", "content": "hack"},
        {},
        ["developer"]
    )

    # This would be blocked due to missing wait_reason
    result2 = strict_tool_gate.validate(
        "update_issue_status",
        {"status": "blocked"},
        {"current_status": "in_progress"},
        ["developer"]
    )

    # This would be blocked due to missing integrity_guard
    result3 = strict_tool_gate.validate(
        "update_issue_status",
        {"status": "done"},
        {"current_status": "code_review"},
        ["developer"]
    )

    assert result1 is not None
    assert result2 is not None
    assert result3 is not None

