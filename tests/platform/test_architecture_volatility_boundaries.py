from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOW_VOL_ROOTS = [
    PROJECT_ROOT / "orket" / "core" / "domain",
    PROJECT_ROOT / "orket" / "core" / "contracts",
]

FORBIDDEN_PREFIXES = (
    "orket.application",
    "orket.adapters",
    "orket.platform",
    "orket.orchestration",
    "orket.interfaces",
    "orket.infrastructure",
    "orket.runtime",
    "orket.services",
    "orket.agents",
    "orket.vendors",
)

LEGACY_IMPORT_PREFIXES = (
    "orket.llm",
    "orket.services.prompt_compiler",
    "orket.services.tool_parser",
    "orket.services.webhook_db",
    "orket.services.gitea_webhook_handler",
    "orket.infrastructure",
    "orket.tool_runtime",
    "orket.tool_strategy",
    "orket.tool_families",
    "orket.orchestration.orchestrator",
    "orket.orchestration.turn_executor",
)


def _imports_for(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_low_volatility_layers_do_not_depend_on_high_volatility_layers():
    violations: list[str] = []
    for root in LOW_VOL_ROOTS:
        for path in root.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            for imp in _imports_for(path):
                if imp.startswith(FORBIDDEN_PREFIXES):
                    rel = path.relative_to(PROJECT_ROOT)
                    violations.append(f"{rel}: forbidden import '{imp}'")
    assert not violations, "Architecture boundary violations:\n" + "\n".join(violations)


def test_application_layer_does_not_depend_on_interfaces_layer():
    app_root = PROJECT_ROOT / "orket" / "application"
    violations: list[str] = []
    for path in app_root.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        for imp in _imports_for(path):
            if imp.startswith("orket.interfaces"):
                rel = path.relative_to(PROJECT_ROOT)
                violations.append(f"{rel}: forbidden import '{imp}'")
    assert not violations, "Application->Interfaces boundary violations:\n" + "\n".join(violations)


def test_application_layer_does_not_depend_on_adapters_layer():
    app_root = PROJECT_ROOT / "orket" / "application"
    violations: list[str] = []
    for path in app_root.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        for imp in _imports_for(path):
            if imp.startswith("orket.adapters"):
                rel = path.relative_to(PROJECT_ROOT)
                violations.append(f"{rel}: forbidden import '{imp}'")
    assert not violations, "Application->Adapters boundary violations:\n" + "\n".join(violations)


def test_runtime_code_has_no_legacy_namespace_imports():
    runtime_root = PROJECT_ROOT / "orket"
    violations: list[str] = []
    for path in runtime_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path.name == "__init__.py":
            continue
        for imp in _imports_for(path):
            if imp.startswith(LEGACY_IMPORT_PREFIXES):
                rel = path.relative_to(PROJECT_ROOT)
                violations.append(f"{rel}: forbidden legacy import '{imp}'")
    assert not violations, "Runtime legacy-import violations:\n" + "\n".join(violations)

