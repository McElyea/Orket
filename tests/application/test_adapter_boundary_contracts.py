from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_ADAPTERS = (
    REPO_ROOT / "orket" / "adapters" / "storage" / "async_protocol_run_ledger.py",
    REPO_ROOT / "orket" / "adapters" / "storage" / "protocol_append_only_ledger.py",
)


def test_cited_ledger_adapters_do_not_import_application_workflows() -> None:
    """Layer: contract. Verifies Packet 2 ledger adapters stay below the application workflow layer."""
    violations: list[str] = []
    for path in LEDGER_ADAPTERS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = str(alias.name)
                    if module_name.startswith("orket.application.workflows"):
                        violations.append(f"{path.name} -> {module_name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                module_name = str(node.module)
                if module_name.startswith("orket.application.workflows"):
                    violations.append(f"{path.name} -> {module_name}")

    assert violations == []
