from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


DEFAULT_UTILITY_AGENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "code_assistant": {
        "profile_id": "code_assistant",
        "allowed_roles": ["architect", "coder", "reviewer"],
        "max_results": 5,
    },
    "ops_assistant": {
        "profile_id": "ops_assistant",
        "allowed_roles": ["architect", "coordinator"],
        "max_results": 5,
    },
}


@dataclass(frozen=True)
class MemoryAccessPolicyError(Exception):
    code: str
    message: str
    detail: Dict[str, Any]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "code": self.code,
            "message": self.message,
            "detail": dict(self.detail),
        }


def load_utility_agent_profiles(path: Path | None = None) -> Dict[str, Dict[str, Any]]:
    if path is None:
        return {key: dict(value) for key, value in DEFAULT_UTILITY_AGENT_PROFILES.items()}
    if not path.exists():
        return {key: dict(value) for key, value in DEFAULT_UTILITY_AGENT_PROFILES.items()}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MemoryAccessPolicyError(
            code="E_UTILITY_AGENT_PROFILE_INVALID",
            message="Profile payload must be a JSON object keyed by profile id.",
            detail={"path": str(path)},
        )
    rows: Dict[str, Dict[str, Any]] = {}
    for key in sorted(payload.keys()):
        row = payload[key]
        if not isinstance(row, dict):
            continue
        profile_id = str(row.get("profile_id") or key).strip()
        allowed_roles = sorted({str(role).strip() for role in (row.get("allowed_roles") or []) if str(role).strip()})
        max_results = max(1, int(row.get("max_results") or 5))
        rows[profile_id] = {
            "profile_id": profile_id,
            "allowed_roles": allowed_roles,
            "max_results": max_results,
        }
    return rows or {key: dict(value) for key, value in DEFAULT_UTILITY_AGENT_PROFILES.items()}


def resolve_utility_agent_profile(profile_id: str, profiles: Dict[str, Dict[str, Any]] | None = None) -> Dict[str, Any]:
    profiles = profiles or load_utility_agent_profiles()
    key = str(profile_id or "").strip()
    if not key:
        raise MemoryAccessPolicyError(
            code="E_UTILITY_AGENT_PROFILE_REQUIRED",
            message="utility agent profile id is required.",
            detail={"profile_id": profile_id},
        )
    profile = profiles.get(key)
    if not isinstance(profile, dict):
        raise MemoryAccessPolicyError(
            code="E_UTILITY_AGENT_PROFILE_UNKNOWN",
            message=f"Unknown utility agent profile '{key}'.",
            detail={"profile_id": key, "known_profiles": sorted(profiles.keys())},
        )
    return dict(profile)


def enforce_role_access(*, role: str, profile: Dict[str, Any]) -> None:
    allowed_roles = sorted({str(item).strip() for item in (profile.get("allowed_roles") or []) if str(item).strip()})
    normalized_role = str(role or "").strip()
    if normalized_role not in allowed_roles:
        raise MemoryAccessPolicyError(
            code="E_UTILITY_AGENT_ROLE_FORBIDDEN",
            message=f"Role '{normalized_role}' is not allowed for profile '{profile.get('profile_id', '')}'.",
            detail={
                "role": normalized_role,
                "profile_id": str(profile.get("profile_id") or ""),
                "allowed_roles": allowed_roles,
            },
        )


def normalize_retrieval_rows(rows: Iterable[Dict[str, Any]], *, limit: int) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "content": str(row.get("content") or ""),
                "metadata": dict(row.get("metadata") or {}),
                "score": float(row.get("score") or 0.0),
                "timestamp": str(row.get("timestamp") or ""),
                "id": int(row.get("id") or 0),
            }
        )
    normalized.sort(
        key=lambda item: (
            -float(item["score"]),
            str(item["timestamp"]),
            int(item["id"]),
        ),
        reverse=False,
    )
    max_rows = max(1, int(limit))
    return normalized[:max_rows]
