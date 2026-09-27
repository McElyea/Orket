# LIFECYCLE: live
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.governance.enforce_test_taxonomy import evaluate_test_taxonomy, main

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def git_fixture(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_enforce_test_taxonomy_reports_missing_labels(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests" / "test_sample.py",
        "\n".join(
            [
                "import pytest",
                "@pytest.mark.unit",
                "def test_with_layer():",
                "    assert True",
                "",
                "def test_missing_layer():",
                "    assert True",
            ]
        )
        + "\n",
    )
    payload = evaluate_test_taxonomy(root=tmp_path / "tests")
    assert payload["tests_total"] == 2
    assert payload["missing_layer_total"] == 1
    assert payload["by_layer"]["unit"] == 1
    assert payload["by_layer"]["unlabeled"] == 1


def test_enforce_test_taxonomy_main_strict_fails_when_missing_layer(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests" / "test_sample.py",
        "\n".join(
            [
                "def test_missing_layer():",
                "    assert True",
            ]
        )
        + "\n",
    )
    exit_code = main(["--root", str(tmp_path / "tests"), "--strict"])
    assert exit_code == 1


def test_enforce_test_taxonomy_main_non_strict_passes_with_missing_layer(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests" / "test_sample.py",
        "\n".join(
            [
                "def test_missing_layer():",
                "    assert True",
            ]
        )
        + "\n",
    )
    exit_code = main(["--root", str(tmp_path / "tests")])
    assert exit_code == 0


def test_collected_markers_include_modules_classes_and_parameters(tmp_path: Path) -> None:
    _write(tmp_path / "test_module.py", """
import pytest
pytestmark = pytest.mark.integration
def test_module_mark():
    raise AssertionError('collection must never execute the body')
class TestInherited:
    def test_inherited(self):
        assert True
""")
    _write(tmp_path / "test_cases.py", """
import pytest
@pytest.mark.contract
class TestBase:
    def test_base(self):
        assert True
class TestChild(TestBase):
    pass
@pytest.mark.parametrize('value', [
    pytest.param(1, marks=pytest.mark.unit),
    pytest.param(2, marks=pytest.mark.end_to_end),
])
def test_parameters(value):
    assert value
""")
    payload = evaluate_test_taxonomy(root=tmp_path)
    assert payload["ok"] is True
    assert payload["tests_total"] == 6
    assert payload["by_layer"] == {"contract": 2, "end_to_end": 1, "integration": 2, "unit": 1}


def test_prose_is_not_a_layer_and_conflicting_inherited_marks_are_invalid(tmp_path: Path) -> None:
    _write(tmp_path / "test_layers.py", """
import pytest
# Layer: unit
def test_prose_only():
    assert True
@pytest.mark.contract
class TestConflicting:
    @pytest.mark.integration
    def test_two_layers(self):
        assert True
@pytest.mark.unit
@pytest.mark.unit
def test_repeated_identical_layer():
    assert True
""")
    payload = evaluate_test_taxonomy(root=tmp_path)
    assert payload["missing_layer_total"] == 1
    assert payload["missing_layers"][0]["test_name"] == "test_prose_only"
    assert payload["invalid_layer_total"] == 1
    assert payload["invalid_layers"][0]["layers"] == ["contract", "integration"]
    assert main(["--root", str(tmp_path), "--strict"]) == 1


def test_parameter_marks_do_not_classify_other_cases(tmp_path: Path) -> None:
    _write(tmp_path / "test_parameters.py", """
import pytest
@pytest.mark.parametrize('value', [pytest.param(1, marks=pytest.mark.unit), 2])
def test_case(value):
    assert value
""")
    payload = evaluate_test_taxonomy(root=tmp_path)
    assert payload["tests_total"] == 2
    assert payload["missing_layer_total"] == 1
    assert payload["missing_layers"][0]["test_name"] == "test_case[2]"


@pytest.mark.parametrize("source", ["def broken(:", "raise RuntimeError('collection sentinel')"])
def test_collection_failure_never_passes_even_without_strict(tmp_path: Path, source: str) -> None:
    _write(tmp_path / "test_broken.py", source)
    payload = evaluate_test_taxonomy(root=tmp_path)
    assert payload["ok"] is False
    assert payload["collection_exit_code"] != 0
    assert payload["collection_errors"]
    assert main(["--root", str(tmp_path)]) == 1


def test_empty_collection_never_passes(tmp_path: Path) -> None:
    payload = evaluate_test_taxonomy(root=tmp_path)
    assert payload["ok"] is False
    assert payload["tests_total"] == 0
    assert payload["collection_exit_code"] == 5
    assert main(["--root", str(tmp_path)]) == 1


def test_collection_ignores_parent_filters_and_retains_deselected_items(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k absent_test")
    _write(tmp_path / "conftest.py", """
def pytest_collection_modifyitems(config, items):
    removed = list(items)
    items[:] = []
    config.hook.pytest_deselected(items=removed)
""")
    _write(tmp_path / "test_unmarked.py", "def test_unmarked():\n    assert True\n")
    payload = evaluate_test_taxonomy(root=tmp_path)
    assert payload["tests_total"] == 1
    assert payload["missing_layer_total"] == 1


def test_missing_root_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="E_TEST_TAXONOMY_ROOT_MISSING"):
        evaluate_test_taxonomy(root=tmp_path / "absent")


def test_ignored_files_are_not_collected(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "ignored/\n")
    _write(tmp_path / "ignored" / "test_untracked.py", "raise RuntimeError('must not import')\n")
    _write(tmp_path / "test_visible.py", "import pytest\n@pytest.mark.unit\ndef test_visible(): assert True\n")
    payload = evaluate_test_taxonomy(root=tmp_path)
    assert payload["ok"] is True
    assert payload["tests_total"] == 1


def test_failed_git_discovery_is_not_empty_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Workspace-local fixtures must not discover the enclosing worktree.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    (tmp_path / ".git").rename(tmp_path / "git-disabled")
    _write(tmp_path / "test_visible.py", "import pytest\n@pytest.mark.unit\ndef test_visible(): assert True\n")
    payload = evaluate_test_taxonomy(root=tmp_path)
    assert payload["ok"] is False
    assert "E_TEST_TAXONOMY_INVENTORY" in payload["collection_errors"][0]
