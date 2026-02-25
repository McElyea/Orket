from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


ERROR_PREFLIGHT_FAILED = "E_PREFLIGHT_FAILED"

_TAG_PATTERNS: list[tuple[str, str]] = [
    ("missing_env_var", r"(missing env var|environment variable|KeyError:\s*'?[A-Z][A-Z0-9_]+'?)"),
    ("missing_dependency", r"(No module named|ModuleNotFoundError|Cannot find module)"),
    ("type_error", r"(TypeError|Incompatible types|mypy)"),
    ("lint_error", r"(ruff|flake8|eslint|lint)"),
    ("test_assertion_failed", r"(AssertionError|FAILED\s+.+|assert .+==.+)"),
    ("build_config_error", r"(pyproject|tsconfig|webpack|vite\.config|build failed)"),
    ("port_in_use", r"(address already in use|EADDRINUSE|port .+ in use)"),
    ("db_connection_failed", r"(connection refused|could not connect|database is locked|OperationalError)"),
]

_ENV_VAR_CAPTURE = re.compile(r"\b[A-Z][A-Z0-9_]{1,}\b")
_COMMAND_CAPTURE = re.compile(
    r"(?:command not found|not recognized as an internal or external command)[:\s]+([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
_FILE_CAPTURE = re.compile(r"No such file or directory:\s*'([^']+)'")


def failure_lessons_enabled() -> bool:
    raw = str(os.getenv("ORKET_FAILURE_LESSONS", "0")).strip().lower()
    return raw not in {"0", "false", "off", "no"}


def strict_preflight_enabled() -> bool:
    raw = str(os.getenv("ORKET_FAILURE_LESSONS_STRICT_PREFLIGHT", "0")).strip().lower()
    return raw not in {"0", "false", "off", "no"}


def _lesson_path(repo_root: Path) -> Path:
    return repo_root / ".orket" / "memory" / "failure_lessons.jsonl"


def _read_lessons(repo_root: Path) -> list[Dict[str, Any]]:
    path = _lesson_path(repo_root)
    if not path.exists():
        return []
    rows: list[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _extract_preflight_checks(output_text: str) -> list[Dict[str, str]]:
    checks: list[Dict[str, str]] = []
    env_vars = sorted({token for token in _ENV_VAR_CAPTURE.findall(output_text) if token not in {"FAIL", "ERROR", "TEST"}})
    for name in env_vars:
        checks.append({"type": "env_var_present", "name": name})

    commands = sorted({match.group(1) for match in _COMMAND_CAPTURE.finditer(output_text)})
    for command_name in commands:
        checks.append({"type": "command_exists", "command": command_name})

    files = sorted({match.group(1) for match in _FILE_CAPTURE.finditer(output_text)})
    for file_name in files:
        checks.append({"type": "file_exists", "path": file_name})
    return checks


def classify_failure(*, output_tail: str, message: str) -> Dict[str, Any]:
    source = f"{message}\n{output_tail}"
    tags: list[str] = []
    signals: list[str] = []
    for tag, pattern in _TAG_PATTERNS:
        if re.search(pattern, source, flags=re.IGNORECASE):
            tags.append(tag)
            signals.append(f"regex:{tag}")
    if not tags:
        tags = ["build_config_error"]
        signals.append("fallback:build_config_error")
    confidence = min(0.95, 0.45 + (0.1 * len(tags)))
    return {
        "tags": tags,
        "confidence": round(confidence, 2),
        "signals": signals,
        "preflight_checks": _extract_preflight_checks(source),
    }


def record_failure_lesson(
    *,
    repo_root: Path,
    command_name: str,
    request: Dict[str, Any],
    result: Dict[str, Any],
    touch_set: Iterable[str],
    head_pre: str,
    head_post: str,
    verify_commands: Iterable[str],
    failed_verify_command: str,
) -> str:
    if not failure_lessons_enabled():
        return ""

    output_tail = str(result.get("verify_output_tail", ""))
    touch_rows = sorted(str(path).replace("\\", "/") for path in touch_set)
    classification = classify_failure(output_tail=output_tail, message=str(result.get("message", "")))
    lesson_payload: Dict[str, Any] = {
        "schema_version": "core_pillars/failure_lesson/v1",
        "created_at": datetime.now(UTC).isoformat(),
        "command": command_name,
        "request": request,
        "repo": {
            "head_pre": head_pre,
            "head_post": head_post,
            "dirty_after_revert": False,
        },
        "plan": {
            "touch_set": touch_rows,
            "touch_count": len(touch_rows),
        },
        "verify": {
            "profile": str(request.get("verify_profile", "")),
            "commands": list(verify_commands),
            "failed_command": failed_verify_command,
            "exit_code": int(result.get("verify_exit_code", 0)),
            "output_tail": output_tail,
        },
        "classification": {
            "tags": classification["tags"],
            "confidence": classification["confidence"],
            "signals": classification["signals"],
        },
        "advice": {
            "summary": str(result.get("message", "")),
            "suggested_actions": [f"Run preflight checks before repeating `{command_name}`."],
            "preflight_checks": classification["preflight_checks"],
        },
    }
    digest = hashlib.sha256(json.dumps(lesson_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    lesson_payload["id"] = digest

    path = _lesson_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(lesson_payload, sort_keys=True, ensure_ascii=False) + "\n")
    return digest


def _score_lesson(
    *,
    lesson: Dict[str, Any],
    command_name: str,
    scope_inputs: List[str],
    touch_set: List[str],
    verify_profile: str,
) -> int:
    score = 0
    if str(lesson.get("command", "")) == command_name:
        score += 10
    lesson_request = lesson.get("request") if isinstance(lesson.get("request"), dict) else {}
    if str(lesson_request.get("verify_profile", "")) == verify_profile:
        score += 5
    lesson_scope = [str(value) for value in (lesson_request.get("scope") or [])]
    scope_overlap = len(set(scope_inputs) & set(lesson_scope))
    score += scope_overlap * 3
    lesson_plan = lesson.get("plan") if isinstance(lesson.get("plan"), dict) else {}
    lesson_touch_set = [str(value) for value in (lesson_plan.get("touch_set") or [])]
    touch_overlap = len(set(touch_set) & set(lesson_touch_set))
    score += touch_overlap * 2
    return score


def lookup_relevant_lessons(
    *,
    repo_root: Path,
    command_name: str,
    scope_inputs: List[str],
    touch_set: List[str],
    verify_profile: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    if not failure_lessons_enabled():
        return []
    ranked: list[tuple[int, str, Dict[str, Any]]] = []
    for row in _read_lessons(repo_root):
        score = _score_lesson(
            lesson=row,
            command_name=command_name,
            scope_inputs=scope_inputs,
            touch_set=touch_set,
            verify_profile=verify_profile,
        )
        if score <= 0:
            continue
        ranked.append((score, str(row.get("created_at", "")), row))
    ranked.sort(key=lambda item: (-item[0], item[1], str(item[2].get("id", ""))))
    results: List[Dict[str, Any]] = []
    for score, _created_at, row in ranked[: max(1, int(top_k))]:
        advice = row.get("advice") if isinstance(row.get("advice"), dict) else {}
        results.append(
            {
                "lesson_id": str(row.get("id", "")),
                "score": score,
                "summary": str(advice.get("summary", "")),
                "preflight_checks": list(advice.get("preflight_checks") or []),
            }
        )
    return results


def run_preflight_checks(*, repo_root: Path, advisories: List[Dict[str, Any]]) -> List[str]:
    failures: list[str] = []
    for advisory in advisories:
        for check in list(advisory.get("preflight_checks") or []):
            if not isinstance(check, dict):
                continue
            check_type = str(check.get("type", ""))
            if check_type == "env_var_present":
                key = str(check.get("name", ""))
                if key and not str(os.getenv(key, "")).strip():
                    failures.append(f"env_var_present:{key}")
            elif check_type == "command_exists":
                command_name = str(check.get("command", ""))
                if command_name and shutil.which(command_name) is None:
                    failures.append(f"command_exists:{command_name}")
            elif check_type == "file_exists":
                raw_path = str(check.get("path", ""))
                if raw_path:
                    candidate = Path(raw_path)
                    if not candidate.is_absolute():
                        candidate = repo_root / candidate
                    if not candidate.exists():
                        failures.append(f"file_exists:{raw_path}")
    return sorted(set(failures))
