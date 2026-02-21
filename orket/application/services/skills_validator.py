from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from orket.core.contracts import SkillManifestContract

SUPPORTED_SKILL_CONTRACT_VERSIONS = {"1.0.5"}
VALIDATION_POLICY_VERSION = "skill.validation.v1"
DETERMINISTIC_VALIDATION_TIMESTAMP = "1970-01-01T00:00:00Z"
PINNED_RUNTIMES = {"python", "node", "container", "shell"}


def _permission_values(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        value = raw.strip()
        return {value} if value else set()
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    return set()


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
        runtime_pinning_ok = True
        fingerprints_complete = True
        side_effect_declarations_ok = True
        permissions_ok = True

        for ep in manifest.entrypoints:
            runtime = str(ep.runtime or "").strip().lower()
            entrypoint_id = str(ep.entrypoint_id or "").strip() or "unknown"

            if runtime in PINNED_RUNTIMES and not str(ep.runtime_version or "").strip():
                runtime_pinning_ok = False
                errors.append(f"entrypoint:{entrypoint_id}:runtime_unpinned")

            if not ep.args_fingerprint_fields or not ep.result_fingerprint_fields:
                fingerprints_complete = False
                errors.append(f"entrypoint:{entrypoint_id}:fingerprint_incomplete")

            if ep.side_effect_categories and not ep.side_effect_fingerprint_fields:
                side_effect_declarations_ok = False
                errors.append(f"entrypoint:{entrypoint_id}:side_effect_undeclared")

            requested = ep.requested_permissions if isinstance(ep.requested_permissions, dict) else {}
            required = ep.required_permissions if isinstance(ep.required_permissions, dict) else {}
            for scope, req_values in required.items():
                missing = _permission_values(req_values) - _permission_values(requested.get(scope))
                if missing:
                    permissions_ok = False
                    errors.append(f"entrypoint:{entrypoint_id}:permission_undeclared")
                    break

        determinism_eligible = bool(
            contract_valid
            and not errors
            and runtime_pinning_ok
            and fingerprints_complete
            and side_effect_declarations_ok
            and permissions_ok
        )

        side_effect_risk = "declared" if side_effect_declarations_ok else "undeclared"
        fingerprint_completeness = "complete" if fingerprints_complete else "incomplete"
        permission_risk = "declared" if permissions_ok else "undeclared"
    else:
        side_effect_risk = "unknown"
        fingerprint_completeness = "incomplete"
        permission_risk = "unknown"

    validation = {
        "contract_valid": bool(contract_valid and not any(err.startswith("schema:") for err in errors)),
        "determinism_eligible": bool(determinism_eligible),
        "side_effect_risk": side_effect_risk,
        "fingerprint_completeness": fingerprint_completeness,
        "permission_risk": permission_risk,
        "trust_level": "untrusted" if errors else "validated",
        "validation_policy_version": VALIDATION_POLICY_VERSION,
        # Keep validator output deterministic for identical payloads.
        "validation_timestamp": DETERMINISTIC_VALIDATION_TIMESTAMP,
        "errors": errors,
    }
    return validation
