from __future__ import annotations

from pathlib import Path


def test_quality_workflow_enforces_architecture_and_volatility_gates() -> None:
    workflow_path = Path(".gitea/workflows/quality.yml")
    text = workflow_path.read_text(encoding="utf-8")

    required_commands = [
        "python scripts/check_dependency_direction.py",
        "python scripts/check_volatility_boundaries.py",
        "python -m pytest -q tests/platform/test_architecture_volatility_boundaries.py",
    ]
    missing = [cmd for cmd in required_commands if cmd not in text]
    assert not missing, "quality workflow missing required architecture gates: " + ", ".join(missing)
