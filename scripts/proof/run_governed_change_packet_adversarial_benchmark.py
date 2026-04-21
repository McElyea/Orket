#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.governed_change_packet_contract import (
    DEFAULT_GOVERNED_CHANGE_PACKET_BENCHMARK_OUTPUT,
    DEFAULT_GOVERNED_CHANGE_PACKET_BENCHMARK_WORKSPACE_ROOT,
)
from scripts.proof.governed_change_packet_verifier import verify_governed_change_packet_payload
from scripts.proof.governed_change_packet_workflow import run_governed_repo_change_packet_flow
from scripts.proof.trusted_repo_change_contract import OPERATOR_SURFACE, TRUSTED_REPO_COMPARE_SCOPE, now_utc_iso, relative_to_repo


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the initial governed change packet adversarial benchmark.")
    parser.add_argument(
        "--workspace-root",
        default=str(DEFAULT_GOVERNED_CHANGE_PACKET_BENCHMARK_WORKSPACE_ROOT),
        help="Benchmark fixture workspace root. Keep distinct from the primary packet workspace.",
    )
    parser.add_argument("--output", default=str(DEFAULT_GOVERNED_CHANGE_PACKET_BENCHMARK_OUTPUT), help="Stable staging benchmark output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted benchmark JSON.")
    return parser.parse_args(argv)


def build_governed_change_packet_adversarial_benchmark(*, workspace_root: Path) -> dict[str, Any]:
    outputs_root = workspace_root.resolve().parent / "governed_change_packet_benchmark_outputs"
    base = run_governed_repo_change_packet_flow(
        workspace_root=workspace_root,
        live_output=outputs_root / "trusted_repo_change_live_run.json",
        second_live_output=outputs_root / "trusted_repo_change_live_run_02.json",
        campaign_output=outputs_root / "trusted_repo_change_witness_verification.json",
        offline_output=outputs_root / "trusted_repo_change_offline_verifier.json",
        denial_output=outputs_root / "trusted_repo_change_denial.json",
        validator_failure_output=outputs_root / "trusted_repo_change_validator_failure.json",
        packet_output=outputs_root / "governed_repo_change_packet.json",
        kernel_model_output=outputs_root / "governed_change_packet_trusted_kernel_model.json",
        verify_output=None,
    )
    packet = copy.deepcopy(base["packet"])
    scenarios = [
        ("wrong_target_with_superficially_valid_approval", _mutate_wrong_target, "invalid"),
        ("success_shaped_packet_missing_validator", _mutate_missing_validator_role, "insufficient_evidence"),
        ("success_shaped_packet_missing_effect_evidence", _mutate_missing_witness_bundle_role, "insufficient_evidence"),
        ("contradictory_final_truth_summary", _mutate_contradictory_workflow_result, "invalid"),
        ("packet_overclaim_beyond_available_evidence", _mutate_overclaim, "insufficient_evidence"),
        ("projection_only_material_presented_as_authority", _mutate_operator_summary_authority, "invalid"),
    ]
    cases: list[dict[str, Any]] = []
    for case_id, mutate, expected_verdict in scenarios:
        candidate = copy.deepcopy(packet)
        mutate(candidate)
        report = verify_governed_change_packet_payload(candidate)
        baseline_signals = _baseline_signals(candidate)
        cases.append(
            {
                "case_id": case_id,
                "expected_packet_verdict": expected_verdict,
                "observed_packet_verdict": report.get("packet_verdict"),
                "expectation_met": report.get("packet_verdict") == expected_verdict,
                "baseline_success_shaped_or_ambiguous": baseline_signals["success_shaped_or_ambiguous"],
                "baseline_visible_artifacts": baseline_signals["visible_artifacts"],
                "missing_evidence": list(report.get("missing_evidence") or []),
                "contradictions": list(report.get("contradictions") or []),
            }
        )
    observed_result = "success" if all(case["expectation_met"] for case in cases) else "failure"
    return {
        "schema_version": "governed_change_packet_adversarial_benchmark.v1",
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "mixed",
        "observed_path": "primary",
        "observed_result": observed_result,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "baseline_comparator": "workflow + logs + approvals",
        "baseline_packet_ref": base.get("packet_ref"),
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "caught_count": sum(1 for case in cases if case["expectation_met"]),
            "baseline_success_shaped_case_count": sum(1 for case in cases if case["baseline_success_shaped_or_ambiguous"]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_path = Path(str(args.output)).resolve()
    benchmark = build_governed_change_packet_adversarial_benchmark(workspace_root=Path(str(args.workspace_root)))
    persisted = write_payload_with_diff_ledger(output_path, benchmark)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"case_count={persisted.get('summary', {}).get('case_count')}",
                    f"output={relative_to_repo(output_path)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


def _baseline_signals(packet: dict[str, Any]) -> dict[str, Any]:
    roles = {item["role"]: item for item in packet.get("artifact_manifest") or [] if isinstance(item, dict)}
    visible = [role for role in ("approved_live_proof", "flow_request", "run_authority") if roles.get(role, {}).get("exists") is True]
    return {
        "success_shaped_or_ambiguous": len(visible) == 3,
        "visible_artifacts": visible,
    }


def _mutate_wrong_target(packet: dict[str, Any]) -> None:
    packet["primary_operator_summary"]["target_artifact_path"] = "repo/config/wrong-target.json"


def _mutate_missing_validator_role(packet: dict[str, Any]) -> None:
    packet["artifact_manifest"] = [item for item in packet["artifact_manifest"] if item.get("role") != "validator_report"]


def _mutate_missing_witness_bundle_role(packet: dict[str, Any]) -> None:
    packet["artifact_manifest"] = [item for item in packet["artifact_manifest"] if item.get("role") != "witness_bundle"]


def _mutate_contradictory_workflow_result(packet: dict[str, Any]) -> None:
    packet["primary_operator_summary"]["workflow_result"] = "blocked"


def _mutate_overclaim(packet: dict[str, Any]) -> None:
    packet["claim_summary"]["requested_claim_tier"] = "replay_deterministic"


def _mutate_operator_summary_authority(packet: dict[str, Any]) -> None:
    for item in packet["artifact_manifest"]:
        if item.get("role") == "operator_summary":
            item["classification"] = "primary_authority"
            break


if __name__ == "__main__":
    raise SystemExit(main())
