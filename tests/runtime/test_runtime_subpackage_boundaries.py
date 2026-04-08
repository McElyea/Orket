from __future__ import annotations

import ast
import importlib
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[2] / "orket" / "runtime"
DOMAIN_PACKAGES = frozenset({"config", "evidence", "execution", "policy", "registry", "summary"})


def test_runtime_flat_modules_are_one_release_alias_shims() -> None:
    """Layer: contract. Structural only; verifies migrated flat runtime modules stay compatibility aliases only."""
    for path in sorted(RUNTIME_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "_import_module(\"orket.runtime." in source, path
        assert "_sys.modules[__name__] = _module" in source, path


def test_runtime_domain_packages_declare_complete_public_surfaces() -> None:
    """Layer: contract. Structural only; verifies each runtime subpackage owns an explicit module surface."""
    for package_name in sorted(DOMAIN_PACKAGES):
        package_path = RUNTIME_ROOT / package_name
        module_names = {path.stem for path in package_path.glob("*.py") if path.name != "__init__.py"}
        package = importlib.import_module(f"orket.runtime.{package_name}")

        assert set(package.__all__) == module_names


def test_runtime_domain_modules_do_not_import_peer_domain_private_modules() -> None:
    """Layer: contract. Structural only; verifies cross-domain imports go through package public surfaces."""
    violations: list[str] = []
    for package_name in sorted(DOMAIN_PACKAGES):
        for path in sorted((RUNTIME_ROOT / package_name).glob("*.py")):
            if path.name == "__init__.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for module_name in _imported_module_names(tree):
                parts = module_name.split(".")
                if parts[:2] != ["orket", "runtime"] or len(parts) < 4:
                    continue
                imported_package = parts[2]
                if imported_package in DOMAIN_PACKAGES and imported_package != package_name:
                    violations.append(f"{path.relative_to(RUNTIME_ROOT)} -> {module_name}")

    assert violations == []


def _imported_module_names(tree: ast.AST) -> list[str]:
    module_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module_names.extend(str(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_names.append(str(node.module))
    return module_names
