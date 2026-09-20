"""One Git-visible, encoding-aware import inventory for dependency governance."""

from __future__ import annotations

import ast
import hashlib
import io
import tokenize
from pathlib import Path

from scripts.common.git_inventory import git_list_files
from scripts.governance.dependency_dynamic_imports import dynamic_observations, literal_forwarding_targets
from scripts.governance.dependency_external_names import external_module_routes
from scripts.governance.dependency_importer_interception import importer_interceptions


def module_from_path(path: Path, root: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def _index(paths: list[Path], root: Path) -> dict[str, str]:
    result = {}
    for path in paths:
        module = module_from_path(path, root)
        parts = module.split(".")
        for length in range(1, len(parts)):
            prefix = ".".join(parts[:length])
            result.setdefault(prefix, prefix)
        result.setdefault(module, module)
    # Python imports a package before a same-named .py file; inventory keeps both.
    for module in list(result):
        if module.endswith(".__init__"):
            result[module.removesuffix(".__init__")] = module
    return result


def _from_targets(
    node: ast.ImportFrom, package: str, known: dict[str, str], exports: dict[str, set[str]]
) -> tuple[list[str], str | None]:
    if any(item.name == "*" for item in node.names):
        return [], "unresolved_star_import"
    prefix = node.module or ""
    if node.level:
        parts = package.split(".")
        if node.level > len(parts):
            return [], "relative_import_beyond_package"
        prefix = ".".join(parts[: len(parts) - node.level + 1] + ([prefix] if prefix else []))
    targets = [prefix]
    unresolved = []
    for item in node.names:
        child = prefix + "." + item.name
        if child in known:
            targets.append(child)
        elif (prefix == "orket" or prefix.startswith("orket.")) and item.name not in exports.get(
            known.get(prefix), set()
        ):
            unresolved.append(child)
    return targets, "unresolved_local_member:" + ",".join(unresolved) if unresolved else None


def _read_source(path: Path) -> tuple[ast.Module | None, str | None, list[dict]]:
    digest = None
    try:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return ast.parse(raw.decode(encoding), filename=str(path)), digest, []
    except (SyntaxError, UnicodeError, LookupError, OSError) as exc:
        return (
            None,
            digest,
            [{"line": getattr(exc, "lineno", 0), "code": "source_parse_or_read_error", "detail": str(exc)}],
        )


def _exported_names(tree: ast.AST) -> set[str]:
    names, stack = set(), list(ast.iter_child_nodes(tree))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(item.asname or item.name.split(".")[0] for item in node.names)
        stack.extend(ast.iter_child_nodes(node))
    return names


def _imports_for_tree(
    tree: ast.AST, path: Path, root: Path, known: dict[str, str], exports: dict[str, set[str]],
    interceptions: list[dict],
) -> tuple[list[dict], list[dict]]:
    module = module_from_path(path, root)
    package = module.rsplit(".", 1)[0]
    relative = path.relative_to(root).as_posix()
    imports, failures = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, item.name, "import") for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            names, error = _from_targets(node, package, known, exports)
            imports.extend((node.lineno, name, "from") for name in names)
            if error:
                failures.append((node.lineno, error))
    intercepted = frozenset(identity for row in interceptions if row["kind"] == "importer_interception"
                            for identity in row["nodes"])
    external = frozenset(identity for row in interceptions if row["kind"] != "importer_interception"
                         for identity in row["nodes"])
    dynamic, errors = dynamic_observations(tree, module.removesuffix(".__init__"),
                                         intercepted_nodes=intercepted, external_nodes=external)
    imports.extend((line, name, "dynamic") for line, name in dynamic)
    failures.extend(errors)
    edges = []
    for line, name, kind in sorted(set(imports)):
        if name != "orket" and not name.startswith("orket."):
            continue
        target = known.get(name)
        if target is None:
            failures.append((line, "unresolved_local_import:" + name))
            target = name
        edges.append({"source": module, "target": target, "path": relative, "line": line, "kind": kind})
    return edges, [{"path": relative, "line": line, "code": code} for line, code in sorted(set(failures))]


def scan_dependencies(root: Path) -> dict:
    root = root.resolve(strict=True)
    paths = [p for p in git_list_files(root) if p.suffix == ".py" and p.is_relative_to(root / "orket")]
    if not paths:
        raise ValueError("No Git-visible Python files in the required orket scan root")
    known = _index(paths, root)
    modules, trees, edges, errors = {}, {}, [], []
    for path in paths:
        tree, digest, failures = _read_source(path)
        module, relative = module_from_path(path, root), path.relative_to(root).as_posix()
        modules[module] = {"path": relative, "sha256": digest}
        errors.extend({"path": relative, **row} for row in failures)
        if tree is not None:
            trees[path] = tree
    exports = {module_from_path(p, root): _exported_names(tree) for p, tree in trees.items()}
    forwarding = {module_from_path(p, root): literal_forwarding_targets(tree) for p, tree in trees.items()}
    changed = True
    while changed:
        changed = False
        for module, targets in forwarding.items():
            additional = set().union(*(exports.get(known.get(t), set()) for t in targets)) - exports[module]
            if additional:
                exports[module].update(additional)
                changed = True
    interceptions = importer_interceptions({module_from_path(p, root): tree for p, tree in trees.items()})
    external = external_module_routes({module_from_path(p, root): tree for p, tree in trees.items()}, namespace="orket")
    resolved = []
    for path, tree in trees.items():
        matches = interceptions[module_from_path(path, root)] + external[module_from_path(path, root)]
        found, failures = _imports_for_tree(tree, path, root, known, exports, matches)
        edges.extend(found)
        errors.extend(failures)
        resolved.extend({"path": path.relative_to(root).as_posix(), **{k: v for k, v in row.items() if k != "nodes"}}
                        for row in matches)
    after = [p for p in git_list_files(root) if p.suffix == ".py" and p.is_relative_to(root / "orket")]
    if after != paths:
        errors.append({"path": "orket", "line": 0, "code": "source_inventory_changed_during_scan"})
    for row in modules.values():
        if row["sha256"] is not None and hashlib.sha256((root / row["path"]).read_bytes()).hexdigest() != row["sha256"]:
            errors.append({"path": row["path"], "line": 0, "code": "source_changed_during_scan"})
    return {
        "modules": modules,
        "edges": edges,
        "analysis_errors": errors,
        "resolved_dynamic_routes": resolved,
        "files_scanned": len(paths),
        "scan_roots": ["orket"],
        "scope": "Git-visible declared imports and recognized dynamic routes; conservative static evidence, not a runtime call graph or hostile-code containment",
    }
