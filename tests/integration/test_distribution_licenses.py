"""Contract controls over real archives; these do not establish legal title or runtime proof."""
from __future__ import annotations

import io
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

from scripts.governance.check_licenses import check_sources, copy_targets, inspect_distribution
from scripts.sdk.check_sdk_tag_version import _load_sdk_version

pytestmark = pytest.mark.contract


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "license-fixture"\nversion = "1.0.0"\n'
        'license = "Apache-2.0"\nlicense-files = ["LICENSE", "NOTICE"]\n', encoding="utf-8")
    (project / "LICENSE").write_bytes(b"canonical license text\n")
    (project / "NOTICE").write_bytes(b"copyright attribution\n")
    return project


def _archive(tmp_path: Path, project: Path, kind: str, defect: str | None = None,
             templates: dict[str, bytes] | None = None) -> Path:
    name = tomllib.loads((project / "pyproject.toml").read_text())["project"]["name"]
    metadata = (f"Metadata-Version: 2.4\nName: {name}\nVersion: 1.0.0\n"
                "License-Expression: Apache-2.0\nLicense-File: LICENSE\nLicense-File: NOTICE\n\n")
    if defect == "version":
        metadata = metadata.replace("Version: 1.0.0", "Version: 0.9.0")
    if defect == "expression":
        metadata = metadata.replace("Apache-2.0", "BUSL-1.1")
    if defect == "metadata":
        metadata = metadata.replace("License-File: NOTICE\n", "")
    if defect == "duplicate-field":
        metadata = metadata.replace("Name: ", "License-Expression: Apache-2.0\nName: ")
    prefix = "license_fixture-1.0.0.dist-info/" if kind == "wheel" else "license_fixture-1.0.0/"
    files = {prefix + ("METADATA" if kind == "wheel" else "PKG-INFO"): metadata.encode()}
    if (project / "THIRD_PARTY_NOTICES.txt").exists():
        metadata = metadata.replace("License-File: NOTICE\n", "License-File: NOTICE\nLicense-File: THIRD_PARTY_NOTICES.txt\n")
        files[next(iter(files))] = metadata.encode()
        files[prefix + ("licenses/" if kind == "wheel" else "") + "THIRD_PARTY_NOTICES.txt"] = b"upstream licenses"
    files.update({("" if kind == "wheel" else prefix) + name: content for name, content in (templates or {}).items()})
    for filename in ("LICENSE", "NOTICE"):
        if defect == "missing" and filename == "NOTICE":
            continue
        location = prefix + ("licenses/" if kind == "wheel" else "") + filename
        files[location] = b"wrong bytes" if defect == "bytes" else (project / filename).read_bytes()
    path = tmp_path / ("fixture.whl" if kind == "wheel" else "fixture.tar.gz")
    if kind == "wheel":
        with zipfile.ZipFile(path, "w") as archive:
            for filename, content in files.items():
                archive.writestr(filename, content)
            if defect == "duplicate-member":
                with pytest.warns(UserWarning, match="Duplicate name"):
                    archive.writestr(next(iter(files)), metadata.encode())
    else:
        with tarfile.open(path, "w:gz") as archive:
            for filename, content in list(files.items()) + (list(files.items())[:1] if defect == "duplicate-member" else []):
                info = tarfile.TarInfo(filename)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
    return path


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_distribution_requires_matching_metadata_and_actual_notice_bytes(tmp_path, kind):
    project = _project(tmp_path)
    result = inspect_distribution(_archive(tmp_path, project, kind), project)
    assert result["expression"] == "Apache-2.0"
    assert result["files"] == ["LICENSE", "NOTICE"]


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("defect", ["missing", "bytes", "version", "expression", "metadata",
                                    "duplicate-field", "duplicate-member"])
def test_distribution_rejects_missing_stale_and_ambiguous_licensing(tmp_path, kind, defect):
    project = _project(tmp_path)
    with pytest.raises(ValueError):
        inspect_distribution(_archive(tmp_path, project, kind, defect), project)


def test_package_configuration_cannot_omit_copyright_notice(tmp_path):
    project = _project(tmp_path)
    path = project / "pyproject.toml"
    path.write_text(path.read_text().replace('["LICENSE", "NOTICE"]', '["LICENSE"]'), encoding="utf-8")
    with pytest.raises(ValueError, match="omits required"):
        inspect_distribution(_archive(tmp_path, project, "wheel"), project)


def test_source_copies_refuse_missing_or_modified_notice_and_can_be_refreshed(tmp_path):
    for filename in copy_targets():
        (tmp_path / filename).write_bytes(filename.encode())
    with pytest.raises(ValueError, match="Missing or stale"):
        check_sources(tmp_path)
    check_sources(tmp_path, write=True)
    check_sources(tmp_path)
    target = tmp_path / copy_targets()["THIRD_PARTY_NOTICES.txt"][1]
    target.write_bytes(b"stale frontend attribution")
    with pytest.raises(ValueError, match="Missing or stale"):
        check_sources(tmp_path)
    check_sources(tmp_path, write=True)
    assert target.read_bytes() == (tmp_path / "THIRD_PARTY_NOTICES.txt").read_bytes()


def test_sdk_version_observation_does_not_execute_selected_package_code(tmp_path):
    package = tmp_path / "orket_extension_sdk"
    package.mkdir()
    marker = tmp_path / "side-effect"
    (package / "__version__.py").write_text(
        f'from pathlib import Path\nPath({str(marker)!r}).touch()\n__version__ = "0.8.0"\n', encoding="utf-8")
    assert _load_sdk_version(tmp_path) == "0.8.0"
    assert not marker.exists()
    (package / "__version__.py").write_text('__version__ = str(8)\n', encoding="utf-8")
    with pytest.raises(ValueError):
        _load_sdk_version(tmp_path)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("defect", [None, "missing", "changed"])
def test_core_nested_templates_must_preserve_full_notices(tmp_path, kind, defect):
    project = _project(tmp_path)
    config = project / "pyproject.toml"
    config.write_text(config.read_text().replace('"license-fixture"', '"orket"').replace(
        '["LICENSE", "NOTICE"]', '["LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.txt"]'), encoding="utf-8")
    (project / "THIRD_PARTY_NOTICES.txt").write_bytes(b"upstream licenses")
    templates = {}
    for name in ("external_extension", "governed_agent_external"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for filename in ("LICENSE", "NOTICE"):
                archive.writestr(filename, (project / filename).read_bytes())
            if name == "external_extension":
                for location in ("frontend/public", "static"):
                    if defect == "missing" and location == "static":
                        continue
                    archive.writestr(f"src/companion_app/{location}/THIRD_PARTY_NOTICES.txt",
                                     b"stale" if defect == "changed" else b"upstream licenses")
        templates[f"orket/runtime/config/assets/extension_templates/{name}.zip"] = buffer.getvalue()
    candidate = _archive(tmp_path, project, kind, templates=templates)
    if defect:
        with pytest.raises(ValueError, match="Packaged template"):
            inspect_distribution(candidate, project)
    else:
        assert inspect_distribution(candidate, project)["name"] == "orket"
