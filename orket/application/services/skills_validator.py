from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from orket.core.contracts import SkillManifestContract

SUPPORTED_SKILL_CONTRACT_VERSIONS = {"1.0.5"}
VALIDATION_POLICY_VERSION = "skill.validation.v1"
DETERMINISTIC_VALIDATION_TIMESTAMP = "1970-01-01T00:00:00Z"


def validate_skill_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a Skill manifest and return machine-readable validation metadata.
    """
    errors: list[str] = []
    contract_valid = False
    determinism_eligible = False
    manifest: SkillManifestContract | None = None

    try:
        manifest = SkillManifestContract.model_validate(payload)
        contract_valid = True
    except ValidationError as exc:
        errors.extend([f"schema:{err.get('loc')}: {err.get('msg')}" for err in exc.errors()])

    if manifest is not None:
        if manifest.skill_contract_version not in SUPPORTED_SKILL_CONTRACT_VERSIONS:
            errors.append("contract:unsupported_version")
        if ":" not in manifest.manifest_digest:
            errors.append("contract:manifest_digest_missing_algorithm_prefix")

        # Minimal deterministic eligibility heuristic for v1.
        determinism_eligible = (
            contract_valid
            and not errors
            and all(bool(ep.args_fingerprint_fields) and bool(ep.result_fingerprint_fields) for ep in manifest.entrypoints)
        )

    validation = {
        "contract_valid": bool(contract_valid and not any(err.startswith("schema:") for err in errors)),
        "determinism_eligible": bool(determinism_eligible),
        "side_effect_risk": "unknown",
        "fingerprint_completeness": "complete" if determinism_eligible else "incomplete",
        "permission_risk": "unknown",
        "trust_level": "untrusted" if errors else "validated",
        "validation_policy_version": VALIDATION_POLICY_VERSION,
        # Keep validator output deterministic for identical payloads.
        "validation_timestamp": DETERMINISTIC_VALIDATION_TIMESTAMP,
        "errors": errors,
    }
    return validation
