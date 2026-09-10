# Layer: integration

from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path

from setuptools import build_meta


def test_clean_core_artifacts_own_the_default_prompt_registry(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Real core builds retain the single registry, without checkout build caches."""
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(root / name, source / name)
    shutil.copytree(root / "orket", source / "orket", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.chdir(source)

    wheel_name = build_meta.build_wheel(str(dist))
    sdist_name = build_meta.build_sdist(str(dist))

    registry = "orket/runtime/config/local_prompt_profiles.json"
    expected = (root / registry).read_bytes()
    with zipfile.ZipFile(dist / wheel_name) as wheel:
        assert wheel.read(registry) == expected
        assert not any("orket_extension_sdk/" in name for name in wheel.namelist())
    with tarfile.open(dist / sdist_name, mode="r:gz") as sdist:
        matches = [name for name in sdist.getnames() if name.endswith("/" + registry)]
        assert len(matches) == 1
        member = sdist.extractfile(matches[0])
        assert member is not None and member.read() == expected
        assert not any("orket_extension_sdk/" in name for name in sdist.getnames())
    assert not (root / "model/core/contracts/local_prompt_profiles.json").exists()
