from __future__ import annotations

from pathlib import Path

import pytest

from scripts.extensions.bootstrap_controller_external_repo import bootstrap_controller_external_repo, main


def test_bootstrap_controller_external_repo_writes_template_files(tmp_path: Path) -> None:
    target = tmp_path / "external_controller"
    result = bootstrap_controller_external_repo(target_dir=target, force=False)
    assert result == target.resolve()
    assert (target / "manifest.json").exists()
    assert (target / "extension.json").exists()
    assert (target / "workload_entrypoint.py").exists()


def test_bootstrap_controller_external_repo_refuses_existing_files_without_force(tmp_path: Path) -> None:
    target = tmp_path / "external_controller"
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Target already contains template files"):
        bootstrap_controller_external_repo(target_dir=target, force=False)


def test_bootstrap_controller_external_repo_main_overwrites_with_force(tmp_path: Path) -> None:
    target = tmp_path / "external_controller"
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text("{}", encoding="utf-8")

    exit_code = main(["--target", str(target), "--force"])
    assert exit_code == 0
    text = (target / "manifest.json").read_text(encoding="utf-8")
    assert "controller.workload.external" in text
