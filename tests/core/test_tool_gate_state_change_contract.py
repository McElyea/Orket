from pathlib import Path

import pytest

from orket.core.policies.tool_gate import ToolGate
from orket.schema import OrganizationConfig

pytestmark = pytest.mark.asyncio


def _strict_org() -> OrganizationConfig:
    return OrganizationConfig(
        name="Test Org",
        vision="Test",
        ethos="Test",
        branding={"design_dos": []},
        architecture={
            "cicd_rules": [],
            "preferred_stack": {},
            "idesign_threshold": 7,
        },
        departments=["core"],
    )


async def test_tool_gate_enforces_state_machine_without_org(tmp_path: Path) -> None:
    """Layer: contract. Verifies missing org config no longer disables transition validation."""
    gate = ToolGate(organization=None, workspace_root=tmp_path)

    result = await gate.validate(
        tool_name="update_issue_status",
        args={"status": "done"},
        context={"current_status": "code_review"},
        roles=["developer"],
    )

    assert result is not None
    assert "integrity_guard" in result.lower()


async def test_tool_gate_uses_context_card_type_for_state_transitions(tmp_path: Path) -> None:
    """Layer: contract. Verifies state validation uses the real card type from context instead of issue-only rules."""
    gate = ToolGate(organization=_strict_org(), workspace_root=tmp_path)

    result = await gate.validate(
        tool_name="update_issue_status",
        args={"status": "done"},
        context={"current_status": "in_progress", "card_type": "epic"},
        roles=["developer"],
    )

    assert result is None
