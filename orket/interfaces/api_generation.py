from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from orket.interfaces.failure_lessons import (
    ERROR_PREFLIGHT_FAILED,
    lookup_relevant_lessons,
    record_failure_lesson,
    run_preflight_checks,
    strict_preflight_enabled,
)
from orket.interfaces.replay_artifacts import write_replay_artifact

ERROR_SCOPE_REQUIRED = "E_SCOPE_REQUIRED"
ERROR_DRAFT_FAILURE = "E_DRAFT_FAILURE"
ERROR_WRITE_OUT_OF_SCOPE = "E_WRITE_OUT_OF_SCOPE"
ERROR_CONFIG_INVALID = "E_CONFIG_INVALID"
ERROR_GIT_REQUIRED = "E_GIT_REQUIRED"
ERROR_WORKTREE_DIRTY = "E_WORKTREE_DIRTY"
ERROR_PROJECT_STYLE_UNSUPPORTED = "E_PROJECT_STYLE_UNSUPPORTED"
ERROR_SCHEMA_PARSE_FAILED = "E_SCHEMA_PARSE_FAILED"
ERROR_INTERNAL = "E_INTERNAL"


@dataclass(frozen=True)
class ParsedSchemaField:
    name: str
    field_type: str


def _run(command: List[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def _run_shell(command: str, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    argv = shlex.split(command, posix=True)
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def _tail(text: str, *, max_lines: int = 200, max_bytes: int = 32768) -> str:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]
    clipped = raw.decode("utf-8", errors="replace")
    return "\n".join(clipped.splitlines()[-max_lines:])


def _parse_schema(schema_text: str) -> List[ParsedSchemaField]:
    rows: List[ParsedSchemaField] = []
    for token in [part.strip() for part in schema_text.split(",") if part.strip()]:
        name, sep, field_type = token.partition(":")
        if not sep or not name.strip() or not field_type.strip():
            raise ValueError(f"Invalid schema segment: {token}")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name.strip()):
            raise ValueError(f"Invalid field name: {name.strip()}")
        rows.append(ParsedSchemaField(name=name.strip(), field_type=field_type.strip()))
    if not rows:
        raise ValueError("Schema must contain at least one field.")
    return rows


def _is_repo_git(repo_root: Path) -> bool:
    probe = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)
    return probe.returncode == 0 and probe.stdout.strip() == "true"


def _is_clean_worktree(repo_root: Path) -> bool:
    status = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if status.returncode != 0:
        return False
    for line in [row.rstrip() for row in status.stdout.splitlines() if row.strip()]:
        path_spec = line[3:] if len(line) >= 4 else line
        candidates = [segment.strip() for segment in path_spec.split("->")]
        normalized = [segment.replace("\\", "/") for segment in candidates]
        if all(item.startswith(".orket/") for item in normalized if item):
            continue
        return False
    return True


def _load_verify_commands(repo_root: Path, profile_name: str) -> List[str]:
    config_path = repo_root / "orket.config.json"
    if not config_path.exists():
        return ["python -m pytest -q"]
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid orket.config.json: {exc}") from exc

    profiles = ((payload.get("verify") or {}).get("profiles") or {})
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise ValueError(f"Verify profile not found: {profile_name}")
    commands = profile.get("commands")
    if not isinstance(commands, list) or not commands or not all(isinstance(item, str) and item.strip() for item in commands):
        raise ValueError(f"Verify profile '{profile_name}' must include non-empty commands list.")
    return [item.strip() for item in commands]


def _validate_scoped(path: Path, scope_roots: List[Path]) -> str | None:
    resolved = path.resolve()
    if "node_modules" in resolved.parts:
        return ERROR_WRITE_OUT_OF_SCOPE
    for scope in scope_roots:
        try:
            resolved.relative_to(scope.resolve())
            return None
        except ValueError:
            continue
    return ERROR_WRITE_OUT_OF_SCOPE


def _detect_express_style(repo_root: Path) -> tuple[Path, Path, Path] | None:
    routes_index = repo_root / "src" / "routes" / "index.js"
    if not routes_index.is_file():
        return None
    controllers_dir = repo_root / "src" / "controllers"
    routes_dir = repo_root / "src" / "routes"
    return routes_index, routes_dir, controllers_dir


def _pascal(name: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", name) if part)


def _route_template(route_name: str, method: str, controller_fn: str) -> str:
    return (
        f"const {controller_fn} = require('../controllers/{route_name}_controller');\n\n"
        f"function register{_pascal(route_name)}Route(router) {{\n"
        f"  router.{method.lower()}('/{route_name}', {controller_fn});\n"
        "}\n\n"
        f"module.exports = {{ register{_pascal(route_name)}Route }};\n"
    )


def _controller_template(route_name: str, method: str, fields: List[ParsedSchemaField]) -> str:
    field_lines = "\n".join([f" * @property {{{field.field_type}}} {field.name}" for field in fields])
    return (
        "/**\n"
        f" * Auto-generated by orket api add for route '{route_name}'.\n"
        f"{field_lines}\n"
        " */\n"
        f"function handle{_pascal(route_name)}{method.capitalize()}(req, res) {{\n"
        "  // ORKET:USER-START\n"
        "  return res.status(501).json({ message: 'Implement route handler logic.' });\n"
        "  // ORKET:USER-END\n"
        "}\n\n"
        f"module.exports = handle{_pascal(route_name)}{method.capitalize()};\n"
    )


def _types_template(route_name: str, fields: List[ParsedSchemaField]) -> str:
    rows = ",\n".join([f'  "{field.name}": "{field.field_type}"' for field in fields])
    return "{\n" f'  "route": "{route_name}",\n' '  "request_schema": {\n' f"{rows}\n" "  }\n}\n"


def _render_plan(route_name: str, scope_inputs: List[str], touch_set: List[Path], verify_commands: List[str]) -> str:
    lines = [f'ORCHESTRATING API ADD: "{route_name}"', "-----------------------------------------------", "SCOPE:"]
    lines.extend(f"  - {scope}" for scope in scope_inputs)
    lines.append("FILES TO BE MODIFIED:")
    lines.extend(f"  [M] {path.as_posix()}" for path in touch_set)
    lines.append("GUARDRAILS ACTIVE:")
    lines.append("  - Write barrier: scope + touch-set")
    lines.append("  - Verification:")
    lines.extend(f"      * {command}" for command in verify_commands)
    return "\n".join(lines)


def run_api_add_transaction(
    *,
    route_name: str,
    schema_text: str,
    method: str,
    scope_inputs: List[str],
    dry_run: bool,
    auto_confirm: bool,
    verify_profile: str = "default",
) -> Dict[str, Any]:
    repo_root = Path.cwd().resolve()
    request_payload = {
        "route_name": route_name,
        "schema": schema_text,
        "method": method,
        "scope": list(scope_inputs),
        "dry_run": bool(dry_run),
        "auto_confirm": bool(auto_confirm),
        "verify_profile": verify_profile,
    }
    if not _is_repo_git(repo_root):
        result = {"ok": False, "code": ERROR_GIT_REQUIRED, "message": "Current directory must be a git repository."}
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result
    if not _is_clean_worktree(repo_root):
        result = {"ok": False, "code": ERROR_WORKTREE_DIRTY, "message": "Working tree must be clean before api-add transaction runs."}
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result
    if not scope_inputs:
        result = {"ok": False, "code": ERROR_SCOPE_REQUIRED, "message": "--scope is required."}
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result

    try:
        fields = _parse_schema(schema_text)
    except ValueError as exc:
        result = {"ok": False, "code": ERROR_SCHEMA_PARSE_FAILED, "message": str(exc)}
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result

    try:
        verify_commands = _load_verify_commands(repo_root, verify_profile)
    except ValueError as exc:
        result = {"ok": False, "code": ERROR_CONFIG_INVALID, "message": str(exc)}
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result

    detected = _detect_express_style(repo_root)
    if detected is None:
        result = {
            "ok": False,
            "code": ERROR_PROJECT_STYLE_UNSUPPORTED,
            "message": "Unsupported project style for v1 API generation adapter.",
        }
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result
    routes_index, routes_dir, controllers_dir = detected
    types_dir = repo_root / "src" / "types"
    route_file = routes_dir / f"{route_name}.js"
    controller_file = controllers_dir / f"{route_name}_controller.js"
    types_file = types_dir / f"{route_name}.json"
    touch_set = [route_file, controller_file, types_file, routes_index]
    scope_roots = [(repo_root / scope).resolve() for scope in scope_inputs]

    for path in touch_set:
        violation = _validate_scoped(path, scope_roots)
        if violation:
            result = {
                "ok": False,
                "code": ERROR_WRITE_OUT_OF_SCOPE,
                "message": f"Write blocked: {path.relative_to(repo_root).as_posix()}",
            }
            write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
            return result

    plan_text = _render_plan(route_name, scope_inputs, [path.relative_to(repo_root) for path in touch_set], verify_commands)
    touch_rel = [path.relative_to(repo_root).as_posix() for path in touch_set]
    advisories = lookup_relevant_lessons(
        repo_root=repo_root,
        command_name="api_add",
        scope_inputs=scope_inputs,
        touch_set=touch_rel,
        verify_profile=verify_profile,
    )
    preflight_warnings = run_preflight_checks(repo_root=repo_root, advisories=advisories)
    if preflight_warnings and strict_preflight_enabled():
        result = {
            "ok": False,
            "code": ERROR_PREFLIGHT_FAILED,
            "message": "Preflight checks failed in strict mode.",
            "plan": plan_text,
            "advisories": advisories,
            "preflight_warnings": preflight_warnings,
        }
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result

    if dry_run:
        result = {
            "ok": True,
            "code": "OK",
            "message": "Dry run only.",
            "plan": plan_text,
            "advisories": advisories,
            "preflight_warnings": preflight_warnings,
        }
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result
    if not auto_confirm:
        result = {
            "ok": False,
            "code": ERROR_SCOPE_REQUIRED,
            "message": "Mutation requires --yes confirmation.",
            "plan": plan_text,
            "advisories": advisories,
            "preflight_warnings": preflight_warnings,
        }
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result

    head = _run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    if head.returncode != 0:
        result = {"ok": False, "code": ERROR_INTERNAL, "message": "Unable to resolve git HEAD."}
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result
    head_sha = head.stdout.strip()

    try:
        route_registration = f"register{_pascal(route_name)}Route"
        routes_index_text = routes_index.read_text(encoding="utf-8")
        import_line = f"const {{ {route_registration} }} = require('./{route_name}');"
        register_line = f"{route_registration}(router);"
        already_present = import_line in routes_index_text and register_line in routes_index_text
        if already_present and route_file.exists() and controller_file.exists() and types_file.exists():
            result = {"ok": True, "code": "OK", "message": "Idempotent no-op: route already present.", "plan": plan_text, "idempotent": True}
            write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
            return result

        route_file.parent.mkdir(parents=True, exist_ok=True)
        controllers_dir.mkdir(parents=True, exist_ok=True)
        types_dir.mkdir(parents=True, exist_ok=True)

        controller_fn = f"handle{_pascal(route_name)}{method.capitalize()}"
        route_file.write_text(_route_template(route_name, method, controller_fn), encoding="utf-8")
        if not controller_file.exists():
            controller_file.write_text(_controller_template(route_name, method, fields), encoding="utf-8")
        if not types_file.exists():
            types_file.write_text(_types_template(route_name, fields), encoding="utf-8")

        new_routes = routes_index_text
        if import_line not in new_routes:
            new_routes = f"{import_line}\n" + new_routes
        if register_line not in new_routes:
            marker = "module.exports"
            if marker in new_routes:
                new_routes = new_routes.replace(marker, f"{register_line}\n\n{marker}", 1)
            else:
                new_routes = f"{new_routes.rstrip()}\n{register_line}\n"
        routes_index.write_text(new_routes, encoding="utf-8")

        for verify_command in verify_commands:
            verify = _run_shell(verify_command, cwd=repo_root)
            if verify.returncode != 0:
                _run(["git", "reset", "--hard", head_sha], cwd=repo_root)
                _run(["git", "clean", "-fd"], cwd=repo_root)
                result = {
                    "ok": False,
                    "code": ERROR_DRAFT_FAILURE,
                    "message": f"Generated draft failed verification and was reverted: {verify_command}",
                    "verify_command": verify_command,
                    "verify_exit_code": verify.returncode,
                    "verify_output_tail": _tail((verify.stdout or "") + "\n" + (verify.stderr or "")),
                    "plan": plan_text,
                    "advisories": advisories,
                    "preflight_warnings": preflight_warnings,
                }
                post_head = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
                lesson_id = record_failure_lesson(
                    repo_root=repo_root,
                    command_name="api_add",
                    request=request_payload,
                    result=result,
                    touch_set=touch_rel,
                    head_pre=head_sha,
                    head_post=post_head,
                    verify_commands=verify_commands,
                    failed_verify_command=verify_command,
                )
                result["failure_lesson_id"] = lesson_id
                write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
                return result

        result = {
            "ok": True,
            "code": "OK",
            "message": "API route generated.",
            "plan": plan_text,
            "advisories": advisories,
            "preflight_warnings": preflight_warnings,
        }
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result
    except OSError as exc:
        _run(["git", "reset", "--hard", head_sha], cwd=repo_root)
        _run(["git", "clean", "-fd"], cwd=repo_root)
        result = {"ok": False, "code": ERROR_INTERNAL, "message": f"api add failed with internal I/O error: {exc}"}
        write_replay_artifact(command_name="api_add", request=request_payload, result=result, repo_root=repo_root)
        return result
