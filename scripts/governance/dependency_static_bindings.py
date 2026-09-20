"""Conservative static binding facts shared by bounded dynamic-route analysis."""
from __future__ import annotations

import ast
from collections import Counter

from scripts.governance.dependency_dynamic_imports import import_aliases, resolve


def static_bindings(tree: ast.AST) -> Counter[str]:
    counts: Counter[str] = Counter()
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            counts[node.name] += 1
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            counts[node.id] += 1
        elif isinstance(node, ast.arg):
            counts[node.arg] += 1
        elif isinstance(node, ast.ExceptHandler) and node.name:
            counts[node.name] += 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for item in node.names:
                name = item.asname or item.name.split('.')[0]
                origin = (item.name if item.asname else name) if isinstance(node, ast.Import) else (
                    '.' * node.level + (node.module or '') + '.' + item.name
                )
                if (name, origin) not in imports:
                    counts[name] += 1
                    imports.add((name, origin))
    return counts

def positional_parameters(node: ast.FunctionDef) -> list[str] | None:
    arguments = node.args
    if node.decorator_list or arguments.vararg or arguments.kwarg or arguments.kwonlyargs:
        return None
    try:
        for value in arguments.defaults:
            ast.literal_eval(value)
    except (ValueError, TypeError):
        return None
    return [item.arg for item in (*arguments.posonlyargs, *arguments.args)]

def unambiguous_definitions(trees: dict[str, ast.Module], definitions: dict) -> dict:
    """A definition or its module namespace cannot escape and still prove a binding."""
    invalid = set()
    modules = {name.rsplit('.', 1)[0] for name in definitions}
    for module, tree in trees.items():
        aliases = import_aliases(tree)
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            origins = {name.removeprefix('loaded:') for name in resolve(node, aliases)}
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                origins.add(module + '.' + node.id)
            parent = parents.get(node)
            for name in origins & definitions.keys():
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    invalid.add(name)
            for name in origins & modules:
                attribute_read = (isinstance(parent, ast.Attribute) and parent.value is node
                                  and isinstance(parent.ctx, ast.Load) and parent.attr != '__dict__')
                if not attribute_read:
                    invalid.update(key for key in definitions if key.rsplit('.', 1)[0] == name)
    return {name: contract for name, contract in definitions.items() if name not in invalid}


def builtin_bindings_are_known(trees: dict[str, ast.Module], names: set[str]) -> bool:
    """Builtin guards are unavailable if their namespace can be changed or escape."""
    protected = {'builtins.' + name for name in names}
    for tree in trees.values():
        aliases = import_aliases(tree)
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            origins = {name.removeprefix('loaded:') for name in resolve(node, aliases)}
            if origins & protected and isinstance(getattr(node, 'ctx', None), (ast.Store, ast.Del)):
                return False
            if 'builtins' not in origins:
                continue
            parent = parents.get(node)
            if not (isinstance(parent, ast.Attribute) and parent.value is node and parent.attr != '__dict__'):
                return False
            if not isinstance(parent.ctx, ast.Load) and parent.attr in names:
                return False
    return True
