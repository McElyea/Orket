#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.terraform_plan_review_live_support import live_config_from_env, missing_required_env
from scripts.proof.trusted_terraform_plan_decision_contract import (
    PROOF_RESULTS_ROOT,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
    now_utc_iso,
    relative_to_repo,
)

GATE_SCHEMA_VERSION = "trusted_terraform_plan_decision_publication_gate.v1"
DEFAULT_GATE_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_publication_gate.json"


@dataclass(frozen=True, slots=True)
class GatePaths:
    proof_foundation: Path
    campaign: Path
    offline: Path
    runtime: Path
    readiness: Path
    gate: Path


@dataclass(frozen=True, slots=True)
class GateStep:
    step_id: str
    command: list[str]
    output_path: Path
    env_overrides: dict[str, str] | None = None


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Terraform governed-proof publication gate sequence.")
    parser.add_argument("--results-root", default=str(PROOF_RESULTS_ROOT), help="Root for stable proof outputs.")
    parser.add_argument("--output", default="", help="Stable aggregate gate output path.")
    parser.add_argument(
        "--force-local-evidence",
        action="store_true",
        help="Regenerate local proof evidence even when live provider preflight is blocked.",
    )
    parser.add_argument("--json", action="store_true", help="Print the persisted aggregate gate JSON.")
    return parser.parse_args(argv)


def run_publication_gate(*, results_root: Path, output: Path | None = None, force_local_evidence: bool = False) -> dict[str, Any]:
    paths = _gate_paths(results_root=results_root, output=output)
    live_env_preflight = _live_environment_preflight()
    if live_env_preflight["status"] != "pass" and not force_local_evidence:
        return _preflight_blocked_report(paths=paths, live_env_preflight=live_env_preflight)
    steps = _gate_steps(paths)
    step_reports = [_execute_step(step) for step in steps]
    readiness_payload = _load_json(paths.readiness)
    publication_decision = str(readiness_payload.get("publication_decision") or "blocked")
    observed_result = str(readiness_payload.get("observed_result") or "failure")
    blocking_reasons = list(readiness_payload.get("blocking_reasons") or [])
    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "mixed",
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "observed_path": "primary" if publication_decision == "ready_for_publication_boundary_update" else "blocked",
        "observed_result": observed_result,
        "publication_decision": publication_decision,
        "public_trust_slice_action": str(readiness_payload.get("public_trust_slice_action") or "do_not_widen_public_trust_slice"),
        "truth_boundary_checks": _truth_boundary_checks(paths),
        "execution_mode": "forced_local_evidence" if force_local_evidence and live_env_preflight["status"] != "pass" else "full_gate_sequence",
        "readiness_schema_version": str(readiness_payload.get("schema_version") or ""),
        "readiness_output_ref": relative_to_repo(paths.readiness),
        "gate_output_ref": relative_to_repo(paths.gate),
        "live_environment_preflight": live_env_preflight,
        "blocking_reasons": blocking_reasons,
        "steps": step_reports,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    results_root = Path(str(args.results_root)).resolve()
    output = Path(str(args.output)).resolve() if str(args.output).strip() else None
    report = run_publication_gate(results_root=results_root, output=output, force_local_evidence=bool(args.force_local_evidence))
    output_path = output or _gate_paths(results_root=results_root, output=None).gate
    persisted = write_payload_with_diff_ledger(output_path, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"publication_decision={persisted.get('publication_decision')}",
                    f"output={relative_to_repo(output_path)}",
                ]
            )
        )
    return 0 if persisted.get("publication_decision") == "ready_for_publication_boundary_update" else 1


def _gate_paths(*, results_root: Path, output: Path | None) -> GatePaths:
    return GatePaths(
        proof_foundation=results_root / "trusted_run_proof_foundation.json",
        campaign=results_root / "trusted_terraform_plan_decision_witness_verification.json",
        offline=results_root / "trusted_terraform_plan_decision_offline_verifier.json",
        runtime=results_root / "trusted_terraform_plan_decision_live_runtime.json",
        readiness=results_root / "trusted_terraform_plan_decision_publication_readiness.json",
        gate=output or (results_root / "trusted_terraform_plan_decision_publication_gate.json"),
    )


def _gate_steps(paths: GatePaths) -> list[GateStep]:
    return [
        GateStep(
            "proof_foundation",
            [sys.executable, "scripts/proof/verify_trusted_run_proof_foundation.py", "--output", str(paths.proof_foundation)],
            paths.proof_foundation,
        ),
        GateStep(
            "terraform_campaign",
            [sys.executable, "scripts/proof/run_trusted_terraform_plan_decision_campaign.py", "--output", str(paths.campaign)],
            paths.campaign,
            {"ORKET_DISABLE_SANDBOX": "1"},
        ),
        GateStep(
            "terraform_offline_claim",
            [
                sys.executable,
                "scripts/proof/verify_offline_trusted_run_claim.py",
                "--input",
                str(paths.campaign),
                "--claim",
                "verdict_deterministic",
                "--output",
                str(paths.offline),
            ],
            paths.offline,
        ),
        GateStep(
            "provider_backed_governed_runtime",
            [
                sys.executable,
                "scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py",
                "--output",
                str(paths.runtime),
            ],
            paths.runtime,
        ),
        GateStep(
            "terraform_publication_readiness",
            [
                sys.executable,
                "scripts/proof/check_trusted_terraform_publication_readiness.py",
                "--foundation-input",
                str(paths.proof_foundation),
                "--campaign-input",
                str(paths.campaign),
                "--offline-input",
                str(paths.offline),
                "--runtime-input",
                str(paths.runtime),
                "--output",
                str(paths.readiness),
            ],
            paths.readiness,
        ),
    ]


def _preflight_blocked_report(*, paths: GatePaths, live_env_preflight: dict[str, Any]) -> dict[str, Any]:
    readiness_payload = _load_json(paths.readiness)
    missing = [str(item) for item in live_env_preflight.get("missing_env") or []]
    blocking_reasons = [f"live_environment_preflight_missing:{','.join(missing)}"] if missing else ["live_environment_preflight_blocked"]
    readiness_blocking_reasons = [str(item) for item in readiness_payload.get("blocking_reasons") or []]
    for reason in readiness_blocking_reasons:
        if reason not in blocking_reasons:
            blocking_reasons.append(reason)
    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "mixed",
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "observed_path": "blocked",
        "observed_result": "environment blocker",
        "publication_decision": "blocked",
        "public_trust_slice_action": "do_not_widen_public_trust_slice",
        "truth_boundary_checks": _truth_boundary_checks(paths),
        "execution_mode": "preflight_blocked",
        "readiness_schema_version": str(readiness_payload.get("schema_version") or ""),
        "readiness_observed_result": str(readiness_payload.get("observed_result") or ""),
        "readiness_publication_decision": str(readiness_payload.get("publication_decision") or ""),
        "readiness_blocking_reasons": readiness_blocking_reasons,
        "readiness_output_ref": relative_to_repo(paths.readiness),
        "gate_output_ref": relative_to_repo(paths.gate),
        "live_environment_preflight": live_env_preflight,
        "blocking_reasons": blocking_reasons,
        "steps": [],
        "skipped_steps": [step.step_id for step in _gate_steps(paths)],
    }


def _live_environment_preflight() -> dict[str, Any]:
    required_env = [
        "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI",
        "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID",
        "AWS_REGION or AWS_DEFAULT_REGION",
    ]
    missing = missing_required_env(live_config_from_env())
    return {
        "status": "pass" if not missing else "blocked",
        "required_env": required_env,
        "missing_env": missing,
        "aws_credentials_source": "standard AWS provider chain; not inspected or recorded",
    }


def _truth_boundary_checks(paths: GatePaths) -> list[dict[str, Any]]:
    setup_dir = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
    runtime_payload = _load_json(paths.runtime)
    runtime_success = runtime_payload.get("observed_result") == "success"
    return [
        {
            "id": "setup_packet_alone_not_admission_evidence",
            "status": "pass",
            "input_present": (setup_dir / "trusted_terraform_plan_decision_live_setup_packet.json").exists(),
            "admission_evidence": False,
        },
        {
            "id": "fixture_generation_alone_not_admission_evidence",
            "status": "pass",
            "input_present": (setup_dir / "terraform-plan-fixture-metadata.json").exists(),
            "admission_evidence": False,
        },
        {
            "id": "aws_setup_success_alone_not_admission_evidence",
            "status": "pass",
            "input_present": (setup_dir / "aws-setup-result.json").exists(),
            "admission_evidence": False,
        },
        {
            "id": "runtime_smoke_success_is_live_smoke_only",
            "status": "pass" if runtime_success else "blocked",
            "input_present": paths.runtime.exists(),
            "admission_evidence": False,
            "northstar_admission_state": "paused_until_same_change_proof_envelope_rerun",
        },
    ]


def _execute_step(step: GateStep) -> dict[str, Any]:
    completed = _run_subprocess(step.command, env_overrides=step.env_overrides)
    payload = _load_json(step.output_path)
    return {
        "id": step.step_id,
        "command": _display_command(step.command),
        "output_ref": relative_to_repo(step.output_path),
        "exit_code": completed.returncode,
        "stdout": _safe_output(completed.stdout),
        "observed_result": str(payload.get("observed_result") or ""),
        "claim_status": str(payload.get("claim_status") or ""),
        "claim_tier": str(payload.get("claim_tier") or ""),
        "publication_decision": str(payload.get("publication_decision") or ""),
        "blocking_reasons": list(payload.get("blocking_reasons") or []),
    }


def _run_subprocess(command: list[str], *, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_overrides or {})
    return subprocess.run(command, cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"observed_result": "failure", "blocking_reasons": [f"missing_output:{relative_to_repo(path)}"]}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"observed_result": "failure", "blocking_reasons": [f"invalid_json:{relative_to_repo(path)}:{exc.msg}"]}
    if not isinstance(payload, dict):
        return {"observed_result": "failure", "blocking_reasons": [f"json_object_required:{relative_to_repo(path)}"]}
    payload.pop("diff_ledger", None)
    return payload


def _display_command(command: list[str]) -> str:
    display = ["python" if index == 0 else value for index, value in enumerate(command)]
    return " ".join(display)


def _safe_output(value: str) -> str:
    return " ".join(value.strip().split())[:500]


if __name__ == "__main__":
    raise SystemExit(main())
