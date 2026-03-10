from __future__ import annotations

from typing import Any


OBSERVABILITY_REDACTION_TEST_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_CHECK_IDS = {
    "env_secret_values_masked",
    "env_non_secret_values_preserved",
    "env_long_values_truncated",
    "workload_snapshot_redaction_shape",
}


def observability_redaction_test_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": OBSERVABILITY_REDACTION_TEST_CONTRACT_SCHEMA_VERSION,
        "checks": [
            {
                "check_id": "env_secret_values_masked",
                "surface": "scripts.common.evidence_environment.redact_env_value",
                "expected_behavior": "secret-like keys are replaced with <redacted>",
            },
            {
                "check_id": "env_non_secret_values_preserved",
                "surface": "scripts.common.evidence_environment.redact_env_value",
                "expected_behavior": "non-secret values are preserved when under max length",
            },
            {
                "check_id": "env_long_values_truncated",
                "surface": "scripts.common.evidence_environment.redact_env_value",
                "expected_behavior": "values over 256 chars are truncated with trailing ellipsis",
            },
            {
                "check_id": "workload_snapshot_redaction_shape",
                "surface": "orket.extensions.workload_artifacts.WorkloadArtifacts._redacted_snapshot",
                "expected_behavior": "redacted snapshot exposes only keys/item_count/payload_digest_sha256",
            },
        ],
    }


def validate_observability_redaction_test_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or observability_redaction_test_contract_snapshot())
    checks = list(contract.get("checks") or [])
    if not checks:
        raise ValueError("E_OBSERVABILITY_REDACTION_TEST_CONTRACT_EMPTY")

    observed_check_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("E_OBSERVABILITY_REDACTION_TEST_CONTRACT_ROW_SCHEMA")
        check_id = str(row.get("check_id") or "").strip()
        surface = str(row.get("surface") or "").strip()
        expected_behavior = str(row.get("expected_behavior") or "").strip()
        if not check_id:
            raise ValueError("E_OBSERVABILITY_REDACTION_TEST_CONTRACT_CHECK_ID_REQUIRED")
        if not surface:
            raise ValueError(f"E_OBSERVABILITY_REDACTION_TEST_CONTRACT_SURFACE_REQUIRED:{check_id}")
        if not expected_behavior:
            raise ValueError(f"E_OBSERVABILITY_REDACTION_TEST_CONTRACT_EXPECTED_BEHAVIOR_REQUIRED:{check_id}")
        observed_check_ids.append(check_id)

    if len(set(observed_check_ids)) != len(observed_check_ids):
        raise ValueError("E_OBSERVABILITY_REDACTION_TEST_CONTRACT_DUPLICATE_CHECK_ID")
    if set(observed_check_ids) != _EXPECTED_CHECK_IDS:
        raise ValueError("E_OBSERVABILITY_REDACTION_TEST_CONTRACT_CHECK_ID_SET_MISMATCH")
    return tuple(sorted(observed_check_ids))
