from __future__ import annotations

from pathlib import Path


def test_coverage_threshold_workflow_enforces_project_coverage_gate() -> None:
    """Layer: contract. Verifies coverage threshold enforcement is explicit CI behavior."""
    workflow = Path(".gitea/workflows/coverage-threshold.yml").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "python -m pytest --cov=orket --cov-report=term --cov-fail-under=70" in workflow
    assert 'ORKET_DISABLE_SANDBOX: "1"' in workflow
    assert "[tool.coverage.report]" in pyproject
    assert "fail_under = 70" in pyproject
