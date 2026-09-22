"""Static adapter declarations and admission checks over the canonical source inventory."""

from __future__ import annotations

import ast

from scripts.governance.dependency_policy import DependencyPolicy


def _contains_flag(target: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Name) and node.id == "side_effecting" and isinstance(node.ctx, (ast.Store, ast.Del))
        for node in ast.walk(target)
    )


def _scope_declarations(body: list[ast.stmt]) -> list[dict]:
    found = []
    pending = [(node, True) for node in reversed(body)]
    while pending:
        node, direct = pending.pop()
        targets, value, kind = [], None, type(node).__name__
        if isinstance(node, ast.Lambda):
            pending.append((node.args, False))
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == "side_effecting":
                found.append(dict(line=node.lineno, kind=kind, direct=direct, literal=None))
            # Defaults, decorators and bases execute in the enclosing scope. Bodies do not.
            body_nodes = {id(statement) for statement in node.body}
            pending.extend(
                (child, False) for child in reversed(list(ast.iter_child_nodes(node))) if id(child) not in body_nodes
            )
            continue
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets, value = [node.target], node.value
        elif isinstance(node, ast.Delete):
            targets = node.targets
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            targets = [node.target]
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            targets = [node.optional_vars]
        if any(_contains_flag(target) for target in targets):
            direct_name = any(isinstance(target, ast.Name) and target.id == "side_effecting" for target in targets)
            literal = (
                value.value if direct_name and isinstance(value, ast.Constant) and type(value.value) is bool else None
            )
            found.append(dict(line=getattr(node, "lineno", 0), kind=kind, direct=direct, literal=literal))
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
            (alias.asname or alias.name.split(".")[0]) == "side_effecting" for alias in node.names
        ):
            found.append(dict(line=node.lineno, kind=kind, direct=direct, literal=None))
        if isinstance(node, ast.ExceptHandler) and node.name == "side_effecting":
            found.append(dict(line=node.lineno, kind=kind, direct=direct, literal=None))
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == "side_effecting":
            found.append(dict(line=node.lineno, kind=kind, direct=direct, literal=None))
        if isinstance(node, ast.MatchMapping) and node.rest == "side_effecting":
            found.append(dict(line=node.lineno, kind=kind, direct=direct, literal=None))
        pending.extend((child, False) for child in reversed(list(ast.iter_child_nodes(node))))
    return sorted(found, key=lambda row: (row["line"], row["kind"]))


def effect_declarations(tree: ast.Module) -> dict:
    """Observe source syntax without importing adapters or acquiring their resources."""
    return {
        "module": _scope_declarations(tree.body),
        "classes": {
            f"{node.name}@{node.lineno}": _scope_declarations(node.body)
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        },
    }


def _literal(declarations: list[dict]) -> bool | None:
    if len(declarations) != 1:
        return None
    declaration = declarations[0]
    if declaration["direct"] and declaration["kind"] in {"Assign", "AnnAssign"}:
        return declaration["literal"]
    return None


def _decision_reachability(target: str, edges: list[dict], effects: dict[str, bool | None]) -> list[dict]:
    forward = {}
    for row in edges:
        forward.setdefault(row["source"], set()).add(row["target"])
    pending, seen, failures = [(target, [target])], set(), []
    while pending:
        current, trail = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        if current in effects and effects[current] is not False:
            failures.append(
                dict(code="decision_adapter_reaches_effectful_adapter", module=target, target=current, trail=trail)
            )
        pending.extend((child, [*trail, child]) for child in sorted(forward.get(current, ()), reverse=True))
    return failures


def evaluate_adapter_effects(observed: dict, policy: DependencyPolicy) -> dict:
    effects, rows, violations = {}, [], []
    declarations = observed.get("effect_declarations", {})
    for module, source in sorted(observed["modules"].items()):
        try:
            layer = policy.layer_for_module(module)
        except ValueError:
            continue  # The existing dependency verdict separately refuses unknown modules.
        if layer != "adapters":
            continue
        facts = declarations.get(module, {"module": [], "classes": {}})
        value = _literal(facts["module"])
        effects[module] = value
        rows.append(
            dict(module=module, path=source["path"], sha256=source["sha256"], side_effecting=value, declarations=facts)
        )
        if value is None:
            violations.append(
                dict(
                    code="adapter_effect_declaration_invalid", module=module, path=source["path"], sites=facts["module"]
                )
            )
        for name, sites in facts["classes"].items():
            class_value = _literal(sites)
            if sites and (class_value is None or (value is False and class_value is True)):
                violations.append(
                    dict(
                        code="adapter_class_effect_declaration_invalid",
                        module=module,
                        path=source["path"],
                        class_name=name,
                        sites=sites,
                    )
                )
    for target in sorted(policy.side_effect_free_adapters):
        if effects.get(target) is not False:
            violations.append(dict(code="decision_adapter_requires_false", module=target))
        violations.extend(_decision_reachability(target, observed["edges"], effects))
    return dict(
        modules=rows,
        violations=violations,
        scope="Declared effect bounds and static repository admission; not behavioral purity or a runtime effect system",
    )
