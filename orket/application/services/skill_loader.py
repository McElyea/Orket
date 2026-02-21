from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orket.application.services.skills_validator import validate_skill_manifest


@dataclass
class SkillLoaderError(Exception):
    error_code: str
    message: str
    skill_id: str
    skill_version: str
    skill_contract_version_seen: str
    validation_stage: str
    retryable: bool
    entrypoint_id: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "error_code": self.error_code,
            "message": self.message,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "skill_contract_version_seen": self.skill_contract_version_seen,
            "validation_stage": self.validation_stage,
            "retryable": self.retryable,
        }
        if self.entrypoint_id:
            payload["entrypoint_id"] = self.entrypoint_id
        return payload


def load_skill_manifest_or_raise(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Contract-first Skill loader: reject invalid manifests with canonical payloads.
    """
    validation = validate_skill_manifest(payload)
    if validation.get("contract_valid") is True and validation.get("errors") == []:
        return {"manifest": payload, "validation": validation}

    errors = list(validation.get("errors") or [])
    code = "ERR_CONTRACT_INVALID"
    stage = "loader"
    entrypoint_id: str | None = None
    for item in errors:
        text = str(item)
        if text.startswith("entrypoint:"):
            parts = text.split(":")
            if len(parts) >= 3:
                entrypoint_id = parts[1].strip() or None
                break
    if any(str(item).startswith("schema:") for item in errors):
        code = "ERR_SCHEMA_INVALID"
        stage = "schema"
    elif "contract:unsupported_version" in errors:
        code = "ERR_CONTRACT_UNSUPPORTED_VERSION"
        stage = "contract_version"
    elif "contract:manifest_digest_missing_algorithm_prefix" in errors:
        code = "ERR_CONTRACT_INVALID"
        stage = "contract"
    elif any(str(item).endswith(":runtime_unpinned") for item in errors):
        code = "ERR_RUNTIME_UNPINNED"
        stage = "runtime"
    elif any(str(item).endswith(":fingerprint_incomplete") for item in errors):
        code = "ERR_FINGERPRINT_INCOMPLETE"
        stage = "fingerprint"
    elif any(str(item).endswith(":side_effect_undeclared") for item in errors):
        code = "ERR_SIDE_EFFECT_UNDECLARED"
        stage = "side_effect"
    elif any(str(item).endswith(":permission_undeclared") for item in errors):
        code = "ERR_PERMISSION_UNDECLARED"
        stage = "permissions"

    raise SkillLoaderError(
        error_code=code,
        message="Skill contract validation failed",
        skill_id=str(payload.get("skill_id") or "unknown"),
        skill_version=str(payload.get("skill_version") or "unknown"),
        skill_contract_version_seen=str(payload.get("skill_contract_version") or "unknown"),
        validation_stage=stage,
        retryable=False,
        entrypoint_id=entrypoint_id,
    )
