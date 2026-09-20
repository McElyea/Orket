"""Recognize narrowly proven import interception without waiving unknown routes."""
from __future__ import annotations

import ast
from collections import Counter

from scripts.governance.dependency_dynamic_imports import import_aliases, resolve
from scripts.governance.dependency_static_bindings import (
    positional_parameters,
    static_bindings,
    unambiguous_definitions,
)

_ARITIES = {"builtins.__import__": 5, "importlib.import_module": 2}


def _validation_prefix(statements: list[ast.stmt], validators: set[str], parameters: set[str]) -> bool:
    conditions = (ast.Compare, ast.BoolOp, ast.UnaryOp, ast.Name, ast.Constant, ast.Load,
                  ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.And, ast.Or, ast.Not)
    for node in statements:
        if isinstance(node, ast.If):
            if any(not isinstance(part, conditions) for part in ast.walk(node.test)):
                return False
            if not _validation_prefix(node.body + node.orelse, validators, parameters):
                return False
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                    and call.func.value.id in validators and not call.keywords
                    and all(isinstance(arg, ast.Name) and arg.id in parameters for arg in call.args)):
                return False
        else:
            return False
    return True


def _factory(node: ast.FunctionDef) -> tuple[int, int, int] | None:
    outer = positional_parameters(node)
    if outer is None or len(node.body) != 2:
        return None
    inner, returned = node.body
    if not (isinstance(inner, ast.FunctionDef) and isinstance(returned, ast.Return)
            and isinstance(returned.value, ast.Name) and returned.value.id == inner.name):
        return None
    parameters = positional_parameters(inner)
    if parameters is None or not inner.body or not isinstance(inner.body[-1], ast.Return):
        return None
    call = inner.body[-1].value
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id in outer and call.func.id not in parameters and not call.keywords
            and len(call.args) == len(parameters)
            and all(isinstance(arg, ast.Name) and arg.id == name
                    for arg, name in zip(call.args, parameters, strict=True))):
        return None
    captured = call.func.id
    uses = [part for part in ast.walk(node) if isinstance(part, ast.Name) and part.id == captured]
    if uses != [call.func] or any(isinstance(part, ast.Name) and not isinstance(part.ctx, ast.Load)
                                for part in ast.walk(inner)):
        return None
    validators = set(outer) - {captured} - set(parameters)
    if not _validation_prefix(inner.body[:-1], validators, set(parameters)):
        return None
    return outer.index(captured), len(parameters), len(outer)


def _installation(node: ast.Assign, module: str, aliases: dict, bindings: Counter, factories: dict) -> dict | None:
    if len(node.targets) != 1 or not isinstance(node.value, ast.Call):
        return None
    target, call = node.targets[0], node.value
    if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
            and bindings[target.value.id] == 1 and isinstance(call.func, ast.Name)
            and bindings[call.func.id] == 1 and not call.keywords):
        return None
    targets = resolve(target, aliases)
    if len(targets) != 1 or not targets <= _ARITIES.keys():
        return None
    target_name = next(iter(targets))
    candidates = resolve(call.func, aliases) or {module + '.' + call.func.id}
    if len(candidates) != 1 or (factory_name := next(iter(candidates))) not in factories:
        return None
    index, arity, outer_arity = factories[factory_name]
    if arity != _ARITIES[target_name] or len(call.args) != outer_arity or any(
        isinstance(arg, ast.Starred) for arg in call.args
    ):
        return None
    argument = call.args[index]
    if not isinstance(argument, (ast.Name, ast.Attribute)) or resolve(argument, aliases) != targets:
        return None
    names = [part.id for part in ast.walk(argument) if isinstance(part, ast.Name)]
    if any(bindings[name] != 1 for name in names):
        return None
    return {"nodes": {id(target), id(argument)}, "line": node.lineno,
            "kind": "importer_interception", "target": target_name,
            "factory": factory_name, "forwarded_arguments": arity}


def importer_interceptions(trees: dict[str, ast.Module]) -> dict[str, list[dict]]:
    """Inspect actual factory bodies, then match only exact standard-hook installations."""
    bindings = {name: static_bindings(tree) for name, tree in trees.items()}
    factories = {}
    for module, tree in trees.items():
        for node in tree.body:
            if (isinstance(node, ast.FunctionDef) and bindings[module][node.name] == 1
                    and (contract := _factory(node)) is not None):
                factories[module + '.' + node.name] = contract
    factories = unambiguous_definitions(trees, factories)
    result = {}
    for module, tree in trees.items():
        aliases = import_aliases(tree)
        result[module] = [match for node in ast.walk(tree) if isinstance(node, ast.Assign)
                          if (match := _installation(node, module, aliases, bindings[module], factories)) is not None]
    return result
