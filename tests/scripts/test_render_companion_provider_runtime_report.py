# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.companion.render_companion_provider_runtime_report import main, render_markdown_report


def _sample_payload() -> dict[str, object]:
    return {
        "generated_at_utc": "2026-03-09T00:00:00Z",
        "status": "partial",
        "observed_result": "partial success",
        "summary": {
            "requested_cases": 2,
            "successful_cases": 1,
            "failed_cases": 1,
            "blocker_count": 1,
        },
        "recommendations": {
            "by_rig_class": {
                "A": {
                    "chat-first": {
                        "status": "recommended",
                        "provider": "ollama",
                        "model": "qwen2.5-coder:7b",
                        "composite_score": 0.84,
                        "profile_coverage": 1.0,
                    }
                }
            }
        },
        "blockers": [
            {
                "provider": "lmstudio",
                "model": "qwen2.5-coder:14b",
                "step": "status",
                "observed_path": "blocked",
                "category": "runtime",
                "error": "connection refused",
            }
        ],
        "cases": [
            {
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "result": "success",
                "observed_path": "primary",
                "latency_ms": 640,
                "scores": {
                    "reasoning": {"status": "measured", "value": 1.0},
                    "memory_usefulness": {"status": "measured", "value": 0.8},
                    "voice_suitability": {"status": "measured", "value": 0.9},
                    "stability": {"status": "measured", "value": 1.0},
                    "mode_adherence": {"status": "measured", "value": 1.0},
                },
            }
        ],
    }


def test_render_markdown_report_includes_summary_recommendation_and_blockers() -> None:
    """Layer: contract. Verifies markdown rendering includes required sections and key matrix fields."""
    report = render_markdown_report(_sample_payload())
    assert "# Companion Provider/Runtime Matrix Report" in report
    assert "## Recommendations" in report
    assert "qwen2.5-coder:7b" in report
    assert "## Blockers" in report
    assert "connection refused" in report
    assert "## Case Scores" in report


def test_render_companion_provider_runtime_report_main_writes_markdown_file(tmp_path: Path) -> None:
    """Layer: integration. Verifies CLI main writes markdown report from matrix JSON input."""
    input_path = tmp_path / "matrix.json"
    output_path = tmp_path / "README.md"
    input_path.write_text(json.dumps(_sample_payload()), encoding="utf-8")

    exit_code = main(["--input", str(input_path), "--output", str(output_path)])
    assert exit_code == 0
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Companion Provider/Runtime Matrix Report" in content
    assert "qwen2.5-coder:7b" in content


def test_render_companion_provider_runtime_report_main_fails_when_input_missing(tmp_path: Path) -> None:
    """Layer: integration. Verifies CLI fails fast with explicit code when the input artifact path does not exist."""
    missing = tmp_path / "missing.json"
    with pytest.raises(SystemExit, match="E_COMPANION_MATRIX_REPORT_INPUT_MISSING"):
        main(["--input", str(missing), "--output", str(tmp_path / "README.md")])
