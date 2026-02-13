from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple


PACKAGE_ROOT = Path("orket")


def _module_from_path(path: Path) -> str:
    rel = path.with_suffix("").as_posix().replace("/", ".")
    return rel


def _layer_for_module(module: str) -> str:
    if not module.startswith("orket."):
        return "external"
    parts = module.split(".")
    if len(parts) < 2:
        return "root"
    top = parts[1]
    if top in {"core", "application", "adapters", "interfaces", "platform"}:
        return top
    if top in {"domain", "infrastructure", "services", "orchestration", "interfaces", "decision_nodes"}:
        return top
    return "root"


def _imports_for_file(path: Path) -> List[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _is_violation(src_layer: str, dst_module: str) -> bool:
    if not dst_module.startswith("orket."):
        return False

    dst_layer = _layer_for_module(dst_module)

    # Tiered volatility architecture rules.
    if src_layer == "core" and dst_layer in {"application", "adapters", "interfaces"}:
        return True
    if src_layer == "application" and dst_layer == "interfaces":
        return True
    if src_layer == "adapters" and dst_layer == "interfaces":
        return True

    if src_layer == "domain" and dst_layer in {"orchestration", "interfaces"}:
        return True
    if src_layer == "decision_nodes" and dst_layer == "interfaces":
        return True
    if src_layer == "infrastructure" and dst_layer in {"services", "orchestration", "interfaces", "decision_nodes"}:
        return True
    return False


def main() -> None:
    violations: List[Tuple[str, str]] = []

    for py_path in PACKAGE_ROOT.rglob("*.py"):
        if "__pycache__" in py_path.parts:
            continue
        src_module = _module_from_path(py_path)
        src_layer = _layer_for_module(src_module)

        for imported in _imports_for_file(py_path):
            if _is_violation(src_layer, imported):
                violations.append((src_module, imported))

    if violations:
        print("Dependency direction violations found:")
        for src, dst in sorted(set(violations)):
            print(f"- {src} -> {dst}")
        raise SystemExit(1)

    print("Dependency direction check passed.")


if __name__ == "__main__":
    main()
