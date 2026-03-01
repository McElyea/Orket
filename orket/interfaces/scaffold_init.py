from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from orket.interfaces.replay_artifacts import write_replay_artifact

ERROR_BLUEPRINT_NOT_FOUND = "E_BLUEPRINT_NOT_FOUND"
ERROR_OUTPUT_DIR_EXISTS = "E_OUTPUT_DIR_EXISTS"
ERROR_INIT_VERIFY_FAILED = "E_INIT_VERIFY_FAILED"
ERROR_INIT_CONFIG_INVALID = "E_INIT_CONFIG_INVALID"


@dataclass(frozen=True)
class Blueprint:
    name: str
    verify_commands: List[str]
    templates: Dict[str, str]


def _builtin_blueprints() -> Dict[str, Blueprint]:
    minimal_node = Blueprint(
        name="minimal-node",
        verify_commands=["python -c \"pass\""],
        templates={
            "README.md": "# {{project_name}}\n\nScaffolded by `orket init`.\n",
            "package.json": json.dumps(
                {
                    "name": "{{project_name}}",
                    "version": "0.1.0",
                    "private": True,
                    "scripts": {"dev": "node src/index.js"},
                },
                indent=2,
            )
            + "\n",
            "src/index.js": "console.log('Hello from {{project_name}}');\n",
        },
    )
    return {minimal_node.name: minimal_node}


def _render_template(raw: str, variables: Dict[str, str]) -> str:
    rendered = raw
    for key, value in sorted(variables.items()):
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _run_shell(command: str, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    argv = shlex.split(command, posix=True)
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def _tail(text: str, *, max_lines: int = 200, max_bytes: int = 32768) -> str:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]
    clipped = raw.decode("utf-8", errors="replace")
    return "\n".join(clipped.splitlines()[-max_lines:])


def run_scaffold_init(
    *,
    template_name: str,
    project_name: str,
    output_dir: str | None = None,
    variable_overrides: Dict[str, str] | None = None,
    verify_enabled: bool = True,
) -> Dict[str, Any]:
    repo_root = Path.cwd().resolve()
    request_payload = {
        "template_name": template_name,
        "project_name": project_name,
        "output_dir": output_dir,
        "variables": variable_overrides or {},
        "verify_enabled": bool(verify_enabled),
    }
    blueprints = _builtin_blueprints()
    blueprint = blueprints.get(template_name)
    if blueprint is None:
        result = {
            "ok": False,
            "code": ERROR_BLUEPRINT_NOT_FOUND,
            "message": f"Blueprint not found: {template_name}",
        }
        write_replay_artifact(command_name="init", request=request_payload, result=result, repo_root=repo_root)
        return result

    target = Path(output_dir).resolve() if output_dir else (Path.cwd() / project_name).resolve()
    if target.exists():
        result = {
            "ok": False,
            "code": ERROR_OUTPUT_DIR_EXISTS,
            "message": f"Output directory already exists: {target}",
        }
        write_replay_artifact(command_name="init", request=request_payload, result=result, repo_root=repo_root)
        return result

    variables = {"project_name": project_name}
    for key, value in sorted((variable_overrides or {}).items()):
        variables[str(key)] = str(value)

    try:
        target.mkdir(parents=True, exist_ok=False)
        for relative_path, raw in blueprint.templates.items():
            path = target / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render_template(raw, variables), encoding="utf-8")
    except OSError as exc:
        shutil.rmtree(target, ignore_errors=True)
        result = {
            "ok": False,
            "code": ERROR_INIT_CONFIG_INVALID,
            "message": f"Failed to write scaffold output: {exc}",
        }
        write_replay_artifact(command_name="init", request=request_payload, result=result, repo_root=repo_root)
        return result

    if verify_enabled:
        for command in blueprint.verify_commands:
            run = _run_shell(command, cwd=target)
            if run.returncode != 0:
                tail = _tail((run.stdout or "") + "\n" + (run.stderr or ""))
                shutil.rmtree(target, ignore_errors=True)
                result = {
                    "ok": False,
                    "code": ERROR_INIT_VERIFY_FAILED,
                    "message": f"Init verify failed: {command}",
                    "verify_command": command,
                    "verify_exit_code": run.returncode,
                    "verify_output_tail": tail,
                }
                write_replay_artifact(command_name="init", request=request_payload, result=result, repo_root=repo_root)
                return result

    result = {
        "ok": True,
        "code": "OK",
        "message": "Scaffold generated.",
        "template": template_name,
        "project_name": project_name,
        "output_dir": str(target),
        "verify_enabled": verify_enabled,
    }
    write_replay_artifact(command_name="init", request=request_payload, result=result, repo_root=repo_root)
    return result
