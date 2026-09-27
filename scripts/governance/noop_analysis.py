"""Bounded binding-aware analysis of executable empty function bodies."""

from __future__ import annotations

import ast
from typing import Any


def noop_reason(body: list[ast.stmt]) -> str | None:
    reasons = []
    for statement in body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            reasons.append("ellipsis" if statement.value.value is Ellipsis else "empty_body")
        elif isinstance(statement, ast.Pass):
            reasons.append("pass_statement")
        elif isinstance(statement, ast.Return) and (
            statement.value is None or isinstance(statement.value, ast.Constant) and statement.value.value is None
        ):
            reasons.append("return_none")
        elif isinstance(statement, ast.AnnAssign) and statement.value is None and isinstance(statement.target, ast.Name):
            reasons.append("empty_body")
        else:
            return None
    for reason in ("return_none", "ellipsis", "pass_statement", "empty_body"):
        if reason in reasons:
            return reason
    return None


class NoopVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.bindings: dict[str, str | None] = {}
        self.class_body = False
        self.protocol_body = False
        self.abstract_body = False
        self.findings: list[dict[str, Any]] = []
        self.unsafe_globals: set[str] = set()
        self.class_lexical: dict[str, str | None] | None = None

    def _resolve(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return self.bindings.get(node.id) if node.id not in self.unsafe_globals else None
        if isinstance(node, ast.Attribute):
            prefix = self._resolve(node.value)
            return f"{prefix}.{node.attr}" if prefix else None
        return None

    def _block(self, body: list[ast.stmt]) -> None:
        for statement in body:
            self.visit(statement)

    def visit_Module(self, node: ast.Module) -> None:
        # Function bodies resolve globals when called, potentially after a later
        # rebinding. Such names cannot justify a declaration exemption.
        self.unsafe_globals = _reassigned_names(node)
        self._block(node.body)

    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.TryStar, ast.Match)):
            super().generic_visit(node)
            return
        before = self.bindings.copy()
        super().generic_visit(node)
        # A zero-iteration loop or exceptional branch cannot establish an import.
        self.bindings = {name: target if self.bindings.get(name) == target else None for name, target in before.items()}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.bindings[alias.asname or alias.name.partition(".")[0]] = alias.name if alias.asname else alias.name.partition(".")[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                self.bindings.clear()
            else:
                self.bindings[alias.asname or alias.name] = f"{node.module}.{alias.name}" if not node.level else None

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bindings[node.id] = None

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            base = node.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                self.bindings[base.id] = None
        self.generic_visit(node)

    def _guard_value(self, node: ast.AST) -> bool | None:
        if self._resolve(node) in {"typing.TYPE_CHECKING", "typing_extensions.TYPE_CHECKING"}:
            return False
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = self._guard_value(node.operand)
            return None if value is None else not value
        return None

    def visit_If(self, node: ast.If) -> None:
        value = self._guard_value(node.test)
        if value is not None:
            self._block(node.body if value else node.orelse)
            return
        before = self.bindings.copy()
        self._block(node.body)
        first = self.bindings
        self.bindings = before.copy()
        self._block(node.orelse)
        self.bindings = {name: target if self.bindings.get(name) == target else None for name, target in first.items()}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = [base.value if isinstance(base, ast.Subscript) else base for base in node.bases]
        protocol = any(self._resolve(base) in {"typing.Protocol", "typing_extensions.Protocol"} for base in bases)
        abstract = protocol or any(self._resolve(base) in {"abc.ABC", "<abstract-class>"} for base in bases)
        abstract = abstract or any(kw.arg == "metaclass" and self._resolve(kw.value) == "abc.ABCMeta" for kw in node.keywords)
        self.bindings[node.name] = None
        outer, class_body, protocol_body = self.bindings, self.class_body, self.protocol_body
        abstract_body = self.abstract_body
        lexical = self.class_lexical
        self.class_lexical = lexical if class_body else outer
        self.bindings = self.class_lexical.copy()
        self.class_body, self.protocol_body = True, protocol
        self.abstract_body = abstract
        self._block(node.body)
        self.bindings, self.class_body, self.protocol_body = outer, class_body, protocol_body
        self.class_lexical = lexical
        self.abstract_body = abstract_body
        self.bindings[node.name] = "<abstract-class>" if abstract else None

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        reason = noop_reason(node.body)
        abstract = self.class_body and self.abstract_body and any(
            self._resolve(mark) == "abc.abstractmethod" for mark in node.decorator_list
        )
        declaration = self.class_body and self.protocol_body and reason in {"ellipsis", "pass_statement", "empty_body"}
        if reason is not None and not abstract and not declaration:
            self.findings.append({
                "line": node.lineno, "name": node.name, "reason": reason,
                "async": isinstance(node, ast.AsyncFunctionDef),
            })
        self.bindings[node.name] = None
        outer, class_body, protocol_body = self.bindings, self.class_body, self.protocol_body
        self.bindings = (self.class_lexical if class_body else outer).copy()
        # A local binding shadows an outer import throughout a Python function.
        for name in _local_names(node):
            self.bindings[name] = None
        self.class_body = self.protocol_body = False
        self._block(node.body)
        self.bindings, self.class_body, self.protocol_body = outer, class_body, protocol_body

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function


def _local_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names = {arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
    names.update(arg.arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None)
    pending: list[ast.AST] = list(node.body)
    while pending:
        child = pending.pop()
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(child.name)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            names.add(child.id)
        elif isinstance(child, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.partition(".")[0] for alias in child.names)
        else:
            pending.extend(ast.iter_child_nodes(child))
    return names


def _reassigned_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    imports: dict[str, set[str]] = {}
    pending: list[ast.AST] = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                local = alias.asname or alias.name.partition(".")[0]
                qualified = f"{node.module}.{alias.name}" if isinstance(node, ast.ImportFrom) else alias.name
                imports.setdefault(local, set()).add(qualified)
        else:
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                names.add(node.id)
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
                base = node.value
                while isinstance(base, ast.Attribute):
                    base = base.value
                if isinstance(base, ast.Name):
                    names.add(base.id)
            pending.extend(ast.iter_child_nodes(node))
    names.update(name for name, targets in imports.items() if len(targets) > 1)
    names.update(name for node in ast.walk(tree) if isinstance(node, ast.Global) for name in node.names)
    return names & set(imports)
