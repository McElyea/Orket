from __future__ import annotations

import ast
from pathlib import Path


def _assert_not_internal_orket_import(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "orket" or alias.name.startswith("orket."):
                    raise AssertionError(
                        f"E_SDK_INTERNAL_IMPORT: {module_path} imports disallowed module '{alias.name}'"
                    )
        if isinstance(node, ast.ImportFrom):
            # Relative imports are package-local and allowed.
            if node.level and node.level > 0:
                continue
            if node.module and (node.module == "orket" or node.module.startswith("orket.")):
                raise AssertionError(
                    f"E_SDK_INTERNAL_IMPORT: {module_path} imports disallowed module '{node.module}'"
                )


def test_sdk_has_no_internal_orket_imports() -> None:
    """Layer: contract. Verifies SDK package authority is isolated from internal `orket.*` imports."""
    sdk_root = Path(__file__).resolve().parents[2] / "orket_extension_sdk"
    for module_path in sorted(sdk_root.rglob("*.py")):
        if "__pycache__" in module_path.parts:
            continue
        _assert_not_internal_orket_import(module_path)
