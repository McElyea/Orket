from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.proof.outward_run_witness_contract import (
    BUNDLE_ONLY_BLOCKER,
    COMPARE_SCOPE,
    OPERATOR_SURFACE,
    REPORT_SCHEMA_VERSION,
)


def rejected_report(
    *,
    failure_code: str,
    scope: str = COMPARE_SCOPE,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_report(
        result="rejected",
        scope=scope,
        bundle=bundle or {},
        missing_evidence=[failure_code],
        invariant_model=_empty_invariant_model(failure_code),
        invariant_signature=_signature(
            scope=scope,
            result="rejected",
            claim_tier_assigned="none",
            invariant_statuses={},
            missing_evidence=[failure_code],
        ),
    )


def bundle_only_report(bundle: dict[str, Any], *, scope: str = COMPARE_SCOPE) -> dict[str, Any]:
    return build_report(
        result="downgraded",
        scope=scope,
        bundle=bundle,
        missing_evidence=[BUNDLE_ONLY_BLOCKER],
        invariant_model=_empty_invariant_model(BUNDLE_ONLY_BLOCKER),
        invariant_signature=_signature(
            scope=scope,
            result="downgraded",
            claim_tier_assigned="none",
            invariant_statuses={},
            missing_evidence=[BUNDLE_ONLY_BLOCKER],
        ),
    )


def build_report(
    *,
    result: str,
    scope: str,
    bundle: dict[str, Any],
    missing_evidence: list[str],
    invariant_model: dict[str, Any],
    invariant_signature: str,
    claim_tier_assigned: str = "none",
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "bundle_id": str(bundle.get("bundle_id") or ""),
        "run_id": str(bundle.get("run_id") or ""),
        "compare_scope": scope,
        "result": result,
        "claim_tier_request": str(bundle.get("claim_tier_request") or ""),
        "claim_tier_assigned": claim_tier_assigned,
        "invariant_model": invariant_model,
        "missing_evidence": list(dict.fromkeys(missing_evidence)),
        "invariant_signature": invariant_signature,
    }


def _empty_invariant_model(failure_code: str) -> dict[str, Any]:
    return {
        "schema_version": "outward_run_invariants.v1",
        "invariants": [
            {
                "id": "package-gate",
                "status": "failed",
                "failure_code": failure_code,
                "detail": None,
            }
        ],
    }


def _signature(
    *,
    scope: str,
    result: str,
    claim_tier_assigned: str,
    invariant_statuses: dict[str, str],
    missing_evidence: list[str],
) -> str:
    material = {
        "schema_version": "outward_run_invariants.v1",
        "compare_scope": scope,
        "operator_surface": OPERATOR_SURFACE,
        "result": result,
        "claim_tier_assigned": claim_tier_assigned,
        "invariants": dict(sorted(invariant_statuses.items())),
        "missing_evidence": sorted(set(missing_evidence)),
    }
    encoded = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
