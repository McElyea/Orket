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
