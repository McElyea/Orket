# Layer: integration

from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path

import pytest
from setuptools import build_meta

pytestmark = pytest.mark.integration


def test_clean_core_artifacts_own_the_default_prompt_registry(tmp_path: Path, monkeypatch) -> None:
    """Real clean builds retain package data exactly, including the single prompt registry."""
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

    expected = {path.relative_to(source).as_posix(): path.read_bytes()
                for path in (source / "orket").rglob("*")
                if path.is_file() and path.suffix not in {".py", ".pyc"}}
    assert "orket/runtime/config/local_prompt_profiles.json" in expected
    assert "orket/runtime/config/qwen38_text_chatml.jinja" in expected
    with zipfile.ZipFile(dist / wheel_name) as wheel:
        actual = {name: wheel.read(name) for name in wheel.namelist()
                  if name.startswith("orket/") and not name.endswith(("/", ".py", ".pyc"))}
        assert actual == expected
        assert not any("orket_extension_sdk/" in name for name in wheel.namelist())
    with tarfile.open(dist / sdist_name, mode="r:gz") as sdist:
        actual = {member.name.partition("/")[2]: sdist.extractfile(member).read()
                  for member in sdist.getmembers() if member.isfile()
                  and member.name.partition("/")[2].startswith("orket/")
                  and not member.name.endswith((".py", ".pyc"))}
        assert actual == expected
        assert not any("orket_extension_sdk/" in name for name in sdist.getnames())
    assert not (root / "model/core/contracts/local_prompt_profiles.json").exists()
