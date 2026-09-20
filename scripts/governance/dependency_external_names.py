"""Prove a narrow plain-string, absolute, outside-package import-name boundary."""
from __future__ import annotations

import ast

from scripts.governance.dependency_dynamic_imports import import_aliases, resolve
from scripts.governance.dependency_static_bindings import (
    builtin_bindings_are_known,
    positional_parameters,
    static_bindings,
    unambiguous_definitions,
)


def _plain_string(test: ast.AST, name: str) -> bool:
    return (isinstance(test, ast.Compare) and len(test.ops) == len(test.comparators) == 1
            and isinstance(test.ops[0], ast.IsNot) and isinstance(test.comparators[0], ast.Name)
            and test.comparators[0].id == 'str' and isinstance(test.left, ast.Call)
            and isinstance(test.left.func, ast.Name) and test.left.func.id == 'type'
            and not test.left.keywords and len(test.left.args) == 1
            and isinstance(test.left.args[0], ast.Name) and test.left.args[0].id == name)


def _excluded_names(test: ast.AST, name: str) -> set[tuple[str, str]] | None:
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
        parts = [_excluded_names(value, name) for value in test.values]
        return set().union(*parts) if all(part is not None for part in parts) else None
    if (isinstance(test, ast.Compare) and len(test.ops) == len(test.comparators) == 1
            and isinstance(test.ops[0], ast.Eq) and isinstance(test.left, ast.Name) and test.left.id == name
            and isinstance(test.comparators[0], ast.Constant) and isinstance(test.comparators[0].value, str)):
        return {('equal', test.comparators[0].value)}
    if (isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute) and test.func.attr == 'startswith'
            and isinstance(test.func.value, ast.Name) and test.func.value.id == name
            and not test.keywords and len(test.args) == 1 and isinstance(test.args[0], ast.Constant)
            and isinstance(test.args[0].value, str)):
        return {('prefix', test.args[0].value)}
    return None


def _validator(node: ast.FunctionDef, namespace: str, bindings: dict) -> bool:
    parameters = positional_parameters(node)
    if parameters is None or len(parameters) != 1 or bindings['type'] or bindings['str'] or len(node.body) < 3:
        return False
    name = parameters[0]
    returned = node.body[-1]
    if not (isinstance(returned, ast.Return) and isinstance(returned.value, ast.Name) and returned.value.id == name):
        return False
    plain, excluded = False, set()
    for index, statement in enumerate(node.body[:-1]):
        if not (isinstance(statement, ast.If) and not statement.orelse and len(statement.body) == 1
                and isinstance(statement.body[0], ast.Raise)):
            return False
        if _plain_string(statement.test, name):
            # Type rejection must dominate calls to overridable string methods.
            if index != 0:
                return False
            plain = True
        elif (names := _excluded_names(statement.test, name)) is not None:
            excluded.update(names)
        else:
            return False
    return plain and {('equal', namespace), ('prefix', namespace + '.'), ('prefix', '.')} <= excluded


def _call_identity(call: ast.Call, module: str, aliases: dict, bindings: dict) -> str | None:
    if not isinstance(call.func, ast.Name) or bindings[call.func.id] != 1:
        return None
    origins = resolve(call.func, aliases) or {module + '.' + call.func.id}
    return next(iter(origins)) if len(origins) == 1 else None


def _observe(node: ast.AST, facts: dict, aliases: dict, bindings: dict, rows: list[dict]) -> None:
    if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return
    if isinstance(node, ast.Call) and len(node.args) == 1 and not node.keywords:
        argument = node.args[0]
        if isinstance(argument, ast.Name) and argument.id in facts:
            origins = resolve(node.func, aliases)
            kind = None
            if origins == {'importlib.import_module'}:
                kind = 'external_module_import'
            elif (isinstance(node.func, ast.Attribute) and node.func.attr == 'get'
                  and resolve(node.func.value, aliases) == {'sys.modules'}):
                kind = 'external_module_cache_read'
            names = [part.id for part in ast.walk(node.func) if isinstance(part, ast.Name)]
            if kind and names and all(bindings[name] == 1 for name in names):
                rows.append(dict(nodes={id(node)}, line=node.lineno, kind=kind, validator=facts[argument.id]))
    for child in ast.iter_child_nodes(node):
        _observe(child, facts, aliases, bindings, rows)


def _unsafe_names(node: ast.AST) -> set[str]:
    return {name for part in ast.walk(node) if isinstance(part, (ast.Global, ast.Nonlocal)) for name in part.names}


def _walk_block(statements: list[ast.stmt], facts: dict, context: dict, unsafe: set[str], rows: list[dict]) -> None:
    module, aliases, bindings, validators = (context[k] for k in ('module', 'aliases', 'bindings', 'validators'))
    for statement in statements:
        for name in static_bindings(statement):
            facts.pop(name, None)
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _walk_block(statement.body, {}, context, _unsafe_names(statement), rows)
        elif isinstance(statement, ast.ClassDef):
            _walk_block(statement.body, {}, context, set(static_bindings(statement)), rows)
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            if value is not None:
                _observe(value, facts, aliases, bindings, rows)
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if (len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id not in unsafe
                    and isinstance(value, ast.Call) and len(value.args) == 1 and not value.keywords
                    and not isinstance(value.args[0], ast.Starred)
                    and (identity := _call_identity(value, module, aliases, bindings)) in validators):
                facts[targets[0].id] = identity
        elif isinstance(statement, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            expression = statement.test if isinstance(statement, (ast.If, ast.While)) else statement.iter
            _observe(expression, facts, aliases, bindings, rows)
            _walk_block(statement.body, dict(facts), context, unsafe, rows)
            _walk_block(statement.orelse, dict(facts), context, unsafe, rows)
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                _observe(item.context_expr, facts, aliases, bindings, rows)
            _walk_block(statement.body, dict(facts), context, unsafe, rows)
        elif isinstance(statement, (ast.Try, ast.TryStar)):
            for block in [statement.body, statement.orelse, statement.finalbody,
                          *(handler.body for handler in statement.handlers)]:
                _walk_block(block, dict(facts), context, unsafe, rows)
        elif not isinstance(statement, ast.Match):
            _observe(statement, facts, aliases, bindings, rows)


def external_module_routes(trees: dict[str, ast.Module], *, namespace: str) -> dict[str, list[dict]]:
    bindings = {name: static_bindings(tree) for name, tree in trees.items()}
    validators = {module + '.' + node.name: True for module, tree in trees.items() for node in tree.body
                  if isinstance(node, ast.FunctionDef) and bindings[module][node.name] == 1
                  and _validator(node, namespace, bindings[module])}
    validators = (unambiguous_definitions(trees, validators)
                  if builtin_bindings_are_known(trees, {'type', 'str'}) else {})
    result = {}
    for module, tree in trees.items():
        rows: list[dict] = []
        context = dict(module=module, aliases=import_aliases(tree), bindings=bindings[module], validators=validators)
        _walk_block(tree.body, {}, context, set(bindings[module]), rows)
        result[module] = [dict(row, excluded_namespace=namespace, plain_string=True, absolute_name=True) for row in rows]
    return result
