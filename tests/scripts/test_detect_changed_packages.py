from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_detect_changed_packages_treats_missing_base_ref_as_all_changed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    config_dir = repo / ".ci"
    config_dir.mkdir()
    config = {
        "packages": [
            {"id": "pkg-a", "path": "packages/a"},
            {"id": "pkg-b", "path": "packages/b"},
        ],
        "global_trigger_paths": [],
    }
    (config_dir / "packages.json").write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)

    result = subprocess.run(
        [
            "python",
            str(Path("scripts/ci/detect_changed_packages.py").resolve()),
            "--config",
            ".ci/packages.json",
            "--base-ref",
            "origin/main",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "changed_ids=pkg-a,pkg-b" in result.stdout
    assert "any_changed=true" in result.stdout
