# LIFECYCLE: live
from __future__ import annotations

from pathlib import Path

from scripts.governance.enforce_test_taxonomy import evaluate_test_taxonomy, main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Layer: contract
def test_enforce_test_taxonomy_reports_missing_labels(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests" / "test_sample.py",
        "\n".join(
            [
                "# Layer: unit",
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


# Layer: integration
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


# Layer: integration
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
