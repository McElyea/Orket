import ast
from pathlib import Path
from typing import List, Dict, Any, Set
from dataclasses import dataclass

@dataclass
class ASTRuleViolation:
    line: int
    message: str
    severity: str = "error"

class ASTValidator:
    """
    Advanced AST-based structural enforcer.
    Analyzes Python code to ensure strict adherence to iDesign principles.
    """
    
    @staticmethod
    def validate_code(content: str, filename: str) -> List[ASTRuleViolation]:
        violations = []
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return [ASTRuleViolation(line=e.lineno or 0, message=f"Syntax Error: {e.msg}", severity="error")]

        # Rules:
        # 1. Component suffix check in class names
        # 2. Dependency layer violation (imports)
        # 3. Method count (anti-God-class)
        
        category = ASTValidator._get_category(filename)
        
        for node in ast.walk(tree):
            # Class-level rules
            if isinstance(node, ast.ClassDef):
                violations.extend(ASTValidator._check_class_rules(node, category))
            
            # Import-level rules
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                violations.extend(ASTValidator._check_import_rules(node, category))
                
        return violations

    @staticmethod
    def _get_category(filename: str) -> str:
        f = filename.lower()
        if "manager" in f: return "manager"
        if "engine" in f: return "engine"
        if "accessor" in f: return "accessor"
        return "other"

    @staticmethod
    def _check_class_rules(node: ast.ClassDef, category: str) -> List[ASTRuleViolation]:
        violations = []
        name = node.name.lower()
        
        # Suffix enforcement
        if category == "manager" and "manager" not in name:
            violations.append(ASTRuleViolation(line=node.lineno, message=f"Class '{node.name}' in a Manager component must end with 'Manager' suffix."))
        if category == "engine" and "engine" not in name:
            violations.append(ASTRuleViolation(line=node.lineno, message=f"Class '{node.name}' in an Engine component must end with 'Engine' suffix."))
        if category == "accessor" and "accessor" not in name:
            violations.append(ASTRuleViolation(line=node.lineno, message=f"Class '{node.name}' in an Accessor component must end with 'Accessor' suffix."))

        # Method count (God-class heuristic)
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        if len(methods) > 15:
            violations.append(ASTRuleViolation(line=node.lineno, message=f"Class '{node.name}' has {len(methods)} methods. iDesign recommends splitting high-complexity components.", severity="warning"))
            
        return violations

    @staticmethod
    def _check_import_rules(node: Any, category: str) -> List[ASTRuleViolation]:
        violations = []
        
        # Define forbidden patterns (Layer Violations)
        # Accessors cannot import Managers or Engines
        # Engines cannot import Managers
        
        target_modules = []
        if isinstance(node, ast.Import):
            target_modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            target_modules = [node.module] if node.module else []

        for mod in target_modules:
            if not mod: continue
            mod_lower = mod.lower()
            
            if category == "accessor":
                if "manager" in mod_lower or "engine" in mod_lower:
                    violations.append(ASTRuleViolation(line=node.lineno, message=f"Layer Violation: Accessor cannot depend on {mod}. Accessors must be leaf nodes."))
            
            if category == "engine":
                if "manager" in mod_lower:
                    violations.append(ASTRuleViolation(line=node.lineno, message=f"Layer Violation: Engine cannot depend on Manager '{mod}'. Engines only depend on Accessors or other Engines."))

        return violations
