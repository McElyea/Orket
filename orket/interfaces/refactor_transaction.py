from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List


ERROR_SCOPE_REQUIRED = "E_SCOPE_REQUIRED"
ERROR_TOUCHSET_EMPTY = "E_TOUCHSET_EMPTY"
ERROR_WRITE_OUT_OF_SCOPE = "E_WRITE_OUT_OF_SCOPE"
ERROR_MODEL_OUTPUT_OUT_OF_SCOPE = "E_MODEL_OUTPUT_OUT_OF_SCOPE"
ERROR_VERIFY_FAILED_REVERTED = "E_VERIFY_FAILED_REVERTED"
ERROR_CONFIG_INVALID = "E_CONFIG_INVALID"
ERROR_GIT_REQUIRED = "E_GIT_REQUIRED"
ERROR_UNSUPPORTED_INSTRUCTION = "E_UNSUPPORTED_INSTRUCTION"
ERROR_INTERNAL = "E_INTERNAL"
ERROR_WORKTREE_DIRTY = "E_WORKTREE_DIRTY"


def _run(command: List[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def _run_shell(command: str, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False, shell=True)


def _tail(text: str, *, max_lines: int = 200, max_bytes: int = 32768) -> str:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]
    clipped = raw.decode("utf-8", errors="replace")
    return "\n".join(clipped.splitlines()[-max_lines:])


def _parse_instruction(instruction: str) -> tuple[str, str] | None:
    match = re.search(r"rename\s+([A-Za-z_][A-Za-z0-9_]*)\s+to\s+([A-Za-z_][A-Za-z0-9_]*)", instruction, re.IGNORECASE)
    if not match:
        return None
    return match.group(1), match.group(2)


def _is_repo_git(repo_root: Path) -> bool:
    probe = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)
    return probe.returncode == 0 and probe.stdout.strip() == "true"


def _is_clean_worktree(repo_root: Path) -> bool:
    status = _run(["git", "status", "--porcelain"], cwd=repo_root)
    return status.returncode == 0 and status.stdout.strip() == ""


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


def _collect_files(scope_roots: List[Path]) -> List[Path]:
    blocked_dir_names = {"node_modules", ".git", ".venv", "__pycache__"}
    files: List[Path] = []
    for scope in scope_roots:
        if not scope.exists():
            continue
        if scope.is_file():
            files.append(scope)
            continue
        for path in scope.rglob("*"):
            if path.is_dir() and path.name in blocked_dir_names:
                continue
            if path.is_file() and not any(part in blocked_dir_names for part in path.parts):
                files.append(path)
    return sorted(set(files))


def _compute_touch_set(repo_root: Path, scope_roots: List[Path], rename_from: str) -> List[Path]:
    pattern = re.compile(rf"\b{re.escape(rename_from)}\b")
    touches: List[Path] = []
    for candidate in _collect_files(scope_roots):
        try:
            text = candidate.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if pattern.search(text):
            touches.append(candidate)
    return sorted(touches)


def _in_scope(path: Path, scope_roots: List[Path]) -> bool:
    for scope in scope_roots:
        try:
            path.resolve().relative_to(scope.resolve())
            return True
        except ValueError:
            continue
    return False


def _validate_write(path: Path, scope_roots: List[Path]) -> str | None:
    resolved = path.resolve()
    if "node_modules" in resolved.parts:
        return ERROR_WRITE_OUT_OF_SCOPE
    if not _in_scope(path, scope_roots):
        return ERROR_WRITE_OUT_OF_SCOPE
    return None


def _render_plan(instruction: str, scope_inputs: List[str], touches: List[Path], verify_commands: List[str]) -> str:
    lines = [f'ORCHESTRATING REFACTOR: "{instruction}"', "-----------------------------------------------", "SCOPE:"]
    lines.extend(f"  - {scope}" for scope in scope_inputs)
    lines.append("FILES TO BE MODIFIED:")
    if touches:
        lines.extend(f"  [M] {path.as_posix()}" for path in touches)
    else:
        lines.append("  (none)")
    lines.append("GUARDRAILS ACTIVE:")
    lines.append("  - Write barrier: scope + touch-set")
    lines.append("  - Verification:")
    lines.extend(f"      * {command}" for command in verify_commands)
    return "\n".join(lines)


def run_refactor_transaction(
    *,
    instruction: str,
    scope_inputs: List[str],
    dry_run: bool,
    auto_confirm: bool,
    verify_profile: str = "default",
) -> Dict[str, Any]:
    repo_root = Path.cwd().resolve()
    if not _is_repo_git(repo_root):
        return {
            "ok": False,
            "code": ERROR_GIT_REQUIRED,
            "message": "Current directory must be a git repository.",
        }
    if not _is_clean_worktree(repo_root):
        return {
            "ok": False,
            "code": ERROR_WORKTREE_DIRTY,
            "message": "Working tree must be clean before refactor transaction runs.",
        }

    if not scope_inputs:
        return {"ok": False, "code": ERROR_SCOPE_REQUIRED, "message": "--scope is required."}

    parsed = _parse_instruction(instruction)
    if parsed is None:
        return {
            "ok": False,
            "code": ERROR_UNSUPPORTED_INSTRUCTION,
            "message": "Only 'rename <SymbolA> to <SymbolB>' is supported in CP-1.1.",
        }
    rename_from, rename_to = parsed

    try:
        verify_commands = _load_verify_commands(repo_root, verify_profile)
    except ValueError as exc:
        return {"ok": False, "code": ERROR_CONFIG_INVALID, "message": str(exc)}

    scope_roots = [(repo_root / scope).resolve() for scope in scope_inputs]
    touch_set = _compute_touch_set(repo_root, scope_roots, rename_from)
    plan_text = _render_plan(instruction, scope_inputs, [path.relative_to(repo_root) for path in touch_set], verify_commands)

    if not touch_set:
        return {"ok": False, "code": ERROR_TOUCHSET_EMPTY, "message": "No files in scope matched refactor plan.", "plan": plan_text}

    if dry_run:
        return {"ok": True, "code": "OK", "message": "Dry run only.", "plan": plan_text, "touch_count": len(touch_set)}

    if not auto_confirm:
        # Non-interactive default in test/runtime shell; explicit --yes required for mutation.
        return {"ok": False, "code": ERROR_SCOPE_REQUIRED, "message": "Mutation requires --yes confirmation.", "plan": plan_text}

    head = _run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    if head.returncode != 0:
        return {"ok": False, "code": ERROR_INTERNAL, "message": "Unable to resolve git HEAD."}
    head_sha = head.stdout.strip()

    pattern = re.compile(rf"\b{re.escape(rename_from)}\b")

    try:
        for path in touch_set:
            violation = _validate_write(path, scope_roots)
            if violation:
                return {
                    "ok": False,
                    "code": ERROR_MODEL_OUTPUT_OUT_OF_SCOPE,
                    "message": f"Planned write out of scope: {path.relative_to(repo_root)}",
                    "plan": plan_text,
                }
            source = path.read_text(encoding="utf-8")
            mutated = pattern.sub(rename_to, source)
            path.write_text(mutated, encoding="utf-8")

        for verify_command in verify_commands:
            verify = _run_shell(verify_command, cwd=repo_root)
            if verify.returncode != 0:
                _run(["git", "reset", "--hard", head_sha], cwd=repo_root)
                _run(["git", "clean", "-fd"], cwd=repo_root)
                return {
                    "ok": False,
                    "code": ERROR_VERIFY_FAILED_REVERTED,
                    "message": f"Verification failed and changes were reverted: {verify_command}",
                    "verify_command": verify_command,
                    "verify_exit_code": verify.returncode,
                    "verify_output_tail": _tail((verify.stdout or "") + "\n" + (verify.stderr or "")),
                    "plan": plan_text,
                }

        return {"ok": True, "code": "OK", "message": "Refactor completed.", "plan": plan_text, "touch_count": len(touch_set)}
    except OSError as exc:
        _run(["git", "reset", "--hard", head_sha], cwd=repo_root)
        _run(["git", "clean", "-fd"], cwd=repo_root)
        return {"ok": False, "code": ERROR_INTERNAL, "message": f"Refactor failed with internal I/O error: {exc}"}
