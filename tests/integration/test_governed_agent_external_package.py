from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from setuptools import build_meta


def test_governed_agent_external_sdist_preserves_validation_surface(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: integration. Proves a clean starter sdist retains its host-validation surface."""
    template = Path(__file__).resolve().parents[2] / "docs" / "templates" / "governed_agent_external"
    source = tmp_path / "source"
    shutil.copytree(
        template,
        source,
        ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__"),
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.chdir(source)

    artifact_name = build_meta.build_sdist(str(dist))

    with tarfile.open(dist / artifact_name, mode="r:gz") as archive:
        members = {Path(name).name for name in archive.getnames()}
    assert {
        "README.md",
        "extension.yaml",
        "governed_agent.py",
        "pyproject.toml",
        "test_governed_agent.py",
    } <= members
