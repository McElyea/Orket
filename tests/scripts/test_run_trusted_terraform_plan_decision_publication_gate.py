from __future__ import annotations

import json
import subprocess
from pathlib import Path

import scripts.proof.run_trusted_terraform_plan_decision_publication_gate as gate
from scripts.proof.check_trusted_terraform_publication_readiness import main as readiness_main
from scripts.proof.trusted_terraform_plan_decision_contract import TRUSTED_TERRAFORM_COMPARE_SCOPE


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fake_run(*, runtime_observed_result: str):
    def _run(command: list[str], *, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        del env_overrides
        if _has_script(command, "verify_trusted_run_proof_foundation.py"):
            _write_json(
                _output_path(command),
                {
                    "schema_version": "trusted_run_proof_foundation.v1",
                    "observed_result": "success",
                    "foundation_targets": [{"status": "pass"} for _index in range(6)],
                },
            )
            return subprocess.CompletedProcess(command, 0, "foundation ok", "")
        if _has_script(command, "run_trusted_terraform_plan_decision_campaign.py"):
            _write_json(
                _output_path(command),
                {
                    "schema_version": "trusted_run_witness_report.v1",
                    "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
                    "observed_result": "success",
                    "claim_tier": "verdict_deterministic",
                    "run_count": 2,
                },
            )
            return subprocess.CompletedProcess(command, 0, "campaign ok", "")
        if _has_script(command, "verify_offline_trusted_run_claim.py"):
            _write_json(
                _output_path(command),
                {
                    "schema_version": "offline_trusted_run_verifier.v1",
                    "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
                    "observed_result": "success",
                    "claim_status": "allowed",
                    "claim_tier": "verdict_deterministic",
                },
            )
            return subprocess.CompletedProcess(command, 0, "offline ok", "")
        if _has_script(command, "run_trusted_terraform_plan_decision_runtime_smoke.py"):
            _write_json(_output_path(command), _runtime_payload(runtime_observed_result))
            return subprocess.CompletedProcess(command, 0 if runtime_observed_result == "success" else 1, "runtime", "")
        if _has_script(command, "check_trusted_terraform_publication_readiness.py"):
            exit_code = readiness_main(_readiness_args(command))
            return subprocess.CompletedProcess(command, exit_code, "readiness", "")
        raise AssertionError(f"unexpected command:{command}")

    return _run


def test_publication_gate_records_environment_blocker(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies the aggregate gate fails fast when live inputs are absent."""
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", raising=False)
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    _write_json(
        tmp_path / "trusted_terraform_plan_decision_publication_readiness.json",
        {
            "schema_version": "trusted_terraform_plan_decision_publication_readiness.v1",
            "observed_result": "environment blocker",
            "publication_decision": "blocked",
            "blocking_reasons": ["runtime_environment_blocker:missing_required_env:AWS_REGION"],
        },
    )

    def _unexpected_run(command: list[str], *, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        del env_overrides
        raise AssertionError(f"preflight blocked gate should not run:{command}")

    monkeypatch.setattr(gate, "_run_subprocess", _unexpected_run)

    exit_code = gate.main(["--results-root", str(tmp_path)])

    payload = json.loads((tmp_path / "trusted_terraform_plan_decision_publication_gate.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["observed_result"] == "environment blocker"
    assert payload["publication_decision"] == "blocked"
    assert payload["public_trust_slice_action"] == "do_not_widen_public_trust_slice"
    assert payload["execution_mode"] == "preflight_blocked"
    assert payload["readiness_schema_version"] == "trusted_terraform_plan_decision_publication_readiness.v1"
    assert payload["readiness_observed_result"] == "environment blocker"
    assert payload["readiness_publication_decision"] == "blocked"
    assert payload["readiness_blocking_reasons"] == ["runtime_environment_blocker:missing_required_env:AWS_REGION"]
    assert payload["live_environment_preflight"]["status"] == "blocked"
    assert payload["steps"] == []
    assert payload["skipped_steps"] == [
        "proof_foundation",
        "terraform_campaign",
        "terraform_offline_claim",
        "provider_backed_governed_runtime",
        "terraform_publication_readiness",
    ]
    assert any(reason.startswith("live_environment_preflight_missing:") for reason in payload["blocking_reasons"])
    assert "runtime_environment_blocker:missing_required_env:AWS_REGION" in payload["blocking_reasons"]
    assert isinstance(payload.get("diff_ledger"), list)


def test_publication_gate_can_force_local_evidence_when_preflight_is_blocked(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies operators can refresh local evidence while preserving blocked publication truth."""
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", raising=False)
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.setattr(gate, "_run_subprocess", _fake_run(runtime_observed_result="environment blocker"))

    exit_code = gate.main(["--results-root", str(tmp_path), "--force-local-evidence"])

    payload = json.loads((tmp_path / "trusted_terraform_plan_decision_publication_gate.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["execution_mode"] == "forced_local_evidence"
    assert payload["publication_decision"] == "blocked"
    assert any(reason.startswith("runtime_environment_blocker:") for reason in payload["blocking_reasons"])
    assert [step["id"] for step in payload["steps"]] == [
        "proof_foundation",
        "terraform_campaign",
        "terraform_offline_claim",
        "provider_backed_governed_runtime",
        "terraform_publication_readiness",
    ]


def test_publication_gate_allows_only_complete_ready_sequence(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies the aggregate gate allows readiness only when every sequenced proof passes."""
    monkeypatch.setenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", "s3://terraform-review-fixtures/plan.json")
    monkeypatch.setenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", "anthropic.fake")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setattr(gate, "_run_subprocess", _fake_run(runtime_observed_result="success"))

    exit_code = gate.main(["--results-root", str(tmp_path)])

    payload = json.loads((tmp_path / "trusted_terraform_plan_decision_publication_gate.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["observed_result"] == "success"
    assert payload["publication_decision"] == "ready_for_publication_boundary_update"
    assert payload["live_environment_preflight"]["status"] == "pass"
    assert payload["blocking_reasons"] == []
    assert [step["id"] for step in payload["steps"]] == [
        "proof_foundation",
        "terraform_campaign",
        "terraform_offline_claim",
        "provider_backed_governed_runtime",
        "terraform_publication_readiness",
    ]


def _output_path(command: list[str]) -> Path:
    return Path(command[command.index("--output") + 1])


def _readiness_args(command: list[str]) -> list[str]:
    index = next(index for index, value in enumerate(command) if value.endswith("check_trusted_terraform_publication_readiness.py"))
    return command[index + 1 :]


def _has_script(command: list[str], script_name: str) -> bool:
    return any(value.endswith(script_name) for value in command)


def _runtime_payload(observed_result: str) -> dict:
    return {
        "schema_version": "trusted_terraform_plan_decision_live_runtime.v1",
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "observed_result": observed_result,
        "execution_status": "success" if observed_result == "success" else "environment_blocker",
        "reason": "" if observed_result == "success" else "missing_required_env:AWS_REGION",
        "witness_bundle_ref": "workspace/trusted_terraform_plan_decision/runs/session/trusted_run_witness_bundle.json",
        "witness_report": {"observed_result": "success"},
    }
