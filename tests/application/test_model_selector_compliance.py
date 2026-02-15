from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from orket.orchestration.models import ModelSelector


def _org_with_policy(policy: dict):
    return SimpleNamespace(
        architecture=SimpleNamespace(preferred_stack={}),
        process_rules={"model_compliance_policy": policy},
    )


def test_model_selector_demotes_blocked_model_to_fallback():
    selector = ModelSelector(
        organization=_org_with_policy(
            {
                "enabled": True,
                "fallback_model": "qwen2.5-coder:14b",
                "blocked_models": ["qwen2.5-coder:7b"],
            }
        ),
        user_settings={"preferred_coder": "qwen2.5-coder:7b"},
    )
    selected = selector.select(role="coder")
    assert selected == "qwen2.5-coder:14b"


def test_model_selector_demotes_low_compliance_score_from_inline_scores():
    selector = ModelSelector(
        organization=_org_with_policy(
            {
                "enabled": True,
                "min_score": 85,
                "fallback_model": "llama3.1:8b",
                "model_scores": {"qwen2.5-coder:7b": 72.0},
            }
        ),
        user_settings={"preferred_coder": "qwen2.5-coder:7b"},
    )
    selected = selector.select(role="coder")
    assert selected == "llama3.1:8b"


def test_model_selector_keeps_model_when_score_meets_threshold():
    selector = ModelSelector(
        organization=_org_with_policy(
            {
                "enabled": True,
                "min_score": 85,
                "fallback_model": "llama3.1:8b",
                "model_scores": {"qwen2.5-coder:7b": 90.0},
            }
        ),
        user_settings={"preferred_coder": "qwen2.5-coder:7b"},
    )
    selected = selector.select(role="coder")
    assert selected == "qwen2.5-coder:7b"


def test_model_selector_uses_score_source_report_file(tmp_path: Path):
    report_path = tmp_path / "pattern_report.json"
    report_path.write_text(
        json.dumps(
            {
                "model_compliance": {
                    "qwen2.5-coder:7b": {"compliance_score": 70.0},
                }
            }
        ),
        encoding="utf-8",
    )
    selector = ModelSelector(
        organization=_org_with_policy(
            {
                "enabled": True,
                "min_score": 85,
                "fallback_model": "qwen2.5-coder:14b",
                "score_source": str(report_path),
            }
        ),
        user_settings={"preferred_coder": "qwen2.5-coder:7b"},
    )
    selected = selector.select(role="coder")
    assert selected == "qwen2.5-coder:14b"
