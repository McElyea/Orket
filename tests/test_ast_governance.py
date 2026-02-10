import pytest
from pathlib import Path
from orket.services.tool_gate import ToolGate
from orket.services.ast_validator import ASTValidator

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

def test_tool_gate_blocks_ast_violation(tmp_path):
    gate = ToolGate(None, tmp_path)
    # Violates layer rule: Accessor importing Manager
    args = {
        "path": "accessors/db_accessor.py",
        "content": "import orket.managers.my_manager\nclass DbAccessor: pass"
    }
    context = {"role": "coder"}
    
    result = gate.validate("write_file", args, context, ["coder"])
    assert "iDesign AST Violation: Layer Violation" in result

def test_tool_gate_allows_valid_ast(tmp_path):
    gate = ToolGate(None, tmp_path)
    args = {
        "path": "managers/order_manager.py",
        "content": "class OrderManager:\n    def process(self): pass"
    }
    context = {"role": "coder"}
    
    result = gate.validate("write_file", args, context, ["coder"])
    assert result is None
