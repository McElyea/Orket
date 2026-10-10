"""Synchronize canonical license copies and verify built distribution licensing."""
from __future__ import annotations

import argparse
import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orket.core.contracts.extension_templates import EXTENSION_TEMPLATE_SOURCES  # noqa: E402
from scripts.sdk.check_sdk_tag_version import _load_sdk_version  # noqa: E402


def copy_targets() -> dict[str, tuple[str, ...]]:
    """The root files are authoritative; standalone distributions carry checked copies."""
    roots = ("orket_extension_sdk", *(f"docs/templates/{name}" for _, name in EXTENSION_TEMPLATE_SOURCES))
    companion = "docs/templates/external_extension/src/companion_app"
    return {
        "LICENSE": tuple(f"{root}/LICENSE" for root in roots),
        "NOTICE": tuple(f"{root}/NOTICE" for root in roots),
        "THIRD_PARTY_NOTICES.txt": (f"{companion}/frontend/public/THIRD_PARTY_NOTICES.txt",
                                    f"{companion}/static/THIRD_PARTY_NOTICES.txt"),
    }


def check_sources(root: Path, *, write: bool = False) -> None:
    for source, targets in copy_targets().items():
        content = (root / source).read_bytes()
        if not content:
            raise ValueError(f"Empty canonical license file: {source}")
        for name in targets:
            target = root / name
            if write:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            if not target.is_file() or target.read_bytes() != content:
                raise ValueError(f"Missing or stale license copy: {name}")


def project_identity(project: Path) -> tuple[dict, str]:
    config = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = config.get("version")
    if version is None and config["name"] == "orket-extension-sdk":
        version = _load_sdk_version(project.parent)
    if not isinstance(version, str) or not version:
        raise ValueError(f"No supported version authority: {project}")
    return config, version


def _archive_files(path: Path) -> tuple[dict[str, bytes], str, str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = [item.filename for item in archive.infolist() if not item.is_dir()]
            if len(names) != len(set(names)):
                raise ValueError(f"Duplicate archive member: {path}")
            files = {name: archive.read(name) for name in names}
        metadata = [name for name in files if len(Path(name).parts) == 2 and name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Expected one wheel METADATA")
        return files, metadata[0], metadata[0].removesuffix("METADATA") + "licenses/"
    with tarfile.open(path, "r:gz") as archive:
        members = [item for item in archive.getmembers() if item.isfile()]
        if len(members) != len({item.name for item in members}):
            raise ValueError(f"Duplicate archive member: {path}")
        files = {}
        for item in members:
            with archive.extractfile(item) as handle:
                files[item.name] = handle.read()
    metadata = [name for name in files if len(Path(name).parts) == 2 and Path(name).name == "PKG-INFO"]
    if len(metadata) != 1:
        raise ValueError("Expected one top-level sdist PKG-INFO")
    return files, metadata[0], metadata[0].removesuffix("PKG-INFO")


def _check_templates(files: dict[str, bytes], prefix: str, project: Path) -> None:
    for _, name in EXTENSION_TEMPLATE_SOURCES:
        member = prefix + f"orket/runtime/config/assets/extension_templates/{name}.zip"
        if member not in files:
            raise ValueError(f"Distribution omits packaged template: {name}")
        with zipfile.ZipFile(BytesIO(files[member])) as template:
            expected = {"LICENSE": "LICENSE", "NOTICE": "NOTICE"}
            if name == "external_extension":
                expected.update({"src/companion_app/static/THIRD_PARTY_NOTICES.txt": "THIRD_PARTY_NOTICES.txt",
                                 "src/companion_app/frontend/public/THIRD_PARTY_NOTICES.txt": "THIRD_PARTY_NOTICES.txt"})
            for target, source in expected.items():
                if template.namelist().count(target) != 1 or template.read(target) != (project / source).read_bytes():
                    raise ValueError(f"Packaged template omits or changes licensing: {name}/{target}")


def inspect_distribution(path: Path, project: Path) -> dict:
    """Inspect actual wheel/sdist bytes; metadata alone cannot prove notice inclusion."""
    config, version = project_identity(project)
    expected = config["license-files"]
    if not expected or len(expected) != len(set(expected)):
        raise ValueError("Declare distinct, explicit license files")
    required = {"LICENSE", "NOTICE"}
    if config["name"] == "orket":
        required.add("THIRD_PARTY_NOTICES.txt")
    elif config["name"] == "orket-companion-template":
        required.add("src/companion_app/static/THIRD_PARTY_NOTICES.txt")
    if not required.issubset(expected):
        raise ValueError("Package configuration omits required license/notice files")
    files, metadata_path, prefix = _archive_files(path)
    metadata = BytesParser().parsebytes(files[metadata_path])
    for field, value in (("Name", config["name"]), ("Version", version), ("License-Expression", config["license"])):
        if metadata.get_all(field) != [value]:
            raise ValueError(f"Missing or stale {field}: {path.name}")
    declared = metadata.get_all("License-File", [])
    if sorted(declared) != sorted(expected):
        raise ValueError(f"Missing or unexpected License-File metadata: {path.name}")
    for name in expected:
        source = (project / name).resolve(strict=True)
        if not source.is_relative_to(project.resolve()):
            raise ValueError(f"License file escapes package root: {name}")
        if prefix + name not in files or files[prefix + name] != source.read_bytes():
            raise ValueError(f"Missing or changed license bytes: {name}")
    if config["name"] == "orket":
        _check_templates(files, "" if path.suffix == ".whl" else prefix, project)
    return {"name": config["name"], "version": version, "expression": config["license"], "files": expected}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Refresh distribution copies from root license files")
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--dist", type=Path, help="Require and inspect this project's wheel and sdist")
    args = parser.parse_args()
    try:
        check_sources(ROOT, write=args.write)
        if args.dist:
            config, version = project_identity(args.project)
            stem = config["name"].replace("-", "_") + "-" + version
            for pattern in (stem + "-*.whl", stem + ".tar.gz"):
                matches = list(args.dist.glob(pattern))
                if len(matches) != 1:
                    raise ValueError(f"Expected one {pattern} in {args.dist}")
                inspect_distribution(matches[0], args.project)
                print(f"License bytes and metadata verified: {matches[0].name}")
    except (OSError, ValueError, KeyError, SyntaxError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"License verification failed: {exc}", file=sys.stderr)
        return 1
    print("Canonical license copies match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
