# Layer: unit
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("code_review_probe_test", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_validated_review_payload_handles_fenced_payload() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_support.py"))
    payload, response_json_found, contract_valid, advisory_errors = module.validated_review_payload(
        "```json\n"
        '{"summary":["one"],"high_risk_issues":[],"missing_tests":[],"questions_for_author":[],"nits":[],"refs":[]}\n'
        "```"
    )

    assert payload["summary"] == ["one"]
    assert response_json_found is True
    assert contract_valid is True
    assert advisory_errors == []


def test_build_deterministic_payload_tracks_fixture_findings() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_support.py"))
    answer_key = module.load_json_object(
        Path("scripts/workloads/fixtures/code_review_probe_v1/human_review_answer_key.json")
    )
    source_text = module.load_text(Path("scripts/workloads/fixtures/code_review_probe_v1/corrupt_order_processor.py"))

    payload = module.build_deterministic_payload(source_text=source_text, answer_key=answer_key, run_id="probe-run")

    hit_ids = {row["issue_id"] for row in payload["findings"]}

    assert payload["run_id"] == "probe-run"
    assert payload["deterministic_lane_version"] == "s04_static_fingerprint_v1"
    assert payload["execution_state_authority"] == "control_plane_records"
    assert payload["lane_output_execution_state_authoritative"] is False
    assert "RAW_PAYLOAD_EVAL" in hit_ids
    assert "DEBUG_PAYLOAD_LEAK" in hit_ids
    assert "VERIFY_SIGNATURE_ALWAYS_TRUE" in hit_ids


def test_build_run_manifest_payload_marks_outputs_non_authoritative() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_support.py"))

    payload = module.build_run_manifest_payload(
        run_id="probe-run",
        snapshot_digest="sha256:test",
        policy_digest="sha256:policy",
        deterministic_lane_version="s04_static_fingerprint_v1",
        prompt_profile="baseline_v2",
        review_method="single_pass",
    )

    assert payload["bundle_kind"] == "code_review_probe"
    assert payload["execution_state_authority"] == "control_plane_records"
    assert payload["lane_outputs_execution_state_authoritative"] is False


# Layer: contract
def test_build_run_manifest_payload_requires_run_id() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_support.py"))

    with pytest.raises(ValueError, match="code_review_probe_run_manifest_run_id_required"):
        module.build_run_manifest_payload(
            run_id="   ",
            snapshot_digest="sha256:test",
            policy_digest="sha256:policy",
            deterministic_lane_version="s04_static_fingerprint_v1",
            prompt_profile="baseline_v2",
            review_method="single_pass",
        )


def test_build_model_assisted_payload_marks_outputs_non_authoritative() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_reporting.py"))

    payload = module.build_model_assisted_payload(
        review_payload={
            "summary": ["summary"],
            "high_risk_issues": [],
            "missing_tests": [],
            "questions_for_author": [],
            "nits": [],
            "refs": [],
        },
        run_id="probe-run",
        model="local-model",
        source_text="print('hello')",
        prompt_profile="baseline_v2",
        review_method="single_pass",
        policy_digest="sha256:policy",
    )

    assert payload["execution_state_authority"] == "control_plane_records"
    assert payload["lane_output_execution_state_authoritative"] is False
    assert payload["run_id"] == "probe-run"


# Layer: contract
def test_build_model_assisted_payload_requires_run_id() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_reporting.py"))

    with pytest.raises(ValueError, match="code_review_probe_model_assisted_run_id_required"):
        module.build_model_assisted_payload(
            review_payload={
                "summary": ["summary"],
                "high_risk_issues": [],
                "missing_tests": [],
                "questions_for_author": [],
                "nits": [],
                "refs": [],
            },
            run_id="",
            model="local-model",
            source_text="print('hello')",
            prompt_profile="baseline_v2",
            review_method="single_pass",
            policy_digest="sha256:policy",
        )


def test_build_guard_messages_includes_coverage_checklist() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_support.py"))

    messages = module.build_guard_messages(
        fixture_path=Path("fixture.py"),
        source_text="print('debug')",
        draft_response_text='{"summary":[],"high_risk_issues":[],"missing_tests":[],"questions_for_author":[],"nits":[],"refs":[]}',
        prompt_profile="verification_focus_v1",
    )

    assert "payload logging or accidental disclosure" in messages[1]["content"]
    assert "Return exactly one JSON object" in messages[0]["content"]


def test_build_governed_claim_payload_tracks_locked_scope() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_support.py"))

    payload = module.build_governed_claim_payload(
        provider="ollama",
        model="qwen2.5-coder:14b",
        prompt_profile="baseline_v2",
        review_method="single_pass",
        temperature=0.0,
        seed=0,
        timeout=180,
        fixture_path=Path("scripts/workloads/fixtures/code_review_probe_v1/corrupt_order_processor.py"),
        answer_key_path=Path("scripts/workloads/fixtures/code_review_probe_v1/human_review_answer_key.json"),
    )

    assert payload["claim_tier"] == "non_deterministic_lab_only"
    assert payload["compare_scope"] == "workload_s04_fixture_v1"
    assert payload["operator_surface"] == "workload_answer_key_scoring_verdict_v1"
    assert payload["authoritative_truth_surface"] == "deterministic_fingerprint_plus_answer_key_scoring_v1"
    assert payload["model_assistance_surface"] == "model_assisted_review_critique_v0"
    assert payload["policy_digest"].startswith("sha256:")
    assert payload["control_bundle_hash"].startswith("sha256:")


# Layer: contract
def test_build_deterministic_payload_requires_run_id() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_support.py"))
    answer_key = module.load_json_object(
        Path("scripts/workloads/fixtures/code_review_probe_v1/human_review_answer_key.json")
    )
    source_text = module.load_text(Path("scripts/workloads/fixtures/code_review_probe_v1/corrupt_order_processor.py"))

    with pytest.raises(ValueError, match="code_review_probe_deterministic_run_id_required"):
        module.build_deterministic_payload(source_text=source_text, answer_key=answer_key, run_id="")


def test_usage_responses_dedupes_single_pass() -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe.py"))
    response = object()

    single_pass = module._usage_responses(
        initial_response=response,
        final_response=response,
        review_method="single_pass",
    )
    self_check = module._usage_responses(
        initial_response=response,
        final_response=object(),
        review_method="self_check",
    )

    assert len(single_pass) == 1
    assert len(self_check) == 2


def test_score_review_bundle_tracks_model_must_catch_hits(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe.py"))
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    (artifact_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:test",
                "changed_files": [
                    {"path": "scripts/workloads/fixtures/code_review_probe_v1/corrupt_order_processor.py"}
                ],
                "diff_unified": "payload = eval(raw_payload, {}, {})\nreturn bool(signature)\n",
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "deterministic_decision.json").write_text(
        json.dumps(
            {
                "run_id": "probe-run",
                "policy_digest": "sha256:test",
                "findings": [],
                "executed_checks": [],
                "deterministic_lane_version": "not_applicable",
                "execution_state_authority": "control_plane_records",
                "lane_output_execution_state_authoritative": False,
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "model_assisted_critique.json").write_text(
        json.dumps(
            {
                "run_id": "probe-run",
                "summary": ["This file has a fake signature check."],
                "high_risk_issues": [
                    {
                        "why": "Untrusted input goes through eval and any non-empty signature passes.",
                        "where": "load_order(eval(raw_payload, {}, {})); verify_signature(return bool(signature))",
                        "impact": "Remote code execution and bypassed integrity checks.",
                        "confidence": 0.98,
                        "suggested_fix": "Use json.loads and a real signature comparison.",
                    }
                ],
                "missing_tests": ["Add a test proving invalid signatures fail closed."],
                "questions_for_author": [],
                "nits": [],
                "refs": [],
                "execution_state_authority": "control_plane_records",
                "lane_output_execution_state_authoritative": False,
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "bundle_kind": "code_review_probe",
                "run_id": "probe-run",
                "snapshot_digest": "sha256:test",
                "policy_digest": "sha256:test",
                "deterministic_lane_version": "not_applicable",
                "model_lane_contract_version": "review_critique_v0",
                "prompt_profile": "baseline_v2",
                "review_method": "single_pass",
                "execution_state_authority": "control_plane_records",
                "lane_outputs_execution_state_authoritative": False,
            }
        ),
        encoding="utf-8",
    )

    answer_key = Path("scripts/workloads/fixtures/code_review_probe_v1/human_review_answer_key.json")
    report = module.score_review_bundle(artifact_dir=artifact_dir, answer_key_path=answer_key)

    assert "RAW_PAYLOAD_EVAL" in report["model_hit_issue_ids"]
    assert "VERIFY_SIGNATURE_ALWAYS_TRUE" in report["model_hit_issue_ids"]
    assert "DEBUG_PAYLOAD_LEAK" in report["model_missed_must_catch"]
    assert report["model_assisted"]["reasoning_score"] >= 2
    assert report["model_assisted"]["fix_score"] >= 1


# Layer: contract
def test_score_review_bundle_rejects_drifted_score_report_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_reporting.py"))

    monkeypatch.setattr(
        module,
        "score_answer_key",
        lambda **_: {
            "contract_version": "drifted",
            "run_id": "probe-run",
            "deterministic": {},
            "model_assisted": {},
            "issues": [],
        },
    )

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_contract_version_invalid"):
        module.score_review_bundle(
            artifact_dir=Path("unused"),
            answer_key_path=Path("unused"),
        )


# Layer: contract
def test_score_review_bundle_rejects_drifted_score_report_issue_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_reporting.py"))

    monkeypatch.setattr(
        module,
        "score_answer_key",
        lambda **_: {
            "contract_version": "reviewrun_answer_key_score_v1",
            "fixture_id": "fixture",
            "run_id": "probe-run",
            "run_dir": "artifact",
            "answer_key": "answer_key.json",
            "snapshot_digest": "sha256:test",
            "policy_digest": "sha256:test",
            "deterministic": {
                "score": 0,
                "max_score": 0,
                "coverage": 0.0,
                "present_issue_count": 0,
                "missed_must_catch": [],
                "unexpected_hits": [],
            },
            "model_assisted": {
                "enabled": False,
                "score": 0,
                "max_score": 0,
                "coverage": 0.0,
                "reasoning_score": 0,
                "reasoning_max_score": 0,
                "fix_score": 0,
                "fix_max_score": 0,
                "reasoning_weight": 2,
                "fix_weight": 1,
            },
            "issues": [
                {
                    "issue_id": "ISSUE-1",
                    "severity": "high",
                    "must_catch": True,
                    "present": True,
                    "deterministic_hit": True,
                    "model_hit": True,
                    "reasoning_hits": 1,
                    "fix_hits": 1,
                    "weight": "5",
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_issue_weight_invalid"):
        module.score_review_bundle(
            artifact_dir=Path("unused"),
            answer_key_path=Path("unused"),
        )


# Layer: contract
def test_score_review_bundle_rejects_drifted_score_report_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_reporting.py"))

    monkeypatch.setattr(
        module,
        "score_answer_key",
        lambda **_: {
            "contract_version": "reviewrun_answer_key_score_v1",
            "fixture_id": "fixture",
            "run_id": "probe-run",
            "run_dir": "artifact",
            "answer_key": "answer_key.json",
            "snapshot_digest": "sha256:test",
            "policy_digest": "sha256:test",
            "deterministic": {
                "score": 5,
                "max_score": 0,
                "coverage": 0.0,
                "present_issue_count": 0,
                "missed_must_catch": [],
                "unexpected_hits": [],
            },
            "model_assisted": {
                "enabled": False,
                "score": 0,
                "max_score": 0,
                "coverage": 0.0,
                "reasoning_score": 0,
                "reasoning_max_score": 0,
                "fix_score": 0,
                "fix_max_score": 0,
                "reasoning_weight": 2,
                "fix_weight": 1,
            },
            "issues": [],
        },
    )

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_deterministic_score_mismatch"):
        module.score_review_bundle(
            artifact_dir=Path("unused"),
            answer_key_path=Path("unused"),
        )


# Layer: contract
def test_score_review_bundle_rejects_drifted_score_report_model_reasoning_aggregates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_reporting.py"))

    monkeypatch.setattr(
        module,
        "score_answer_key",
        lambda **_: {
            "contract_version": "reviewrun_answer_key_score_v1",
            "fixture_id": "fixture",
            "run_id": "probe-run",
            "run_dir": "artifact",
            "answer_key": "answer_key.json",
            "snapshot_digest": "sha256:test",
            "policy_digest": "sha256:test",
            "deterministic": {
                "score": 0,
                "max_score": 5,
                "coverage": 0.0,
                "present_issue_count": 1,
                "missed_must_catch": ["ISSUE-1"],
                "unexpected_hits": [],
            },
            "model_assisted": {
                "enabled": True,
                "score": 0,
                "max_score": 5,
                "coverage": 0.0,
                "reasoning_score": 2,
                "reasoning_max_score": 2,
                "fix_score": 0,
                "fix_max_score": 1,
                "reasoning_weight": 2,
                "fix_weight": 1,
            },
            "issues": [
                {
                    "issue_id": "ISSUE-1",
                    "severity": "high",
                    "must_catch": True,
                    "present": True,
                    "deterministic_hit": False,
                    "model_hit": False,
                    "reasoning_hits": 0,
                    "fix_hits": 0,
                    "weight": 5,
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_model_assisted_reasoning_score_mismatch"):
        module.score_review_bundle(
            artifact_dir=Path("unused"),
            answer_key_path=Path("unused"),
        )


# Layer: contract
def test_score_review_bundle_rejects_drifted_score_report_snapshot_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe_reporting.py"))

    monkeypatch.setattr(
        module,
        "score_answer_key",
        lambda **_: {
            "contract_version": "reviewrun_answer_key_score_v1",
            "fixture_id": "fixture",
            "run_id": "probe-run",
            "run_dir": "artifact",
            "answer_key": "answer_key.json",
            "snapshot_digest": "",
            "policy_digest": "sha256:test",
            "deterministic": {
                "score": 0,
                "max_score": 0,
                "coverage": 0.0,
                "present_issue_count": 0,
                "missed_must_catch": [],
                "unexpected_hits": [],
            },
            "model_assisted": {
                "enabled": False,
                "score": 0,
                "max_score": 0,
                "coverage": 0.0,
                "reasoning_score": 0,
                "reasoning_max_score": 0,
                "fix_score": 0,
                "fix_max_score": 0,
                "reasoning_weight": 2,
                "fix_weight": 1,
            },
            "issues": [],
        },
    )

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_snapshot_digest_invalid"):
        module.score_review_bundle(
            artifact_dir=Path("unused"),
            answer_key_path=Path("unused"),
        )


def test_score_review_bundle_rejects_drifted_bundle_run_id(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/workloads/code_review_probe.py"))
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    (artifact_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:test",
                "changed_files": [
                    {"path": "scripts/workloads/fixtures/code_review_probe_v1/corrupt_order_processor.py"}
                ],
                "diff_unified": "payload = eval(raw_payload, {}, {})\nreturn bool(signature)\n",
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "deterministic_decision.json").write_text(
        json.dumps(
            {
                "run_id": "other-run",
                "policy_digest": "sha256:test",
                "findings": [],
                "executed_checks": [],
                "deterministic_lane_version": "not_applicable",
                "execution_state_authority": "control_plane_records",
                "lane_output_execution_state_authoritative": False,
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "model_assisted_critique.json").write_text(
        json.dumps(
            {
                "run_id": "probe-run",
                "summary": ["This file has a fake signature check."],
                "high_risk_issues": [],
                "missing_tests": [],
                "questions_for_author": [],
                "nits": [],
                "refs": [],
                "execution_state_authority": "control_plane_records",
                "lane_output_execution_state_authoritative": False,
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "bundle_kind": "code_review_probe",
                "run_id": "probe-run",
                "snapshot_digest": "sha256:test",
                "policy_digest": "sha256:test",
                "deterministic_lane_version": "not_applicable",
                "model_lane_contract_version": "review_critique_v0",
                "prompt_profile": "baseline_v2",
                "review_method": "single_pass",
                "execution_state_authority": "control_plane_records",
                "lane_outputs_execution_state_authoritative": False,
            }
        ),
        encoding="utf-8",
    )

    answer_key = Path("scripts/workloads/fixtures/code_review_probe_v1/human_review_answer_key.json")
    with pytest.raises(ValueError, match="deterministic_review_decision_run_id_mismatch"):
        module.score_review_bundle(artifact_dir=artifact_dir, answer_key_path=answer_key)
