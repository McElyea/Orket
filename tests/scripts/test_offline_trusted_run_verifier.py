from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.proof.offline_trusted_run_verifier import (
    COMPARE_SCOPE,
    FALLBACK_CLAIM_TIER,
    OFFLINE_VERIFIER_SCHEMA_VERSION,
    REPLAY_EVIDENCE_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    TEXT_IDENTITY_SCHEMA_VERSION,
    evaluate_offline_trusted_run_claim,
)
from scripts.proof.trusted_run_witness_support import (
    build_campaign_verification_report,
    verify_witness_bundle_payload,
)
from scripts.proof.verify_offline_trusted_run_claim import main as offline_verifier_main
from tests.helpers.trusted_run_witness_fixtures import valid_bundle


def test_bundle_input_proves_only_lab_claim() -> None:
    """Layer: contract. Verifies raw bundles remain lab-only without repeat evidence."""
    report = evaluate_offline_trusted_run_claim(valid_bundle(), evidence_ref="runs/sess-a/trusted_run_witness_bundle.json")

    assert report["schema_version"] == OFFLINE_VERIFIER_SCHEMA_VERSION
    assert report["input_mode"] == "bundle"
    assert report["observed_result"] == "success"
    assert report["claim_status"] == "allowed"
    assert report["claim_tier"] == FALLBACK_CLAIM_TIER
    assert report["allowed_claims"] == [FALLBACK_CLAIM_TIER]
    assert _forbidden_reasons(report, TARGET_CLAIM_TIER) == ["repeat_evidence_missing"]


def test_single_report_input_proves_only_lab_claim() -> None:
    """Layer: contract. Verifies single verifier reports do not become deterministic claims."""
    source = _single_report()

    report = evaluate_offline_trusted_run_claim(source, input_mode="single_report")

    assert report["observed_result"] == "success"
    assert report["claim_tier"] == FALLBACK_CLAIM_TIER
    assert report["allowed_claims"] == [FALLBACK_CLAIM_TIER]


def test_campaign_report_reaches_verdict_deterministic() -> None:
    """Layer: contract. Verifies stable campaign reports allow the verdict deterministic claim."""
    report = evaluate_offline_trusted_run_claim(_campaign_report(), requested_claims=[TARGET_CLAIM_TIER])

    assert report["input_mode"] == "campaign_report"
    assert report["observed_result"] == "success"
    assert report["claim_status"] == "allowed"
    assert report["claim_tier"] == TARGET_CLAIM_TIER
    assert report["allowed_claims"] == [FALLBACK_CLAIM_TIER, TARGET_CLAIM_TIER]
    assert _forbidden_reasons(report, "replay_deterministic") == ["replay_evidence_missing"]


def test_requested_replay_claim_downgrades_to_verdict_claim() -> None:
    """Layer: contract. Verifies missing replay evidence forbids replay without hiding verdict proof."""
    report = evaluate_offline_trusted_run_claim(
        _campaign_report(),
        requested_claims=["replay_deterministic"],
    )

    assert report["observed_result"] == "partial success"
    assert report["claim_status"] == "downgraded"
    assert report["claim_tier"] == TARGET_CLAIM_TIER
    assert _forbidden_reasons(report, "replay_deterministic") == ["replay_evidence_missing"]


def test_cli_writes_diff_ledger_report(tmp_path: Path) -> None:
    """Layer: integration. Verifies the CLI writes a stable diff-ledger JSON report."""
    input_path = tmp_path / "campaign.json"
    output_path = tmp_path / "offline.json"
    input_path.write_text(json.dumps(_campaign_report()), encoding="utf-8")

    exit_code = offline_verifier_main(["--input", str(input_path), "--output", str(output_path), "--claim", TARGET_CLAIM_TIER])

    assert exit_code == 0
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == OFFLINE_VERIFIER_SCHEMA_VERSION
    assert persisted["claim_tier"] == TARGET_CLAIM_TIER
    assert isinstance(persisted.get("diff_ledger"), list)


def test_cli_fails_when_requested_claim_is_downgraded(tmp_path: Path) -> None:
    """Layer: integration. Verifies forbidden requested claims are not false-green CLI exits."""
    input_path = tmp_path / "campaign.json"
    output_path = tmp_path / "offline.json"
    input_path.write_text(json.dumps(_campaign_report()), encoding="utf-8")

    exit_code = offline_verifier_main(
        ["--input", str(input_path), "--output", str(output_path), "--claim", "replay_deterministic"]
    )

    assert exit_code == 1
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["claim_status"] == "downgraded"


@pytest.mark.parametrize(
    ("corruption_id", "payload_factory", "input_mode", "expected"),
    [
        ("OVCL-CORR-001", lambda: {"schema_version": "unsupported"}, "auto", "schema_version_missing_or_unsupported"),
        ("OVCL-CORR-002", lambda: _single_report_with_compare_scope_drift(), "single_report", "compare_scope_mismatch"),
        ("OVCL-CORR-003", lambda: _single_report_with_operator_surface_drift(), "single_report", "operator_surface_mismatch"),
        ("OVCL-CORR-004", lambda: _bundle_with_run_id_drift(), "bundle", "canonical_run_id_drift"),
        ("OVCL-CORR-005", lambda: _bundle_without_final_truth(), "bundle", "missing_final_truth"),
        ("OVCL-CORR-006", lambda: _bundle_without_effect_evidence(), "bundle", "missing_effect_evidence"),
        ("OVCL-CORR-007", lambda: _single_report_without_side_effect_proof(), "single_report", "verifier_side_effect_absence_not_mechanically_proven"),
        ("OVCL-CORR-008", lambda: _single_report_campaign(), "campaign_report", "repeat_evidence_missing"),
        ("OVCL-CORR-009", lambda: _campaign_with_verdict_signature_drift(), "campaign_report", "verdict_signature_not_stable"),
        ("OVCL-CORR-010", lambda: _campaign_with_invariant_signature_drift(), "campaign_report", "invariant_model_signature_not_stable"),
        ("OVCL-CORR-011", lambda: _campaign_with_substrate_signature_drift(), "campaign_report", "substrate_signature_not_stable"),
        ("OVCL-CORR-012", lambda: _campaign_with_must_catch_drift(), "campaign_report", "must_catch_outcomes_not_stable"),
        ("OVCL-CORR-013", lambda: {}, "replay_report", "replay_evidence_missing"),
        ("OVCL-CORR-014", lambda: _replay_report_with_scope_drift(), "replay_report", "replay_compare_scope_mismatch"),
        ("OVCL-CORR-015", lambda: {}, "text_identity_report", "text_identity_evidence_missing"),
        ("OVCL-CORR-016", lambda: _text_report_with_hash_drift(), "text_identity_report", "text_hash_not_stable"),
    ],
)
def test_negative_claim_ladder_matrix_fails_closed(
    corruption_id: str,
    payload_factory: object,
    input_mode: str,
    expected: str,
) -> None:
    """Layer: contract. Verifies each offline claim-ladder corruption remains machine-readable."""
    report = evaluate_offline_trusted_run_claim(payload_factory(), input_mode=input_mode)

    assert expected in report["missing_evidence"] or expected in _all_forbidden_reasons(report), corruption_id
    if report["claim_status"] == "blocked":
        assert report["allowed_claims"] == [], corruption_id


def _single_report(session_id: str = "sess-a") -> dict[str, object]:
    return verify_witness_bundle_payload(valid_bundle(session_id=session_id))


def _campaign_report() -> dict[str, object]:
    return build_campaign_verification_report([_single_report("sess-a"), _single_report("sess-b")])


def _single_report_with_compare_scope_drift() -> dict[str, object]:
    report = _single_report()
    report["compare_scope"] = "other"
    return report


def _single_report_with_operator_surface_drift() -> dict[str, object]:
    report = _single_report()
    report["operator_surface"] = "other"
    return report


def _bundle_with_run_id_drift() -> dict[str, object]:
    bundle = valid_bundle()
    bundle["authority_lineage"]["run"]["run_id"] = "other"
    return bundle


def _bundle_without_final_truth() -> dict[str, object]:
    bundle = valid_bundle()
    bundle["authority_lineage"].pop("final_truth")
    return bundle


def _bundle_without_effect_evidence() -> dict[str, object]:
    bundle = valid_bundle()
    bundle["authority_lineage"].pop("effect_journal")
    return bundle


def _single_report_without_side_effect_proof() -> dict[str, object]:
    report = _single_report()
    report.pop("side_effect_free_verification")
    return report


def _single_report_campaign() -> dict[str, object]:
    return build_campaign_verification_report([_single_report()])


def _campaign_with_verdict_signature_drift() -> dict[str, object]:
    first = _single_report("sess-a")
    second = _single_report("sess-b")
    second["contract_verdict"]["verdict_signature_digest"] = "sha256:different"
    return build_campaign_verification_report([first, second])


def _campaign_with_invariant_signature_drift() -> dict[str, object]:
    first = _single_report("sess-a")
    second = _single_report("sess-b")
    second["invariant_model_signature_digest"] = "sha256:different"
    return build_campaign_verification_report([first, second])


def _campaign_with_substrate_signature_drift() -> dict[str, object]:
    first = _single_report("sess-a")
    second = _single_report("sess-b")
    second["substrate_signature_digest"] = "sha256:different"
    return build_campaign_verification_report([first, second])


def _campaign_with_must_catch_drift() -> dict[str, object]:
    first = _single_report("sess-a")
    second = copy.deepcopy(_single_report("sess-b"))
    second["must_catch_outcomes"] = ["different"]
    return build_campaign_verification_report([first, second])


def _replay_report_with_scope_drift() -> dict[str, object]:
    return {"schema_version": REPLAY_EVIDENCE_SCHEMA_VERSION, "compare_scope": "other"}


def _text_report_with_hash_drift() -> dict[str, object]:
    return {"schema_version": TEXT_IDENTITY_SCHEMA_VERSION, "compare_scope": COMPARE_SCOPE, "output_hash_stable": False}


def _forbidden_reasons(report: dict[str, object], claim_tier: str) -> list[str]:
    for item in report.get("forbidden_claims") or []:
        if item.get("claim_tier") == claim_tier:
            return list(item.get("reason_codes") or [])
    return []


def _all_forbidden_reasons(report: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    for item in report.get("forbidden_claims") or []:
        reasons.extend(str(reason) for reason in item.get("reason_codes") or [])
    return reasons
