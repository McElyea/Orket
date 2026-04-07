from pathlib import Path

import pytest

from orket.schema import OrganizationConfig
from orket.services.ast_validator import ASTValidator
from orket.services.tool_gate import ToolGate


def test_ast_validator_suffix_violation():
    code = "class WrongName:\n    pass"
    violations = ASTValidator.validate_code(code, "test_manager.py")
    assert any("must end with 'Manager' suffix" in v.message for v in violations)

def test_ast_validator_layer_violation():
    code = "import orket.managers.engine_manager\nclass MyAccessor:\n    pass"
    violations = ASTValidator.validate_code(code, "db_accessor.py")
    assert any("Layer Violation: Accessor cannot depend on" in v.message for v in violations)

def test_ast_validator_god_class_warning():
    # 16 methods to trigger warning
    methods = "\n".join([f"    def method_{i}(self): pass" for i in range(16)])
    code = f"class HugeManager:\n{methods}"
    violations = ASTValidator.validate_code(code, "big_manager.py")
    assert any("iDesign recommends splitting high-complexity components" in v.message for v in violations)
    assert all(v.severity == "warning" for v in violations if "complexity" in v.message)

@pytest.mark.asyncio
async def test_tool_gate_blocks_ast_violation(tmp_path):
    gate = ToolGate(None, tmp_path)
    # Violates layer rule: Accessor importing Manager
    args = {
        "path": "accessors/db_accessor.py",
        "content": "import orket.managers.my_manager\nclass DbAccessor: pass"
    }
    context = {"role": "coder", "idesign_enabled": True}

    result = await gate.validate("write_file", args, context, ["coder"])
    assert "iDesign AST Violation: Layer Violation" in result

@pytest.mark.asyncio
async def test_tool_gate_allows_valid_ast(tmp_path):
    gate = ToolGate(None, tmp_path)
    args = {
        "path": "managers/order_manager.py",
        "content": "class OrderManager:\n    def process(self): pass"
    }
    context = {"role": "coder", "idesign_enabled": True}

    result = await gate.validate("write_file", args, context, ["coder"])
    assert result is None


@pytest.mark.asyncio
async def test_tool_gate_skips_idesign_ast_when_disabled(tmp_path):
    gate = ToolGate(None, tmp_path)
    args = {
        "path": "accessors/db_accessor.py",
        "content": "import orket.managers.my_manager\nclass DbAccessor: pass",
    }
    context = {"role": "coder", "idesign_enabled": False}

    result = await gate.validate("write_file", args, context, ["coder"])
    assert result is None


@pytest.mark.asyncio
async def test_tool_gate_passes_real_role_and_issue_id_to_idesign_validator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Layer: integration. Verifies file-write validation passes the actual execution identity to iDesign validation."""
    gate = ToolGate(None, tmp_path)
    captured = {}

    def _spy_validate_turn(_validator, turn, workspace_root):  # type: ignore[no-untyped-def]
        captured["role"] = turn.role
        captured["issue_id"] = turn.issue_id
        captured["workspace_root"] = workspace_root
        return []

    monkeypatch.setattr("orket.services.idesign_validator.iDesignValidator.validate_turn", _spy_validate_turn)
    result = await gate.validate(
        "write_file",
        {"path": "agent_output/test.py", "content": "print('ok')\n"},
        {"role": "coder", "issue_id": "iss-001", "idesign_enabled": True},
        ["coder"],
    )

    assert result is None
    assert captured == {"role": "coder", "issue_id": "iss-001", "workspace_root": tmp_path}


@pytest.mark.asyncio
async def test_tool_gate_uses_configured_idesign_categories(tmp_path):
    """Layer: integration. Verifies organization-configured iDesign categories replace the built-in fallback."""
    org = OrganizationConfig(
        name="demo",
        vision="ship",
        ethos="truth",
        allowed_idesign_categories=["utilities"],
    )
    gate = ToolGate(org, tmp_path)

    result = await gate.validate(
        "write_file",
        {"path": "utilities/helpers.py", "content": "print('ok')\n"},
        {"role": "coder", "idesign_enabled": True},
        ["coder"],
    )

    assert result is None

