from __future__ import annotations

from pathlib import Path

import pytest

from orket.reforger.modes import ModeValidationError, load_mode


def _write_mode(path: Path, *, hard: str = "  - never fabricate\n", soft: str = "  - be concise\n") -> None:
    path.write_text(
        "".join(
            [
                "mode_id: truth_only\n",
                "description: truth mode\n",
                "hard_rules:\n",
                hard,
                "soft_rules:\n",
                soft,
                "rubric:\n",
                "  quality: 1.0\n",
                "required_outputs:\n",
                "  - refusal_reason\n",
                "suite_ref: suites/truth_only\n",
            ]
        ),
        encoding="utf-8",
    )


def test_mode_schema_validates_and_normalizes(tmp_path: Path) -> None:
    mode_file = tmp_path / "truth_only.yaml"
    _write_mode(mode_file)
    mode = load_mode(mode_file)
    assert mode.mode_id == "truth_only"
    assert mode.hard_rules == ("never fabricate",)
    assert mode.soft_rules == ("be concise",)
    assert tuple(mode.rubric.keys()) == ("quality",)


def test_mode_invalid_hard_rules_fails(tmp_path: Path) -> None:
    mode_file = tmp_path / "bad.yaml"
    _write_mode(mode_file, hard="  - \n")
    with pytest.raises(ModeValidationError):
        load_mode(mode_file)

