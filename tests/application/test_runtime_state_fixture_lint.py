from __future__ import annotations

from pathlib import Path


def test_runtime_state_test_references_require_fresh_fixture() -> None:
    """Layer: unit. Lints tests that touch the module-level runtime_state singleton."""
    root = Path(__file__).resolve().parents[2]
    patterns = (
        "from orket.state import runtime_state",
        "orket.state.runtime_state",
        "api_module.runtime_state",
        "state_module.runtime_state",
    )
    allowed_paths = {
        Path("tests/conftest.py"),
        Path("tests/application/test_runtime_state_fixture_lint.py"),
    }
    violations: list[str] = []
    for path in sorted((root / "tests").rglob("test_*.py")):
        relative_path = path.relative_to(root)
        if relative_path in allowed_paths:
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in patterns) and "fresh_runtime_state" not in text:
            violations.append(relative_path.as_posix())

    assert violations == []
