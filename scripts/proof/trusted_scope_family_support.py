from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.proof.trusted_run_witness_contract import now_utc_iso
from scripts.proof.trusted_scope_family_claims import evaluate_validator_backed_scope_offline_claim
from scripts.proof.trusted_scope_family_common import as_dict, text, unique, without_diff_ledger


@dataclass(frozen=True, slots=True)
class ValidatorBackedScopeConfig:
    compare_scope: str
    operator_surface: str
    fallback_claim_tier: str
    target_claim_tier: str
    bundle_schema_version: str = "trusted_run.witness_bundle.v1"
    report_schema_version: str = "trusted_run_witness_report.v1"


def build_validator_backed_campaign_report(
    reports: list[dict[str, Any]],
    *,
    config: ValidatorBackedScopeConfig,
    must_catch_outcomes: list[str],
    bundle_refs: list[str] | None = None,
    live_proof_refs: list[str] | None = None,
) -> dict[str, Any]:
    clean_reports = [without_diff_ledger(report) for report in reports]
    successes = [report for report in clean_reports if report.get("observed_result") == "success"]
    verdict_digests = _digest_set(successes, "contract_verdict", "verdict_signature_digest")
    validator_digests = {text(report.get("validator_signature_digest")) for report in successes}
    invariant_digests = {text(report.get("invariant_model_signature_digest")) for report in successes}
    substrate_digests = {text(report.get("substrate_signature_digest")) for report in successes}
    for digest_set in (validator_digests, invariant_digests, substrate_digests):
        digest_set.discard("")
    must_catch_sets = {tuple(report.get("must_catch_outcomes") or []) for report in successes}
    side_effect_free = bool(successes) and all(report.get("side_effect_free_verification") is True for report in successes)
    stable = (
        len(clean_reports) >= 2
        and len(successes) == len(clean_reports)
        and len(verdict_digests) == 1
        and len(validator_digests) == 1
        and len(invariant_digests) == 1
        and len(substrate_digests) == 1
        and len(must_catch_sets) == 1
        and side_effect_free
    )
    return {
        "schema_version": config.report_schema_version,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live",
        "observed_path": "primary" if clean_reports else "blocked",
        "observed_result": "success" if stable else ("partial success" if successes else "failure"),
        "claim_tier": config.target_claim_tier if stable else config.fallback_claim_tier,
        "compare_scope": config.compare_scope,
        "operator_surface": config.operator_surface,
        "run_count": len(clean_reports),
        "successful_verification_count": len(successes),
        "verdict_signature_digests": sorted(verdict_digests),
        "validator_signature_digests": sorted(validator_digests),
        "invariant_model_signature_digests": sorted(invariant_digests),
        "substrate_signature_digests": sorted(substrate_digests),
        "must_catch_outcomes": list(must_catch_outcomes),
        "must_catch_outcomes_stable": len(must_catch_sets) == 1 if successes else False,
        "validator_signature_stable": len(validator_digests) == 1 if successes else False,
        "invariant_model_signature_stable": len(invariant_digests) == 1 if successes else False,
        "substrate_signature_stable": len(substrate_digests) == 1 if successes else False,
        "side_effect_free_verification": side_effect_free,
        "bundle_refs": list(bundle_refs or []),
        "live_proof_refs": list(live_proof_refs or []),
        "bundle_reports": clean_reports,
        "missing_evidence": _campaign_missing_evidence(
            reports=clean_reports,
            stable=stable,
            verdict=verdict_digests,
            validator=validator_digests,
            invariant=invariant_digests,
            substrate=substrate_digests,
            side_effect_free=side_effect_free,
        ),
    }


def build_bundle_verification_failures(
    verdict: dict[str, Any],
    recomputed: dict[str, Any],
    invariant: dict[str, Any],
    substrate: dict[str, Any],
    *,
    side_effect_free: bool,
) -> list[str]:
    failures: list[str] = []
    if not verdict:
        failures.append("contract_verdict_missing")
    if text(verdict.get("verdict_signature_digest")) != text(recomputed.get("verdict_signature_digest")):
        failures.append("contract_verdict_drift")
    if recomputed.get("verdict") != "pass":
        failures.extend(str(item) for item in recomputed.get("failures") or [])
    if invariant.get("result") != "pass":
        failures.extend(str(item) for item in invariant.get("failures") or [])
    if substrate.get("result") != "pass":
        failures.extend(str(item) for item in substrate.get("failures") or [])
    if not side_effect_free:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    return unique(failures)


def _campaign_missing_evidence(
    *,
    reports: list[dict[str, Any]],
    stable: bool,
    verdict: set[str],
    validator: set[str],
    invariant: set[str],
    substrate: set[str],
    side_effect_free: bool,
) -> list[str]:
    if stable:
        return []
    failures: list[str] = []
    if len(reports) < 2:
        failures.append("repeat_evidence_missing")
    if any(report.get("observed_result") != "success" for report in reports):
        failures.append("bundle_verification_failed")
    for reason, items in (
        ("verdict_signature_not_stable", verdict),
        ("validator_signature_not_stable", validator),
        ("invariant_model_signature_not_stable", invariant),
        ("substrate_signature_not_stable", substrate),
    ):
        if len(items) != 1:
            failures.append(reason)
    if not side_effect_free:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    return unique(failures)


def _digest_set(reports: list[dict[str, Any]], key: str, digest_key: str) -> set[str]:
    values = {text(as_dict(report.get(key)).get(digest_key)) for report in reports}
    values.discard("")
    return values
