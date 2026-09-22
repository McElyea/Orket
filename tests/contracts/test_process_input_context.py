"""Layer: contract. Explicit input isolation and native path admission rules."""
from pathlib import Path

import pytest

from orket.application.services.process_input_service import capture_process_context

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("supplied", [{}, {"ORKET_TEST_INPUT": "admitted"}], ids=["empty", "explicit"])
def test_explicit_absolute_context_never_reads_ambient_directory(tmp_path, monkeypatch, supplied):
    def unexpected():
        raise AssertionError("An explicit absolute directory must not depend on ambient cwd")

    monkeypatch.setattr(Path, "cwd", unexpected)
    expected = dict(supplied)
    directory, environment = capture_process_context(cwd=tmp_path, environment=supplied)
    supplied["ORKET_TEST_INPUT"] = "changed"
    assert directory == tmp_path and dict(environment) == expected
    with pytest.raises(TypeError):
        environment["ORKET_TEST_INPUT"] = "mutated"


def test_drive_relative_context_obeys_native_path_semantics(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    selected = Path("C:relative")
    if selected.drive:
        with pytest.raises(ValueError, match="E_PROCESS_DRIVE_RELATIVE_PATH_UNSUPPORTED"):
            capture_process_context(cwd=selected, environment={})
    else:
        # A colon is an ordinary POSIX filename, not a hidden drive directory.
        assert capture_process_context(cwd=selected, environment={})[0] == tmp_path / selected
