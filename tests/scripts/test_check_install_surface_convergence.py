from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_install_surface_convergence import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_repo(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        'Install:\npython -m pip install -e ".[dev]"\n',
    )
    _write(
        tmp_path / "docs" / "CONTRIBUTOR.md",
        'Quick setup: python -m pip install -e ".[dev]"\n',
    )
    _write(
        tmp_path / "docs" / "RUNBOOK.md",
        'Bootstrap: python -m pip install -e ".[dev]"\n',
    )
    _write(
        tmp_path / "requirements.txt",
        "# derived shim\n-e .[dev]\n",
    )
    _write(
        tmp_path / ".gitea" / "workflows" / "quality.yml",
        "steps:\n  - run: |\n      python -m pip install --upgrade pip\n      python -m pip install -e \".[dev]\"\n  - run: |\n      python scripts/governance/check_install_surface_convergence.py\n",
    )


def test_check_install_surface_convergence_passes_and_writes_result(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    out_path = tmp_path / "benchmarks" / "result.json"
    exit_code = main(["--repo-root", str(tmp_path), "--out", str(out_path)])
    assert exit_code == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert "diff_ledger" in payload
    assert payload["failures"] == []


def test_check_install_surface_convergence_fails_on_legacy_doc_command(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    _write(tmp_path / "README.md", "pip install -r requirements.txt\n")
    exit_code = main(["--repo-root", str(tmp_path)])
    assert exit_code == 1


def test_check_install_surface_convergence_fails_when_workflow_missing_canonical_command(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    _write(
        tmp_path / ".gitea" / "workflows" / "quality.yml",
        "steps:\n  - run: |\n      python -m pip install --upgrade pip\n      pip install setuptools\n  - run: |\n      python scripts/governance/check_install_surface_convergence.py\n",
    )
    exit_code = main(["--repo-root", str(tmp_path)])
    assert exit_code == 1


def test_check_install_surface_convergence_fails_on_requirements_drift(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    _write(tmp_path / "requirements.txt", "fastapi==0.109.0\n")
    exit_code = main(["--repo-root", str(tmp_path)])
    assert exit_code == 1
