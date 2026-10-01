"""Observe documented argv and its source entrypoint without executing commands."""

from __future__ import annotations

import ast
import re
import shlex
import tomllib
from collections.abc import Callable
from pathlib import PurePosixPath

import yaml


def documented_commands(text: str, source: str) -> list[list[str]]:
    """Only Markdown code or actual YAML run bodies supply command declarations."""
    snippets: list[str] = []
    if source.endswith((".yml", ".yaml")):
        try:
            document = yaml.safe_load(text)
            for job in document.get("jobs", {}).values():
                for step in job.get("steps", []):
                    snippets.extend(str(step.get("run", "")).splitlines())
        except (yaml.YAMLError, AttributeError, TypeError) as exc:
            raise ValueError(f"invalid workflow command source: {source}") from exc
    else:
        fenced = False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                fenced = not fenced
            elif fenced:
                snippets.append(line.strip())
            else:
                snippets.extend(re.findall(r"`([^`\n]+)`", line))
    commands = []
    for snippet in snippets:
        try:
            tokens = shlex.split(snippet, comments=True)
        except ValueError:
            continue
        if tokens and not any(token in {"&&", "||", "|", ";", "&"} for token in tokens):
            commands.append(tokens)
    return commands


def _python_target(read: Callable[[str], str], path: str, symbol: str, *, script: bool) -> None:
    tree = ast.parse(read(path), filename=path)
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
               for node in tree.body):
        raise ValueError(f"entrypoint function missing: {path}#{symbol}")
    if script:
        guards = [node for node in tree.body if isinstance(node, ast.If)
                  and ast.unparse(node.test) in {"__name__ == '__main__'", "'__main__' == __name__"}]
        if not any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == symbol
                   for guard in guards for call in ast.walk(guard)):
            raise ValueError(f"native __main__ entrypoint is missing: {path}#{symbol}")


def _external_tool(read: Callable[[str], str], tool: str) -> str:
    project = tomllib.loads(read("pyproject.toml"))["project"]
    dependencies = project.get("optional-dependencies", {}).get("dev", [])
    if not any(re.split(r"[<>=!~;\[]", requirement, maxsplit=1)[0].strip() == tool
               for requirement in dependencies):
        raise ValueError(f"external command lacks a development dependency declaration: {tool}")
    return f"external development dependency: {tool}; execution unavailable"


def _install(read: Callable[[str], str], tokens: list[str]) -> str:
    operands = tokens[4:]
    if tokens[3:4] != ["install"] or len(operands) != 4 or operands[::2] != ["-e", "-e"]:
        raise ValueError("bootstrap requires two editable project operands")
    targets = set()
    for operand in operands[1::2]:
        match = re.fullmatch(r"([^\[\]]+)\[([a-z][a-z0-9_-]*)\]", operand)
        if not match:
            raise ValueError("editable project must name one declared extra")
        path = (PurePosixPath(match[1]) / "pyproject.toml").as_posix()
        targets.add(path)
        extra = match[2]
        project = tomllib.loads(read(path))["project"]
        if extra not in project.get("optional-dependencies", {}):
            raise ValueError(f"installation extra missing: {path}[{extra}]")
    if targets != {"pyproject.toml", "orket_extension_sdk/pyproject.toml"}:
        raise ValueError("bootstrap must bind both core and SDK projects")
    return "core and SDK packaging declarations; installation proof unavailable"


def bind_command(record: dict, read: Callable[[str], str]) -> str:
    """Derive the target from the actual argv; an authored target cannot substitute."""
    tokens = shlex.split(record["command"])
    if tokens not in documented_commands(read(record["source"]), record["source"]):
        raise ValueError(f"documented command argv differs: {record['id']}")
    if tokens[:3] == ["python", "-m", "pip"]:
        return _install(read, tokens)
    if tokens[:3] == ["python", "-m", "pytest"] or tokens[:1] == ["pytest"]:
        return _external_tool(read, "pytest")
    if tokens[:1] == ["ruff"]:
        return _external_tool(read, "ruff")
    if tokens[:1] == ["python"] and len(tokens) > 1 and tokens[1].endswith(".py"):
        _python_target(read, tokens[1], "main", script=True)
        return f"{tokens[1]}#main; native entrypoint source observed"
    if tokens[:2] == ["python", "-m"] and len(tokens) > 2:
        path = tokens[2].replace(".", "/") + ".py"
        _python_target(read, path, "main", script=True)
        return f"{path}#main; module entrypoint source observed"
    project = tomllib.loads(read("pyproject.toml"))["project"]
    target = project.get("scripts", {}).get(tokens[0] if tokens else "")
    if not isinstance(target, str) or target.count(":") != 1:
        raise ValueError(f"command has no supported entrypoint: {record['id']}")
    module, symbol = target.split(":")
    path = module.replace(".", "/") + ".py"
    _python_target(read, path, symbol, script=False)
    return f"{path}#{symbol}; console entrypoint source observed"
