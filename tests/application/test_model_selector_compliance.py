from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.model_selection_service import ModelSelectionService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _selector(organization=None, preferences=None, user_settings=None):
    return await ModelSelectionService(environment=dict(os.environ)).prepare(
        organization, preferences or {}, user_settings or {})


def _org_with_policy(policy: dict):
    return SimpleNamespace(
        architecture=SimpleNamespace(preferred_stack={}),
        process_rules={"model_compliance_policy": policy},
    )


# Layer: integration
async def test_model_selector_demotes_blocked_model_to_fallback():
    selector = await _selector(
        organization=_org_with_policy(
            {
                "enabled": True,
                "fallback_model": "qwen2.5-coder:14b",
                "blocked_models": ["qwen2.5-coder:7b"],
            }
        ),
        preferences={"models": {"coder": "qwen2.5-coder:7b"}},
    )
    selected = selector.select(role="coder").final_model
    assert selected == "qwen2.5-coder:14b"


# Layer: integration
async def test_model_selector_demotes_low_compliance_score_from_inline_scores():
    selector = await _selector(
        organization=_org_with_policy(
            {
                "enabled": True,
                "min_score": 85,
                "fallback_model": "llama3.1:8b",
                "model_scores": {"qwen2.5-coder:7b": 72.0},
            }
        ),
        preferences={"models": {"coder": "qwen2.5-coder:7b"}},
    )
    selected = selector.select(role="coder").final_model
    assert selected == "llama3.1:8b"


# Layer: integration
async def test_model_selector_keeps_model_when_score_meets_threshold():
    selector = await _selector(
        organization=_org_with_policy(
            {
                "enabled": True,
                "min_score": 85,
                "fallback_model": "llama3.1:8b",
                "model_scores": {"qwen2.5-coder:7b": 90.0},
            }
        ),
        preferences={"models": {"coder": "qwen2.5-coder:7b"}},
    )
    selected = selector.select(role="coder").final_model
    assert selected == "qwen2.5-coder:7b"


# Layer: integration
async def test_model_selector_uses_score_source_report_file(tmp_path: Path):
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
    selector = await _selector(
        organization=_org_with_policy(
            {
                "enabled": True,
                "min_score": 85,
                "fallback_model": "qwen2.5-coder:14b",
                "score_source": str(report_path),
            }
        ),
        preferences={"models": {"coder": "qwen2.5-coder:7b"}},
    )
    selected = selector.select(role="coder").final_model
    assert selected == "qwen2.5-coder:14b"
