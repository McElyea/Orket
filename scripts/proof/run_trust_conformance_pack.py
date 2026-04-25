#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.finite_trust_kernel_model import evaluate_finite_trust_kernel_model
from scripts.proof.governed_change_packet_contract import (
    DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT,
    DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT,
    load_json_object,
    resolve_repo_path,
)
from scripts.proof.governed_change_packet_verifier import verify_governed_change_packet_payload
from scripts.proof.governed_change_packet_workflow import run_governed_repo_change_packet_flow
from scripts.proof.trusted_repo_change_contract import (
    DEFAULT_CAMPAIGN_OUTPUT,
    DEFAULT_OFFLINE_OUTPUT,
    DEFAULT_WORKSPACE_ROOT,
    PROOF_RESULTS_ROOT,
    TARGET_CLAIM_TIER,
    TRUSTED_REPO_COMPARE_SCOPE,
    relative_to_repo,
    stable_json_digest,
)

CONFORMANCE_SUMMARY_SCHEMA_VERSION = "portable_trust_conformance_summary.v1"
DEFAULT_CONFORMANCE_OUTPUT = PROOF_RESULTS_ROOT / "trust_conformance_summary.json"
DEFAULT_FINITE_MODEL_OUTPUT = PROOF_RESULTS_ROOT / "finite_trust_kernel_model.json"


def run_trust_conformance_pack(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    output: Path = DEFAULT_CONFORMANCE_OUTPUT,
    finite_model_output: Path = DEFAULT_FINITE_MODEL_OUTPUT,
    packet_output: Path = DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT,
    packet_verifier_output: Path = DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT,
    verify_fixture: bool = False,
    packet_input: Path | None = None,
) -> dict[str, Any]:
    os.environ.setdefault("ORKET_DISABLE_SANDBOX", "1")
    substeps: list[dict[str, str]] = []
    if verify_fixture:
        if packet_input is None:
            raise ValueError("conformance_packet_input_required")
        refs = _verify_supplied_packet(packet_input, substeps=substeps)
    else:
        refs = _generate_positive_packet(
            workspace_root=workspace_root,
            packet_output=packet_output,
            packet_verifier_output=packet_verifier_output,
            substeps=substeps,
        )
    artifacts = _load_positive_artifacts(refs)
    finite_model = evaluate_finite_trust_kernel_model(
        artifacts["campaign_report"],
        requested_claims=[TARGET_CLAIM_TIER],
        evidence_ref=refs["campaign_report"],
    )
    persisted_model = write_payload_with_diff_ledger(finite_model_output.resolve(), finite_model)
    substeps.append(_substep("finite_model", "evaluate_finite_trust_kernel_model", refs["campaign_report"], relative_to_repo(finite_model_output.resolve()), persisted_model.get("observed_result")))
    negatives = _negative_cases(artifacts, refs)
    summary = _summary(
        mode="supplied_fixture_verification" if verify_fixture else "generated_fixture_conformance",
        refs=refs,
        finite_model_ref=relative_to_repo(finite_model_output.resolve()),
        finite_model=persisted_model,
        packet_verifier=artifacts["packet_verifier"],
        negative_cases=negatives,
        substeps=substeps,
    )
    return write_payload_with_diff_ledger(output.resolve(), summary)


def _generate_positive_packet(*, workspace_root: Path, packet_output: Path, packet_verifier_output: Path, substeps: list[dict[str, str]]) -> dict[str, str]:
    result = run_governed_repo_change_packet_flow(
        workspace_root=workspace_root,
        packet_output=packet_output,
        verify_output=packet_verifier_output,
    )
    substeps.append(_substep("positive_packet_generation", "run_governed_repo_change_packet_flow", "", str(result.get("packet_ref") or ""), result.get("packet", {}).get("observed_result")))
    substeps.append(_substep("packet_verifier", "verify_governed_change_packet_payload", str(result.get("packet_ref") or ""), str(result.get("packet_verifier_ref") or ""), result.get("packet_verifier", {}).get("observed_result")))
    return {
        "packet": str(result.get("packet_ref") or ""),
        "packet_verifier": str(result.get("packet_verifier_ref") or ""),
        "campaign_report": str(result.get("campaign_ref") or relative_to_repo(DEFAULT_CAMPAIGN_OUTPUT)),
        "offline_verifier_report": str(result.get("offline_ref") or relative_to_repo(DEFAULT_OFFLINE_OUTPUT)),
        "witness_bundle": _witness_bundle_ref(result),
        "validator_report": _validator_ref(result),
    }


def _verify_supplied_packet(packet_input: Path, *, substeps: list[dict[str, str]]) -> dict[str, str]:
    packet_path = packet_input.resolve()
    packet = load_json_object(packet_path)
    verifier = verify_governed_change_packet_payload(packet, evidence_ref=relative_to_repo(packet_path))
    substeps.append(_substep("supplied_packet_verifier", "verify_governed_change_packet_payload", relative_to_repo(packet_path), "support-only:conformance-summary", verifier.get("observed_result")))
    manifest = _manifest_by_role(packet)
    return {
        "packet": relative_to_repo(packet_path),
        "packet_verifier": "support-only:in-memory",
        "campaign_report": str(manifest.get("campaign_report", {}).get("path") or ""),
        "offline_verifier_report": str(manifest.get("offline_verifier_report", {}).get("path") or ""),
        "witness_bundle": str(manifest.get("witness_bundle", {}).get("path") or ""),
        "validator_report": str(manifest.get("validator_report", {}).get("path") or ""),
        "_packet_verifier_payload": verifier,
    }


def _load_positive_artifacts(refs: dict[str, str]) -> dict[str, Any]:
    packet = load_json_object(resolve_repo_path(refs["packet"]))
    packet_verifier = refs.get("_packet_verifier_payload") or load_json_object(resolve_repo_path(refs["packet_verifier"]))
    campaign = load_json_object(resolve_repo_path(refs["campaign_report"]))
    offline = load_json_object(resolve_repo_path(refs["offline_verifier_report"]))
    bundle = load_json_object(resolve_repo_path(refs["witness_bundle"]))
    validator = load_json_object(resolve_repo_path(refs["validator_report"]))
    return {"packet": packet, "packet_verifier": packet_verifier, "campaign_report": campaign, "offline_report": offline, "witness_bundle": bundle, "validator_report": validator}


def _negative_cases(artifacts: dict[str, Any], refs: dict[str, str]) -> list[dict[str, Any]]:
    bundle_cases: list[tuple[str, str, Callable[[dict[str, Any]], None], str]] = [
        ("missing_final_truth", refs["witness_bundle"], lambda item: item["authority_lineage"].pop("final_truth", None), "missing_final_truth"),
        ("missing_operator_decision", refs["witness_bundle"], lambda item: item["authority_lineage"].pop("operator_action", None), "missing_approval_resolution"),
        ("missing_effect_evidence", refs["witness_bundle"], lambda item: item["authority_lineage"].pop("effect_journal", None), "missing_effect_evidence"),
        ("validator_failure", refs["witness_bundle"], lambda item: item["validator_result"].__setitem__("validation_result", "fail"), "validator_failed"),
        ("authority_digest_drift", refs["witness_bundle"], lambda item: item["contract_verdict"].__setitem__("verdict_signature_digest", "sha256:drift"), "contract_verdict_drift"),
    ]
    cases = [_bundle_negative(case_id, source, artifacts["witness_bundle"], mutate, expected) for case_id, source, mutate, expected in bundle_cases]
    cases.append(_campaign_negative("compare_scope_drift", refs["campaign_report"], artifacts["campaign_report"], lambda item: item.__setitem__("compare_scope", "other_scope"), "compare_scope_mismatch"))
    cases.append(_packet_projection_negative(artifacts["packet"], refs["packet"]))
    cases.append(_unsupported_claim_negative(artifacts["campaign_report"], refs["campaign_report"]))
    return cases


def _bundle_negative(case_id: str, source_ref: str, bundle: dict[str, Any], mutate: Callable[[dict[str, Any]], None], expected: str) -> dict[str, Any]:
    corrupted = copy.deepcopy(bundle)
    mutate(corrupted)
    model = evaluate_finite_trust_kernel_model(corrupted)
    return _negative_result(case_id, source_ref, expected, model.get("missing_evidence") or model.get("claim_downgrade_reasons") or [], model.get("observed_result"), "finite_model", f"bundle mutation for {case_id}")


def _campaign_negative(case_id: str, source_ref: str, campaign: dict[str, Any], mutate: Callable[[dict[str, Any]], None], expected: str) -> dict[str, Any]:
    corrupted = copy.deepcopy(campaign)
    mutate(corrupted)
    model = evaluate_finite_trust_kernel_model(corrupted, requested_claims=[TARGET_CLAIM_TIER])
    return _negative_result(case_id, source_ref, expected, model.get("missing_evidence") or [], model.get("observed_result"), "finite_model", f"campaign mutation for {case_id}")


def _packet_projection_negative(packet: dict[str, Any], source_ref: str) -> dict[str, Any]:
    corrupted = copy.deepcopy(packet)
    for item in corrupted.get("artifact_manifest") or []:
        if isinstance(item, dict) and item.get("role") == "operator_summary":
            item["classification"] = "authority_bearing"
    report = verify_governed_change_packet_payload(corrupted, evidence_ref=source_ref)
    observed = list(report.get("contradictions") or []) + list(report.get("missing_evidence") or [])
    return _negative_result("projection_only_masquerades_as_authority", source_ref, "packet_operator_summary_masquerades_as_authority", observed, report.get("observed_result"), "packet_verifier", "operator_summary classification changed to authority_bearing")


def _unsupported_claim_negative(campaign: dict[str, Any], source_ref: str) -> dict[str, Any]:
    model = evaluate_finite_trust_kernel_model(campaign, requested_claims=["replay_deterministic"])
    return _negative_result("unsupported_claim_request", source_ref, "replay_evidence_missing", model.get("claim_downgrade_reasons") or [], model.get("observed_result"), "finite_model", "requested replay_deterministic without replay evidence")


def _negative_result(case_id: str, source_ref: str, expected: str, observed: list[Any], observed_result: Any, verifier: str, corruption: str) -> dict[str, Any]:
    observed_reasons = [str(item) for item in observed]
    passed = expected in observed_reasons and observed_result in {"failure", "partial success"}
    return {
        "case_id": case_id,
        "classification": "generated_corruption",
        "source_fixture_ref": source_ref,
        "corruption_applied": corruption,
        "verifier": verifier,
        "expected_reason_code": expected,
        "observed_reason_codes": observed_reasons,
        "observed_result": str(observed_result or ""),
        "result": "pass" if passed else "fail",
    }


def _summary(
    *,
    mode: str,
    refs: dict[str, str],
    finite_model_ref: str,
    finite_model: dict[str, Any],
    packet_verifier: dict[str, Any],
    negative_cases: list[dict[str, Any]],
    substeps: list[dict[str, str]],
) -> dict[str, Any]:
    positive_ok = finite_model.get("observed_result") == "success" and packet_verifier.get("observed_result") == "success"
    negative_ok = all(item.get("result") == "pass" for item in negative_cases)
    observed_result = "success" if positive_ok and negative_ok else ("partial success" if positive_ok or negative_ok else "failure")
    return {
        "schema_version": CONFORMANCE_SUMMARY_SCHEMA_VERSION,
        "proof_kind": "fixture",
        "mode": mode,
        "observed_path": "primary" if observed_result == "success" else "blocked",
        "observed_result": observed_result,
        "adopted_compare_scopes": [TRUSTED_REPO_COMPARE_SCOPE],
        "selected_claim_tier": finite_model.get("claim_tier"),
        "allowed_claims": list(finite_model.get("allowed_claims") or []),
        "forbidden_claims": list(finite_model.get("forbidden_claims") or []),
        "positive_case_results": [_positive_case(finite_model, packet_verifier)],
        "negative_case_results": negative_cases,
        "stable_signature_digests": _signature_digests(finite_model, packet_verifier),
        "artifact_refs": _artifact_refs(refs, finite_model_ref),
        "verifier_substeps": substeps,
        "authority_boundary": "summary is claim-supporting derived evidence only; underlying witness, validator, offline verifier, and packet verifier artifacts remain authority-bearing or claim-bearing surfaces",
    }


def _positive_case(finite_model: dict[str, Any], packet_verifier: dict[str, Any]) -> dict[str, str]:
    passed = finite_model.get("observed_result") == "success" and packet_verifier.get("observed_result") == "success"
    return {"case_id": "positive_repo_change_conformance", "result": "pass" if passed else "fail", "finite_model_result": str(finite_model.get("observed_result") or ""), "packet_verifier_result": str(packet_verifier.get("observed_result") or "")}


def _signature_digests(finite_model: dict[str, Any], packet_verifier: dict[str, Any]) -> dict[str, str]:
    return {
        "finite_model": str(finite_model.get("model_signature_digest") or ""),
        "packet_verifier": str(packet_verifier.get("report_signature_digest") or ""),
        "summary_basis": stable_json_digest({"finite_model": finite_model.get("model_signature_digest"), "packet_verifier": packet_verifier.get("report_signature_digest")}),
    }


def _artifact_refs(refs: dict[str, str], finite_model_ref: str) -> list[dict[str, str]]:
    roles = {"packet": "operator_entry_artifact", "packet_verifier": "claim_bearing_verifier_output", "campaign_report": "authority_bearing_input_evidence", "offline_verifier_report": "claim_bearing_verifier_output", "witness_bundle": "authority_bearing_input_evidence", "validator_report": "authority_bearing_input_evidence"}
    artifacts = [{"role": role, "classification": roles[role], "path": refs[role]} for role in roles]
    artifacts.append({"role": "finite_model_report", "classification": "claim_supporting_derived_evidence", "path": finite_model_ref})
    return artifacts


def _substep(name: str, command: str, input_ref: str, output_ref: str, observed_result: Any) -> dict[str, str]:
    return {"name": name, "command_or_function": command, "input_ref": input_ref, "output_ref": output_ref, "observed_result": str(observed_result or "")}


def _manifest_by_role(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("role") or ""): item for item in packet.get("artifact_manifest") or [] if isinstance(item, dict)}


def _witness_bundle_ref(result: dict[str, Any]) -> str:
    packet = result.get("packet") if isinstance(result.get("packet"), dict) else {}
    return str(_manifest_by_role(packet).get("witness_bundle", {}).get("path") or "")


def _validator_ref(result: dict[str, Any]) -> str:
    packet = result.get("packet") if isinstance(result.get("packet"), dict) else {}
    return str(_manifest_by_role(packet).get("validator_report", {}).get("path") or "")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the portable trust conformance pack.")
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT), help="Fixture workspace root for generation mode.")
    parser.add_argument("--output", default=str(DEFAULT_CONFORMANCE_OUTPUT), help="Stable conformance summary output path.")
    parser.add_argument("--finite-model-output", default=str(DEFAULT_FINITE_MODEL_OUTPUT), help="Stable finite-model support output path.")
    parser.add_argument("--packet-output", default=str(DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT), help="Packet output path in generation mode.")
    parser.add_argument("--packet-verifier-output", default=str(DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT), help="Packet verifier output path in generation mode.")
    parser.add_argument("--verify-fixture", action="store_true", help="Verify a supplied packet read-only instead of generating one.")
    parser.add_argument("--packet", help="Supplied governed change packet path for --verify-fixture mode.")
    parser.add_argument("--json", action="store_true", help="Print the persisted conformance summary.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    summary = run_trust_conformance_pack(
        workspace_root=Path(str(args.workspace_root)),
        output=Path(str(args.output)),
        finite_model_output=Path(str(args.finite_model_output)),
        packet_output=Path(str(args.packet_output)),
        packet_verifier_output=Path(str(args.packet_verifier_output)),
        verify_fixture=bool(args.verify_fixture),
        packet_input=Path(str(args.packet)).resolve() if args.packet else None,
    )
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=True))
    else:
        print(f"observed_result={summary.get('observed_result')} claim_tier={summary.get('selected_claim_tier')} output={relative_to_repo(Path(str(args.output)).resolve())}")
    return 0 if summary.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
