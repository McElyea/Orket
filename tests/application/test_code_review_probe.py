# Layer: unit
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


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

    payload = module.build_deterministic_payload(source_text=source_text, answer_key=answer_key)

    hit_ids = {row["issue_id"] for row in payload["findings"]}

    assert payload["deterministic_lane_version"] == "s04_static_fingerprint_v1"
    assert "RAW_PAYLOAD_EVAL" in hit_ids
    assert "DEBUG_PAYLOAD_LEAK" in hit_ids
    assert "VERIFY_SIGNATURE_ALWAYS_TRUE" in hit_ids


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
                "policy_digest": "sha256:test",
                "findings": [],
                "executed_checks": [],
                "deterministic_lane_version": "not_applicable",
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "model_assisted_critique.json").write_text(
        json.dumps(
            {
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
