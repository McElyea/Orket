"""Git-visible size observations with explicit nested-definition context."""
from __future__ import annotations

import ast
import hashlib
import io
import tokenize
from pathlib import Path
from typing import Any

from scripts.common.git_inventory import GitInventoryError
from scripts.governance.quality_scan_inventory import git_visible_python_files

FILE_LIMIT = 400
FUNCTION_LIMIT = 70
_ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "head", "options", "trace",
                     "route", "api_route", "websocket", "websocket_route"}


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and (parent := _dotted_name(node.value)):
        return f"{parent}.{node.attr}"
    return None


def _direct_definition_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    pending, count = list(node.body), 0
    while pending:
        child = pending.pop()
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            count += 1
        else:
            pending.extend(ast.iter_child_nodes(child))
    return count


class _FunctionInventory(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.scopes: list[dict[str, str]] = []
        self.functions: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes.append({"kind": "class", "name": node.name})
        self.generic_visit(node)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        spans = int((node.end_lineno or node.lineno) - node.lineno + 1)
        route_syntax = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                name = _dotted_name(decorator.func)
                if name and name.rsplit(".", 1)[-1] in _ROUTE_DECORATORS:
                    route_syntax.append(name)
        self.functions.append({
            "path": self.path, "line": node.lineno, "name": node.name, "lines": spans,
            "qualified_name": ".".join([scope["name"] for scope in self.scopes] + [node.name]),
            "enclosing_scopes": [dict(scope) for scope in self.scopes],
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "route_decorator_syntax": route_syntax,
            "direct_nested_definitions": _direct_definition_count(node),
        })
        self.scopes.append({"kind": "function", "name": node.name})
        self.generic_visit(node)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def collect_architecture_sizes(repo_root: Path) -> dict[str, Any]:
    """Observe complete oversized inventories; inventory failures cannot pass."""
    repo_root = repo_root.resolve()
    files, functions, parse_errors, inventory_errors = [], [], [], []
    sources: dict[str, str] = {}
    try:
        selected = git_visible_python_files([repo_root / "orket"])
    except (GitInventoryError, OSError) as exc:
        selected = []
        inventory_errors.append(str(exc))
    if not selected and not inventory_errors:
        inventory_errors.append("scan_files_empty")
    for path in selected:
        relative = path.relative_to(repo_root).as_posix()
        try:
            raw = path.read_bytes()
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            source = raw.decode(encoding)
            tree = ast.parse(source, filename=relative)
        except (OSError, SyntaxError, UnicodeError) as exc:
            parse_errors.append({"path": relative, "error": str(exc)})
            continue
        sources[relative] = hashlib.sha256(raw).hexdigest()
        lines = len(source.splitlines())
        if lines > FILE_LIMIT:
            files.append({"path": relative, "lines": lines})
        visitor = _FunctionInventory(relative)
        visitor.visit(tree)
        functions.extend(row for row in visitor.functions if row["lines"] > FUNCTION_LIMIT)
    for relative, digest in sources.items():
        try:
            unchanged = hashlib.sha256((repo_root / relative).read_bytes()).hexdigest() == digest
        except OSError as exc:
            inventory_errors.append(f"{relative}: {exc}")
        else:
            if not unchanged:
                inventory_errors.append(f"source_changed_during_scan: {relative}")
    files.sort(key=lambda row: (-row["lines"], row["path"]))
    functions.sort(key=lambda row: (-row["lines"], row["path"], row["line"]))
    return {
        "schema_version": "architecture_size_inventory.v2", "proof": "structural_ast",
        "collection_ok": bool(selected) and not parse_errors and not inventory_errors,
        "inventory": "git_visible", "span_semantics": "inclusive_nested_definitions",
        "thresholds": {"file_lines": FILE_LIMIT, "function_lines": FUNCTION_LIMIT},
        "python_files_scanned": len(selected), "parsed_files_total": len(sources),
        "files_over_400_total": len(files), "functions_over_70_total": len(functions),
        "files_over_400": files, "functions_over_70": functions,
        "largest_files": files[:25], "largest_functions": functions[:25],
        "source_sha256": sources, "parse_errors": parse_errors, "inventory_errors": inventory_errors,
    }
