"""Conservative dynamic import recognition; unresolved routes are diagnostics."""

from __future__ import annotations

import ast

IMPORTERS = frozenset(
    {
        "importlib.import_module",
        "builtins.__import__",
        "importlib.util.find_spec",
        "pkgutil.resolve_name",
        "runpy.run_module",
    }
)
CODE_LOADERS = frozenset(
    {
        "builtins.exec",
        "builtins.eval",
        "runpy.run_path",
        "importlib.util.spec_from_file_location",
        "importlib.machinery.SourceFileLoader",
    }
)
REFLECTION = frozenset({"builtins.globals", "builtins.locals", "builtins.vars"})
IMPORT_NAMESPACES = frozenset({"importlib", "importlib.util", "importlib.machinery", "builtins", "pkgutil", "runpy"})
NAMESPACES = IMPORT_NAMESPACES | frozenset({"importlib.__dict__", "builtins.__dict__", "sys.modules"})
TRACKED = IMPORTERS | CODE_LOADERS | REFLECTION | NAMESPACES | frozenset({"builtins.getattr", "sys"})


def literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = literal_string(node.left), literal_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _loaded_module_origins(name: str) -> set[str]:
    # Loading a known importer module must retain its callable identity.
    return {"loaded:" + name} | ({name} if name in IMPORT_NAMESPACES else set())


def resolve(node: ast.AST, aliases: dict[str, set[str]]) -> set[str]:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, set()) if isinstance(node.ctx, ast.Load) else set()
    if isinstance(node, ast.Attribute):
        return {n + "." + node.attr for n in resolve(node.value, aliases)}
    if isinstance(node, ast.Subscript):
        key = literal_string(node.slice)
        if key is not None:
            origins = resolve(node.value, aliases)
            found = {n.removesuffix(".__dict__") + "." + key for n in origins - {"sys.modules"}}
            return found | (_loaded_module_origins(key) if "sys.modules" in origins else set())
    if isinstance(node, ast.Call) and "builtins.getattr" in resolve(node.func, aliases) and len(node.args) >= 2:
        key = literal_string(node.args[1])
        if key is not None:
            return {n + "." + key for n in resolve(node.args[0], aliases)}
    if isinstance(node, ast.Call) and (calls := resolve(node.func, aliases)) & IMPORTERS:
        name = literal_string(_argument(node, 0, "mod_name" if "runpy.run_module" in calls else "name"))
        if name is not None and not name.startswith("."):
            origins = _loaded_module_origins(name)
            if "builtins.__import__" in calls and name.partition(".")[0] in IMPORT_NAMESPACES:
                origins.add(name.partition(".")[0])
            return origins
    if isinstance(node, ast.Call) and node.args:
        getters = resolve(node.func, aliases) & {"builtins.get", "builtins.__dict__.get", "importlib.__dict__.get"}
        key = literal_string(node.args[0])
        if getters and key is not None:
            return {n.removesuffix(".get").removesuffix(".__dict__") + "." + key for n in getters}
    return set()


def import_aliases(tree: ast.AST) -> dict[str, set[str]]:
    aliases = {
        name: {"builtins." + name} for name in ("__import__", "exec", "eval", "globals", "locals", "vars", "getattr")
    }
    aliases["__builtins__"] = {"builtins"}
    nodes = list(ast.walk(tree))
    loaded = {
        "loaded:" + value
        for n in nodes
        if isinstance(n, ast.Call) and n.args
        if (value := literal_string(n.args[0])) is not None
    }
    for node in nodes:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases.setdefault(item.asname or item.name.split(".")[0], set()).add(
                    item.name if item.asname else item.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            for item in node.names:
                aliases.setdefault(item.asname or item.name, set()).add(node.module + "." + item.name)
    # Union across scopes is deliberately conservative: rebinding cannot hide a loader.
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
                targets, value = [node.target], node.value
            else:
                continue
            if value is None:
                continue
            origins = resolve(value, aliases) & (TRACKED | loaded)
            for target in targets:
                if isinstance(target, ast.Name) and origins - aliases.get(target.id, set()):
                    aliases.setdefault(target.id, set()).update(origins)
                    changed = True
    return aliases


def _argument(node: ast.Call, index: int, keyword: str) -> ast.AST | None:
    if len(node.args) > index:
        return node.args[index]
    return next((item.value for item in node.keywords if item.arg == keyword), None)


def dynamic_target(node: ast.Call, origins: set[str], package: str) -> tuple[list[str], str | None]:
    name = literal_string(_argument(node, 0, "name" if "runpy.run_module" not in origins else "mod_name"))
    if name is None:
        return [], "unresolved_dynamic_import"
    if name.startswith("."):
        explicit = literal_string(_argument(node, 1, "package"))
        if not explicit or "importlib.import_module" not in origins:
            return [], "unresolved_relative_dynamic_import"
        from importlib.util import resolve_name

        try:
            name = resolve_name(name, explicit)
        except (ImportError, ValueError):
            return [], "invalid_relative_dynamic_import"
    targets = [name.partition(":")[0]]
    if "builtins.__import__" in origins:
        level = _argument(node, 4, "level")
        if level is not None and not (isinstance(level, ast.Constant) and level.value == 0):
            return targets, "unresolved_builtin_import_level"
        names = _argument(node, 3, "fromlist")
        if names is not None:
            if not isinstance(names, (ast.List, ast.Tuple)) or any(literal_string(n) is None for n in names.elts):
                return targets, "unresolved_dynamic_fromlist"
            targets.extend(name + "." + literal_string(n) for n in names.elts)
    return targets, None


def dynamic_observations(
    tree: ast.AST, module: str, *, intercepted_nodes: frozenset[int] = frozenset(),
    external_nodes: frozenset[int] = frozenset(),
) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    aliases = import_aliases(tree)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    targets, errors = [], []
    for node in ast.walk(tree):
        origins = resolve(node, aliases)
        if isinstance(node, ast.Call):
            calls = resolve(node.func, aliases)
            if calls & IMPORTERS and id(node) not in external_nodes:
                found, error = dynamic_target(node, calls, module)
                targets.extend((node.lineno, name) for name in found)
                if error:
                    errors.append((node.lineno, error))
            if (
                calls & CODE_LOADERS
                or isinstance(node.func, ast.Attribute)
                and node.func.attr in {"exec_module", "load_module"}
            ):
                errors.append((node.lineno, "dynamic_code_loading"))
            if calls & REFLECTION:
                errors.append((node.lineno, "unresolved_reflection"))
            if (
                "builtins.getattr" in calls
                and node.args
                and resolve(node.args[0], aliases) & IMPORT_NAMESPACES
                and (len(node.args) < 2 or literal_string(node.args[1]) is None)
            ):
                errors.append((node.lineno, "unresolved_import_attribute"))
        if origins & IMPORTERS and id(node) not in intercepted_nodes:
            parent = parents.get(node)
            called = isinstance(parent, ast.Call) and parent.func is node
            assigned = (
                isinstance(parent, ast.Assign)
                and parent.value is node
                and all(isinstance(t, ast.Name) for t in parent.targets)
            ) or (
                isinstance(parent, (ast.AnnAssign, ast.NamedExpr))
                and parent.value is node
                and isinstance(parent.target, ast.Name)
            )
            nested = isinstance(parent, ast.Attribute) and parent.value is node
            if not called and not assigned and not nested:
                errors.append((getattr(node, "lineno", 0), "importer_escape"))
        found, failures = _registry_reads(node, aliases, module)
        targets.extend(found)
        errors.extend(failures)
        if id(node) not in external_nodes:
            errors.extend(_unresolved_namespaces(node, parents.get(node), aliases))
    return sorted(set(targets)), sorted(set(errors))


def _module_name(node: ast.AST, module: str) -> str | None:
    if isinstance(node, ast.Name) and node.id == "__name__":
        return module
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and node.slice.value == 0:
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "rsplit"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "__name__"
            and len(call.args) == 2
            and literal_string(call.args[0]) == "."
            and isinstance(call.args[1], ast.Constant)
            and call.args[1].value == 1
            and not call.keywords
        ):
            return module.rsplit(".", 1)[0]
    return literal_string(node)


def _registry_reads(node: ast.AST, aliases: dict[str, set[str]], module: str) -> tuple[list, list]:
    if not isinstance(node, ast.Subscript) or "sys.modules" not in resolve(node.value, aliases):
        return [], []
    name = _module_name(node.slice, module)
    if name == module:
        return [], []
    if name is not None:
        return [(node.lineno, name)], []
    if isinstance(node.slice, ast.Attribute) and node.slice.attr == "__name__":
        names = {n.removeprefix("loaded:") for n in resolve(node.slice.value, aliases) if n.startswith("loaded:")}
        if names:
            return [(node.lineno, n) for n in names], []
    return [], [(node.lineno, "unresolved_module_registry")]


def literal_forwarding_targets(tree: ast.AST) -> set[str]:
    aliases = import_aliases(tree)
    targets = set()
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Subscript)
            and "sys.modules" in resolve(target.value, aliases)
            and isinstance(target.slice, ast.Name)
            and target.slice.id == "__name__"
        ):
            targets.update(n.removeprefix("loaded:") for n in resolve(node.value, aliases) if n.startswith("loaded:"))
    return targets


def _unresolved_namespaces(
    node: ast.AST, parent: ast.AST | None, aliases: dict[str, set[str]]
) -> list[tuple[int, str]]:
    errors = []
    if (
        isinstance(node, ast.Subscript)
        and resolve(node.value, aliases) & (NAMESPACES - {"sys.modules"})
        and literal_string(node.slice) is None
    ):
        errors.append((node.lineno, "unresolved_import_attribute"))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
        origins = resolve(node.func.value, aliases)
        if "sys.modules" in origins:
            errors.append((node.lineno, "unresolved_module_registry"))
        elif origins & NAMESPACES and (not node.args or literal_string(node.args[0]) is None):
            errors.append((node.lineno, "unresolved_import_attribute"))
    if resolve(node, aliases) & NAMESPACES:
        accessor = isinstance(parent, (ast.Attribute, ast.Subscript)) and parent.value is node
        assigned = (
            isinstance(parent, ast.Assign)
            and parent.value is node
            and all(isinstance(t, ast.Name) for t in parent.targets)
        )
        getter = isinstance(parent, ast.Call) and "builtins.getattr" in resolve(parent.func, aliases)
        if not accessor and not assigned and not getter:
            errors.append((getattr(node, "lineno", 0), "import_namespace_escape"))
    return errors
