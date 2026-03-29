from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("reviewrun_answer_key_scoring_test", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _write_review_authority_artifacts(
    run_dir: Path,
    *,
    deterministic: dict,
    model_assisted: dict | None = None,
    manifest_overrides: dict | None = None,
) -> None:
    manifest_payload = {
        "run_id": "run-1",
        "execution_state_authority": "control_plane_records",
        "lane_outputs_execution_state_authoritative": False,
        "control_plane_run_id": "run-1",
        "control_plane_attempt_id": "run-1:attempt:0001",
        "control_plane_step_id": "run-1:step:start",
    }
    manifest_payload.update(dict(manifest_overrides or {}))
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest_payload), encoding="utf-8")

    deterministic_payload = {
        "run_id": "run-1",
        "execution_state_authority": "control_plane_records",
        "lane_output_execution_state_authoritative": False,
        "control_plane_run_id": "run-1",
        "control_plane_attempt_id": "run-1:attempt:0001",
        "control_plane_step_id": "run-1:step:start",
        **dict(deterministic),
    }
    (run_dir / "deterministic_decision.json").write_text(json.dumps(deterministic_payload), encoding="utf-8")

    if model_assisted is not None:
        critique_payload = {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
            **dict(model_assisted),
        }
        (run_dir / "model_assisted_critique.json").write_text(json.dumps(critique_payload), encoding="utf-8")


def _minimal_answer_key_score_report() -> dict:
    return {
        "contract_version": "reviewrun_answer_key_score_v1",
        "fixture_id": "fixture",
        "run_id": "run-1",
        "run_dir": "artifact",
        "answer_key": "answer_key.json",
        "snapshot_digest": "sha256:abc",
        "policy_digest": "sha256:def",
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
    }


def test_score_answer_key_hits_issue_by_fingerprint(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [{"path": "app/config.py"}],
                "diff_unified": "+++ b/app/config.py\n+debug: bool = True\n",
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={
            "policy_digest": "sha256:def",
            "findings": [
                {
                    "message": "Forbidden pattern matched: debug: bool = True",
                    "details": {"pattern": "debug: bool = True"},
                }
            ],
        },
    )
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(
        json.dumps(
            {
                "fixture_id": "fixture",
                "scoring": {"must_catch_weight": 5, "nice_catch_weight": 2, "reasoning_weight": 2, "fix_weight": 1},
                "issues": [
                    {
                        "issue_id": "CFG_DEBUG_DEFAULT_TRUE",
                        "must_catch": True,
                        "severity": "high",
                        "files": ["app/config.py"],
                        "fingerprints": ["debug: bool = True"],
                        "expected_reasoning": [],
                        "expected_fix": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)
    assert report["deterministic"]["score"] == 5
    assert report["deterministic"]["max_score"] == 5
    assert report["deterministic"]["missed_must_catch"] == []


# Layer: contract
def test_score_answer_key_emits_contract_framing_and_run_id(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [{"path": "app/config.py"}],
                "diff_unified": "+++ b/app/config.py\n+debug: bool = True\n",
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={
            "policy_digest": "sha256:def",
            "findings": [],
        },
    )
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(
        json.dumps(
            {
                "fixture_id": "fixture",
                "scoring": {"must_catch_weight": 5, "nice_catch_weight": 2, "reasoning_weight": 2, "fix_weight": 1},
                "issues": [],
            }
        ),
        encoding="utf-8",
    )

    report = module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)

    assert report["contract_version"] == module.REPORT_CONTRACT_VERSION
    assert report["run_id"] == "run-1"


# Layer: contract
def test_answer_key_score_contract_rejects_nested_score_drift() -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key_contract.py"))
    payload = _minimal_answer_key_score_report()
    payload["deterministic"]["present_issue_count"] = "1"

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_deterministic_present_issue_count_invalid"):
        module.validate_answer_key_score_report(payload)


# Layer: contract
def test_answer_key_score_contract_rejects_deterministic_aggregate_drift() -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key_contract.py"))
    payload = _minimal_answer_key_score_report()
    payload["deterministic"]["score"] = 1

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_deterministic_score_mismatch"):
        module.validate_answer_key_score_report(payload)


# Layer: contract
def test_answer_key_score_contract_rejects_disabled_model_activity_drift() -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key_contract.py"))
    payload = _minimal_answer_key_score_report()
    payload["deterministic"]["present_issue_count"] = 1
    payload["deterministic"]["max_score"] = 5
    payload["deterministic"]["coverage"] = 0.0
    payload["deterministic"]["missed_must_catch"] = ["ISSUE-1"]
    payload["issues"] = [
        {
            "issue_id": "ISSUE-1",
            "severity": "high",
            "must_catch": True,
            "present": True,
            "deterministic_hit": False,
            "model_hit": True,
            "reasoning_hits": 1,
            "fix_hits": 0,
            "weight": 5,
        }
    ]

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_model_assisted_disabled_issue_activity_invalid"):
        module.validate_answer_key_score_report(payload)


# Layer: contract
def test_answer_key_score_contract_rejects_model_reasoning_aggregate_drift() -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key_contract.py"))
    payload = _minimal_answer_key_score_report()
    payload["deterministic"]["present_issue_count"] = 1
    payload["deterministic"]["max_score"] = 5
    payload["deterministic"]["coverage"] = 0.0
    payload["deterministic"]["missed_must_catch"] = ["ISSUE-1"]
    payload["model_assisted"]["enabled"] = True
    payload["model_assisted"]["max_score"] = 5
    payload["model_assisted"]["coverage"] = 0.0
    payload["model_assisted"]["reasoning_score"] = 2
    payload["model_assisted"]["reasoning_max_score"] = 2
    payload["model_assisted"]["fix_max_score"] = 1
    payload["issues"] = [
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
    ]

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_model_assisted_reasoning_score_mismatch"):
        module.validate_answer_key_score_report(payload)


# Layer: contract
def test_answer_key_score_contract_rejects_missing_fixture_provenance() -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key_contract.py"))
    payload = _minimal_answer_key_score_report()
    payload["fixture_id"] = ""

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_fixture_id_required"):
        module.validate_answer_key_score_report(payload)


def test_score_answer_key_uses_tag_hit_when_present(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [{"path": "app/api.py"}],
                "diff_unified": "+++ b/app/api.py\n+print('x')\n",
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={
            "policy_digest": "sha256:def",
            "findings": [{"message": "something", "details": {"tags": ["API_DEBUG_PRINTS_PAYLOAD"]}}],
        },
    )
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(
        json.dumps(
            {
                "fixture_id": "fixture",
                "scoring": {"must_catch_weight": 5, "nice_catch_weight": 2, "reasoning_weight": 2, "fix_weight": 1},
                "issues": [
                    {
                        "issue_id": "API_DEBUG_PRINTS_PAYLOAD",
                        "must_catch": True,
                        "severity": "high",
                        "files": ["app/api.py"],
                        "fingerprints": ["nope-never-matches"],
                        "expected_reasoning": [],
                        "expected_fix": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)
    assert report["deterministic"]["score"] == 5
    assert report["issues"][0]["deterministic_hit"] is True


def test_score_answer_key_structured_model_scoring_awards_reasoning_and_fix(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [
                    {"path": "scripts/workloads/fixtures/code_review_probe_v1/corrupt_order_processor.py"}
                ],
                "diff_unified": (
                    "payload = eval(raw_payload, {}, {})\n"
                    "return bool(signature)\n"
                    "print(\"DEBUG payload=\", raw_payload)\n"
                ),
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={"policy_digest": "sha256:def", "findings": [], "executed_checks": []},
        model_assisted={
            "summary": [
                "Insecure deserialization using eval",
                "Potential signature verification bypass",
            ],
            "high_risk_issues": [
                {
                    "why": "The load_order function uses eval to parse raw_payload, creating arbitrary code execution risk.",
                    "where": "load_order function",
                    "impact": "Attackers can execute code instead of safely decoding the request body.",
                    "confidence": 1.0,
                    "suggested_fix": "Replace eval with json.loads and validate the payload shape before use.",
                },
                {
                    "why": "The verify_signature function does not actually verify a signature and can be bypassed.",
                    "where": "verify_signature function",
                    "impact": "Integrity checks are ineffective because invalid signatures can still pass.",
                    "confidence": 0.9,
                    "suggested_fix": "Use a real signature comparison and fail closed on mismatch.",
                },
            ],
            "missing_tests": [],
            "questions_for_author": [],
            "nits": [],
            "refs": [],
        },
    )

    answer_key = Path("scripts/workloads/fixtures/code_review_probe_v1/human_review_answer_key.json")
    report = module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)

    issue_rows = {row["issue_id"]: row for row in report["issues"]}

    assert issue_rows["RAW_PAYLOAD_EVAL"]["model_hit"] is True
    assert issue_rows["RAW_PAYLOAD_EVAL"]["reasoning_hits"] >= 1
    assert issue_rows["RAW_PAYLOAD_EVAL"]["fix_hits"] >= 1
    assert issue_rows["VERIFY_SIGNATURE_ALWAYS_TRUE"]["model_hit"] is True
    assert report["model_assisted"]["reasoning_weight"] == 2
    assert report["model_assisted"]["fix_weight"] == 1
    assert report["model_assisted"]["reasoning_score"] >= 2
    assert report["model_assisted"]["fix_score"] >= 1


def test_score_answer_key_rejects_drifted_review_bundle_markers(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [{"path": "app/config.py"}],
                "diff_unified": "+++ b/app/config.py\n+debug: bool = True\n",
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={"policy_digest": "sha256:def", "findings": []},
        manifest_overrides={"lane_outputs_execution_state_authoritative": True},
    )
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(
        json.dumps(
            {
                "fixture_id": "fixture",
                "scoring": {"must_catch_weight": 5, "nice_catch_weight": 2, "reasoning_weight": 2, "fix_weight": 1},
                "issues": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="review_run_manifest_execution_state_authoritative_invalid"):
        module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)


def test_score_answer_key_rejects_missing_answer_key_fixture_id(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [{"path": "app/config.py"}],
                "diff_unified": "+++ b/app/config.py\n+debug: bool = True\n",
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={"policy_digest": "sha256:def", "findings": []},
    )
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(
        json.dumps(
            {
                "scoring": {"must_catch_weight": 5, "nice_catch_weight": 2, "reasoning_weight": 2, "fix_weight": 1},
                "issues": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reviewrun_answer_key_score_fixture_id_required"):
        module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)


def test_score_answer_key_rejects_drifted_review_bundle_identifiers(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [{"path": "app/config.py"}],
                "diff_unified": "+++ b/app/config.py\n+debug: bool = True\n",
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={
            "policy_digest": "sha256:def",
            "findings": [],
            "control_plane_attempt_id": "run-1:attempt:9999",
        },
    )
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(
        json.dumps(
            {
                "fixture_id": "fixture",
                "scoring": {"must_catch_weight": 5, "nice_catch_weight": 2, "reasoning_weight": 2, "fix_weight": 1},
                "issues": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_attempt_id_mismatch"):
        module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)


def test_score_answer_key_rejects_missing_review_bundle_control_plane_ref(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [{"path": "app/config.py"}],
                "diff_unified": "+++ b/app/config.py\n+debug: bool = True\n",
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={
            "policy_digest": "sha256:def",
            "findings": [],
            "control_plane_step_id": "",
        },
    )
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(
        json.dumps(
            {
                "fixture_id": "fixture",
                "scoring": {"must_catch_weight": 5, "nice_catch_weight": 2, "reasoning_weight": 2, "fix_weight": 1},
                "issues": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_step_id_missing"):
        module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)


def test_score_answer_key_rejects_orphaned_review_bundle_control_plane_ref(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/score_answer_key.py"))
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_digest": "sha256:abc",
                "changed_files": [{"path": "app/config.py"}],
                "diff_unified": "+++ b/app/config.py\n+debug: bool = True\n",
            }
        ),
        encoding="utf-8",
    )
    _write_review_authority_artifacts(
        run_dir,
        deterministic={
            "policy_digest": "sha256:def",
            "findings": [],
            "control_plane_run_id": "",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
        manifest_overrides={
            "control_plane_run_id": "",
            "control_plane_attempt_id": "",
            "control_plane_step_id": "",
        },
    )
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(
        json.dumps(
            {
                "fixture_id": "fixture",
                "scoring": {"must_catch_weight": 5, "nice_catch_weight": 2, "reasoning_weight": 2, "fix_weight": 1},
                "issues": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_run_id_missing"):
        module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)
