from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DIALECTS = ("qwen", "llama3", "deepseek-r1", "phi", "generic")
_ROLE_CONFIGS = {
    "requirements_analyst": {
        "tools": ["write_file", "update_issue_status"],
        "description": (
            "Produce concrete requirements for a tiny CLI summation program. "
            "You must write agent_output/requirements.txt and then set status to code_review. "
            "Do not call comment or context-only tools."
        ),
    },
    "architect": {
        "tools": ["read_file", "write_file", "update_issue_status"],
        "description": (
            "Design a one-class implementation based on requirements. "
            "You must write architecture decision JSON to agent_output/design.txt with recommendation, "
            "confidence, evidence, and frontend_framework when required, then set status to code_review. "
            "Do not call comment or context-only tools."
        ),
    },
    "coder": {
        "tools": ["read_file", "write_file", "update_issue_status"],
        "description": (
            "Implement from requirements and design. "
            "You must write runnable Python code to agent_output/main.py and then set status to code_review. "
            "Do not call comment or context-only tools."
        ),
    },
    "code_reviewer": {
        "tools": ["read_file", "update_issue_status"],
        "description": (
            "Review implementation against requirements and design. "
            "You must read every path listed in the Read Path Contract in the same response, "
            "then set status to code_review for guard finalization. "
            "Do not call add_issue_comment."
        ),
    },
    "integrity_guard": {
        "tools": ["read_file", "update_issue_status"],
        "description": (
            "Final gatekeeper. Decide approve/reject and finalize card status. "
            "Set status to done when acceptable; otherwise blocked. "
            "Do not call add_issue_comment."
        ),
    },
}


def write_core_acceptance_assets(root: Path, *, epic_id: str, environment_model: str = "dummy") -> None:
    resolved_root = Path(root)
    _ensure_model_dirs(resolved_root)
    _write_json(resolved_root / "config" / "organization.json", _organization_payload())
    _write_dialects(resolved_root)
    _write_roles(resolved_root)
    _write_json(resolved_root / "model" / "core" / "teams" / "standard.json", _team_payload())
    _write_json(
        resolved_root / "model" / "core" / "environments" / "standard.json",
        _environment_payload(environment_model),
    )
    _write_json(
        resolved_root / "model" / "core" / "epics" / f"{epic_id}.json",
        _epic_payload(epic_id=epic_id, environment_model=environment_model),
    )


def _ensure_model_dirs(root: Path) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    for directory in ("epics", "roles", "dialects", "teams", "environments"):
        (root / "model" / "core" / directory).mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(payload).encode("utf-8"))


def _organization_payload() -> dict[str, Any]:
    return {
        "name": "Acceptance Org",
        "vision": "Test",
        "ethos": "Test",
        "branding": {"design_dos": []},
        "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
        "departments": ["core"],
    }


def _write_dialects(root: Path) -> None:
    for dialect_name in _DIALECTS:
        _write_json(
            root / "model" / "core" / "dialects" / f"{dialect_name}.json",
            {
                "model_family": dialect_name,
                "dsl_format": "JSON",
                "constraints": [],
                "hallucination_guard": "None",
            },
        )


def _write_roles(root: Path) -> None:
    for role_name, role_config in _ROLE_CONFIGS.items():
        _write_json(
            root / "model" / "core" / "roles" / f"{role_name}.json",
            {
                "id": role_name.upper(),
                "summary": role_name,
                "type": "utility",
                "description": role_config["description"],
                "tools": list(role_config["tools"]),
            },
        )


def _team_payload() -> dict[str, Any]:
    return {
        "name": "standard",
        "seats": {
            "requirements_analyst": {"name": "Req", "roles": ["requirements_analyst"]},
            "architect": {"name": "Arch", "roles": ["architect"]},
            "coder": {"name": "Coder", "roles": ["coder"]},
            "code_reviewer": {"name": "CR", "roles": ["code_reviewer"]},
            "integrity_guard": {"name": "Guard", "roles": ["integrity_guard"]},
        },
    }


def _environment_payload(environment_model: str) -> dict[str, Any]:
    return {
        "name": "standard",
        "model": environment_model,
        "temperature": 0.0,
        "timeout": 300,
    }


def _epic_payload(*, epic_id: str, environment_model: str) -> dict[str, Any]:
    return {
        "id": epic_id,
        "name": "Acceptance Pipeline",
        "type": "epic",
        "team": "standard",
        "environment": "standard",
        "description": "Role-pipeline acceptance",
        "params": {
            "model_overrides": {
                "requirements_analyst": environment_model,
                "architect": environment_model,
                "coder": environment_model,
                "code_reviewer": environment_model,
                "integrity_guard": environment_model,
            }
        },
        "architecture_governance": {"idesign": False, "pattern": "Tactical"},
        "issues": [
            {"id": "REQ-1", "summary": "Write requirements", "seat": "requirements_analyst", "priority": "High"},
            {
                "id": "ARC-1",
                "summary": "Design one-class architecture",
                "seat": "architect",
                "priority": "High",
                "depends_on": ["REQ-1"],
            },
            {
                "id": "COD-1",
                "summary": "Implement based on design",
                "seat": "coder",
                "priority": "High",
                "depends_on": ["ARC-1"],
            },
            {
                "id": "REV-1",
                "summary": "Review against requirements",
                "seat": "code_reviewer",
                "priority": "High",
                "depends_on": ["COD-1"],
            },
        ],
    }
