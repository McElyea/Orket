from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("reviewrun_answer_key_scoring_test", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


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
    (run_dir / "deterministic_decision.json").write_text(
        json.dumps(
            {
                "policy_digest": "sha256:def",
                "findings": [
                    {
                        "message": "Forbidden pattern matched: debug: bool = True",
                        "details": {"pattern": "debug: bool = True"},
                    }
                ],
            }
        ),
        encoding="utf-8",
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
    (run_dir / "deterministic_decision.json").write_text(
        json.dumps(
            {
                "policy_digest": "sha256:def",
                "findings": [{"message": "something", "details": {"tags": ["API_DEBUG_PRINTS_PAYLOAD"]}}],
            }
        ),
        encoding="utf-8",
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
    (run_dir / "deterministic_decision.json").write_text(
        json.dumps({"policy_digest": "sha256:def", "findings": [], "executed_checks": []}),
        encoding="utf-8",
    )
    (run_dir / "model_assisted_critique.json").write_text(
        json.dumps(
            {
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
            }
        ),
        encoding="utf-8",
    )

    answer_key = Path("scripts/workloads/fixtures/code_review_probe_v1/human_review_answer_key.json")
    report = module.score_answer_key(run_dir=run_dir, answer_key_path=answer_key)

    issue_rows = {row["issue_id"]: row for row in report["issues"]}

    assert issue_rows["RAW_PAYLOAD_EVAL"]["model_hit"] is True
    assert issue_rows["RAW_PAYLOAD_EVAL"]["reasoning_hits"] >= 1
    assert issue_rows["RAW_PAYLOAD_EVAL"]["fix_hits"] >= 1
    assert issue_rows["VERIFY_SIGNATURE_ALWAYS_TRUE"]["model_hit"] is True
    assert report["model_assisted"]["reasoning_score"] >= 2
    assert report["model_assisted"]["fix_score"] >= 1
