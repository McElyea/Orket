"""Source requirements with syntax-aware handling of the Python entrypoint guard."""
from __future__ import annotations

import ast

MAIN_GUARD = 'if __name__ == "__main__":'


def _has_main_guard(module: ast.Module | None) -> bool:
    if module is None:
        return False
    for statement in module.body:
        if not isinstance(statement, ast.If):
            continue
        condition = statement.test
        if not (isinstance(condition, ast.Compare) and len(condition.ops) == 1
                and isinstance(condition.ops[0], ast.Eq)):
            continue
        left, right = condition.left, condition.comparators[0]
        if isinstance(right, ast.Name):
            left, right = right, left
        if (isinstance(left, ast.Name) and left.id == "__name__"
                and isinstance(right, ast.Constant) and right.value == "__main__"):
            return True
    return False


def missing_source_requirements(required: list[str], source: str, module: ast.Module | None) -> list[str]:
    """Only the canonical main guard uses syntax; other tokens retain substring semantics."""
    lowered = source.lower()
    return [token for token in required
            if not (_has_main_guard(module) if token == MAIN_GUARD else token.lower() in lowered)]
