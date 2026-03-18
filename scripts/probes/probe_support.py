from __future__ import annotations

import json
import os
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Sequence

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.core.critical_path import CriticalPathEngine
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

DEFAULT_ROLE_NAME = "coder"
DEFAULT_REVIEWER_ROLE_NAME = "code_reviewer"
DEFAULT_GUARD_ROLE_NAME = "integrity_guard"
DEFAULT_TEAM_NAME = "probe_team"
DEFAULT_ENV_NAME = "standard"
DEFAULT_ROLE_DESCRIPTION = (
    "Complete the small task described in the issue summary. "
    "Write the requested artifact exactly where the issue asks, then call update_issue_status "
    "with status code_review in the same response. Do not add issue comments."
)
DEFAULT_REVIEWER_DESCRIPTION = (
    "Review the artifact produced for the issue and call update_issue_status "
    "with status code_review in the same response. Do not add issue comments."
)
DEFAULT_GUARD_DESCRIPTION = (
    "Act as the final gatekeeper for the issue. Call update_issue_status with status done "
    "when the requested artifact is present and acceptable; otherwise use blocked."
)
_DIALECTS = ("qwen", "llama3", "deepseek-r1", "phi", "generic")


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


@contextmanager
def applied_probe_env(
    *,
    provider: str = "ollama",
    ollama_host: str | None = None,
    disable_sandbox: bool = True,
    extra_env: dict[str, str] | None = None,
) -> Iterator[None]:
    updates: dict[str, str] = {}
    if provider:
        updates["ORKET_LLM_PROVIDER"] = str(provider).strip()
    if ollama_host:
        updates["ORKET_LLM_OLLAMA_HOST"] = str(ollama_host).strip()
    if disable_sandbox:
        updates["ORKET_DISABLE_SANDBOX"] = "1"
    if extra_env:
        updates.update({str(key): str(value) for key, value in extra_env.items()})

    previous: dict[str, str | None] = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_probe_runtime_root(
    root: Path,
    *,
    epic_id: str,
    environment_model: str,
    issues: Sequence[dict[str, Any]],
    team_name: str = DEFAULT_TEAM_NAME,
    role_name: str = DEFAULT_ROLE_NAME,
    role_description: str = DEFAULT_ROLE_DESCRIPTION,
    temperature: float = 0.0,
    seed: int = 0,
    timeout: int = 300,
) -> None:
    resolved_root = Path(root)
    _write_json(resolved_root / "config" / "organization.json", _organization_payload())
    _write_dialects(resolved_root)
    _write_json(
        resolved_root / "model" / "core" / "roles" / f"{role_name}.json",
        _role_payload(
            role_name=role_name,
            description=role_description,
            tools=["read_file", "write_file", "list_directory", "update_issue_status"],
        ),
    )
    _write_json(
        resolved_root / "model" / "core" / "roles" / f"{DEFAULT_REVIEWER_ROLE_NAME}.json",
        _role_payload(
            role_name=DEFAULT_REVIEWER_ROLE_NAME,
            description=DEFAULT_REVIEWER_DESCRIPTION,
            tools=["read_file", "list_directory", "update_issue_status"],
        ),
    )
    _write_json(
        resolved_root / "model" / "core" / "roles" / f"{DEFAULT_GUARD_ROLE_NAME}.json",
        _role_payload(
            role_name=DEFAULT_GUARD_ROLE_NAME,
            description=DEFAULT_GUARD_DESCRIPTION,
            tools=["read_file", "list_directory", "update_issue_status"],
        ),
    )
    _write_json(
        resolved_root / "model" / "core" / "teams" / f"{team_name}.json",
        _team_payload(team_name=team_name, role_name=role_name),
    )
    _write_json(
        resolved_root / "model" / "core" / "environments" / f"{DEFAULT_ENV_NAME}.json",
        _environment_payload(model=environment_model, temperature=temperature, seed=seed, timeout=timeout),
    )
    _write_json(
        resolved_root / "model" / "core" / "epics" / f"{epic_id}.json",
        _epic_payload(
            epic_id=epic_id,
            team_name=team_name,
            role_name=role_name,
            environment_model=environment_model,
            issues=issues,
        ),
    )


def run_root(workspace: Path, session_id: str) -> Path:
    return Path(workspace) / "runs" / str(session_id).strip()


def run_summary(workspace: Path, session_id: str) -> dict[str, Any]:
    path = run_root(workspace, session_id) / "run_summary.json"
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def protocol_events(workspace: Path, session_id: str) -> list[dict[str, Any]]:
    path = run_root(workspace, session_id) / "events.log"
    if not path.exists():
        return []
    return [dict(row) for row in AppendOnlyRunLedger(path).replay_events()]


def runtime_events(workspace: Path, session_id: str) -> list[dict[str, Any]]:
    path = Path(workspace) / "agent_output" / "observability" / "runtime_events.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            continue
        if str(payload.get("session_id") or "").strip() != str(session_id).strip():
            continue
        rows.append(payload)
    return rows


def workspace_log_records(
    workspace: Path,
    session_id: str,
    *,
    event_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    log_path = Path(workspace) / "orket.log"
    if not log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            continue
        data = payload.get("data")
        if not isinstance(data, dict):
            continue
        if str(data.get("session_id") or "").strip() != str(session_id).strip():
            continue
        event_name = str(payload.get("event") or "").strip()
        if event_names is not None and event_name not in event_names:
            continue
        rows.append(payload)
    return rows


def collect_artifact_hits(workspace: Path, session_id: str, names: Sequence[str]) -> dict[str, list[str]]:
    observability_root = Path(workspace) / "observability" / str(session_id).strip()
    hits: dict[str, list[str]] = {}
    for name in names:
        if observability_root.exists():
            paths = sorted(observability_root.rglob(str(name)))
        else:
            paths = []
        hits[str(name)] = [path.relative_to(workspace).as_posix() for path in paths if path.is_file()]
    return hits


def observability_inventory(workspace: Path, session_id: str) -> list[dict[str, Any]]:
    observability_root = Path(workspace) / "observability" / str(session_id).strip()
    if not observability_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(observability_root.rglob("*")):
        if not path.is_file():
            continue
        rows.append(
            {
                "path": path.relative_to(workspace).as_posix(),
                "size_bytes": path.stat().st_size,
            }
        )
    return rows


def unique_issue_order(
    events: Sequence[dict[str, Any]],
    *,
    event_name: str,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in events:
        if str(row.get("event") or "").strip() != event_name:
            continue
        issue_id = str(row.get("issue_id") or "").strip()
        if not issue_id or issue_id in seen:
            continue
        seen.add(issue_id)
        ordered.append(issue_id)
    return ordered


def simulate_dynamic_priority_order(issues: Sequence[dict[str, Any]]) -> list[str]:
    state = [deepcopy(dict(issue)) for issue in issues]
    completed: set[str] = set()
    for issue in state:
        deps = [str(item) for item in issue.get("depends_on", []) if str(item).strip()]
        issue["depends_on"] = deps
        issue["status"] = "ready" if not deps else "blocked"

    ordered: list[str] = []
    while True:
        ready_queue = CriticalPathEngine.get_priority_queue(state)
        if not ready_queue:
            return ordered
        next_issue_id = ready_queue[0]
        ordered.append(next_issue_id)
        completed.add(next_issue_id)
        for issue in state:
            issue_id = str(issue.get("id") or "").strip()
            if issue_id == next_issue_id:
                issue["status"] = "done"
                continue
            deps = issue.get("depends_on", [])
            if issue.get("status") == "done":
                continue
            issue["status"] = "ready" if set(deps).issubset(completed) else "blocked"


def write_report(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return write_payload_with_diff_ledger(Path(path), payload)


def is_environment_blocker(error: Exception) -> bool:
    text = str(error).lower()
    tokens = (
        "ollama",
        "connection refused",
        "timed out",
        "provider",
        "model",
        "not found",
        "no connection",
        "http",
    )
    return any(token in text for token in tokens)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _organization_payload() -> dict[str, Any]:
    return {
        "name": "Probe Org",
        "vision": "Observe the cards engine with a real local model.",
        "ethos": "Truthful probes over optimistic demos.",
        "branding": {"design_dos": [], "design_donts": []},
        "architecture": {"idesign_threshold": 7, "preferred_stack": {}, "cicd_rules": []},
        "departments": ["core"],
        "process_rules": {"small_project_builder_variant": DEFAULT_ROLE_NAME},
    }


def _write_dialects(root: Path) -> None:
    for dialect_name in _DIALECTS:
        _write_json(
            root / "model" / "core" / "dialects" / f"{dialect_name}.json",
            {
                "model_family": dialect_name,
                "dsl_format": "JSON",
                "constraints": [],
                "hallucination_guard": "Do not invent files, tools, or runtime state.",
                "prompt_metadata": {
                    "id": f"dialect.{dialect_name}",
                    "version": "1.0.0",
                    "status": "stable",
                },
            },
        )


def _role_payload(*, role_name: str, description: str, tools: Sequence[str]) -> dict[str, Any]:
    return {
        "id": role_name.upper(),
        "name": role_name,
        "type": "utility",
        "description": description,
        "tools": list(tools),
        "prompt_metadata": {
            "id": f"role.{role_name}",
            "version": "1.0.0",
            "status": "stable",
            "owner": "probe",
        },
    }


def _team_payload(*, team_name: str, role_name: str) -> dict[str, Any]:
    return {
        "name": team_name,
        "description": "Probe-only small-project team.",
        "seats": {
            role_name: {
                "name": "Probe Builder",
                "roles": [role_name],
            },
            DEFAULT_REVIEWER_ROLE_NAME: {
                "name": "Probe Reviewer",
                "roles": [DEFAULT_REVIEWER_ROLE_NAME],
            },
            DEFAULT_GUARD_ROLE_NAME: {
                "name": "Probe Guard",
                "roles": [DEFAULT_GUARD_ROLE_NAME],
            }
        },
    }


def _environment_payload(*, model: str, temperature: float, seed: int, timeout: int) -> dict[str, Any]:
    return {
        "name": DEFAULT_ENV_NAME,
        "description": "Probe environment",
        "model": str(model),
        "temperature": float(temperature),
        "seed": int(seed),
        "timeout": int(timeout),
        "params": {},
    }


def _epic_payload(
    *,
    epic_id: str,
    team_name: str,
    role_name: str,
    environment_model: str,
    issues: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": epic_id,
        "name": epic_id,
        "type": "epic",
        "status": "ready",
        "team": team_name,
        "environment": DEFAULT_ENV_NAME,
        "description": "Phase 1 cards engine probe workload.",
        "architecture_governance": {"idesign": False, "pattern": "Probe"},
        "params": {
            "model_overrides": {
                role_name: str(environment_model),
                DEFAULT_REVIEWER_ROLE_NAME: str(environment_model),
                DEFAULT_GUARD_ROLE_NAME: str(environment_model),
            }
        },
        "issues": [dict(issue) for issue in issues],
    }
