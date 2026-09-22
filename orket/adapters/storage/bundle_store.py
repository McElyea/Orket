"""Owned bundle filesystem operations; all reads and writes run in retained workers."""
from __future__ import annotations

import hashlib
import os
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path, PurePosixPath

from orket.adapters.execution.owned_io import run_owned_thread

MANIFEST_NAMES = ("orket.yaml", "orket.yml", "orket.json")


side_effecting = True


@dataclass(frozen=True)
class BundleManifestSource:
    path: Path | None
    root: Path
    content: bytes | None


@dataclass(frozen=True)
class BundleArchiveSource:
    names: tuple[str, ...]
    manifest_name: str | None
    manifest_bytes: bytes | None


def safe_archive_name(name: str) -> bool:
    normalized = str(name or "").replace("\\", "/")
    if not normalized or normalized.startswith(("/", "./")):
        return False
    pure = PurePosixPath(normalized)
    return not pure.is_absolute() and ".." not in pure.parts and normalized == str(pure)


class BundleSourceChangedError(ValueError):
    """The manifest changed after application validation admitted the pack."""


class BundleStore:
    # Reads observe external state; packing creates/replaces an archive.
    side_effecting = True

    async def read_manifest(self, target: Path) -> BundleManifestSource:
        return await run_owned_thread(lambda: _read_manifest(target), label="bundle-manifest-read")

    async def existing_references(self, root: Path, names: tuple[str, ...]) -> frozenset[str]:
        return await run_owned_thread(lambda: _existing_references(root, names), label="bundle-reference-read")

    async def target_kind(self, target: Path) -> str:
        def observe() -> str:
            return "file" if target.is_file() else "directory" if target.is_dir() else "missing"
        return await run_owned_thread(observe, label="bundle-target-read")

    async def read_archive(self, target: Path) -> BundleArchiveSource:
        return await run_owned_thread(lambda: _read_archive(target), label="bundle-archive-read")

    async def pack(self, source: BundleManifestSource, destination: Path,
                   required_names: tuple[str, ...]) -> tuple[Path, int]:
        return await run_owned_thread(lambda: _pack(source, destination, required_names), label="bundle-archive-write")

    async def engine_version(self) -> str:
        return await run_owned_thread(_engine_version, label="bundle-engine-version")


def _read_manifest(target: Path) -> BundleManifestSource:
    if target.is_file():
        path, root = target, target.parent
    else:
        root = target
        path = next((target / name for name in MANIFEST_NAMES if (target / name).is_file()), None)
    return BundleManifestSource(path, root, path.read_bytes() if path else None)


def _engine_version() -> str:
    try:
        return metadata.version("orket")
    except metadata.PackageNotFoundError:
        project = Path(__file__).resolve().parents[3] / "pyproject.toml"
        try:
            payload = tomllib.loads(project.read_text(encoding="utf-8"))
            return str((payload.get("project") or {}).get("version") or "").strip() or "0.0.0"
        except (OSError, tomllib.TOMLDecodeError, AttributeError):
            return "0.0.0"


def _existing_references(root: Path, names: tuple[str, ...]) -> frozenset[str]:
    resolved_root = root.resolve()
    return frozenset(name for name in names
                     if (resolved_root / name).resolve().is_relative_to(resolved_root)
                     and (resolved_root / name).is_file())


def _read_archive(target: Path) -> BundleArchiveSource:
    with zipfile.ZipFile(target, "r") as archive:
        names = tuple(sorted(name for name in archive.namelist() if not name.endswith("/")))
        name = next((name for name in MANIFEST_NAMES if name in names), None)
        content = archive.read(name) if name else None
    return BundleArchiveSource(names, name, content)


def _source_entries(source: BundleManifestSource, destination: Path) -> list[tuple[Path, str]]:
    root = source.root.resolve()
    entries = []
    for path in sorted(source.root.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved == destination:
            continue
        if not resolved.is_relative_to(root):
            raise ValueError(f"Bundle source escapes its root: {path}")
        name = path.relative_to(source.root).as_posix().replace("\\", "/")
        if not safe_archive_name(name):
            raise ValueError(f"Unsafe archive path derived from source: {name}")
        entries.append((resolved, name))
    if len(entries) != len({name for _, name in entries}):
        raise ValueError("Bundle source paths collide after archive path normalization")
    return entries


def _write_archive(path: Path, entries: list[tuple[Path, str]]) -> dict[str, str]:
    hashes = {}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, name in sorted(entries, key=lambda item: item[1]):
            data = source.read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, data)
    return hashes


def _verify_archive(path: Path, hashes: dict[str, str]) -> None:
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != sorted(hashes):
            raise OSError("Packed bundle entries differ from admitted source entries")
        for name, expected in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise OSError(f"Packed bundle content mismatch: {name}")


def _pack(source: BundleManifestSource, destination: Path, required_names: tuple[str, ...]) -> tuple[Path, int]:
    assert source.path is not None and source.content is not None
    destination = destination.resolve()
    entries = _source_entries(source, destination)
    if not set(required_names).issubset(name for _, name in entries):
        raise BundleSourceChangedError("Required bundle files disappeared after validation")
    if source.path.resolve() == destination:
        raise ValueError("Bundle destination must not replace its source manifest")
    if source.path.read_bytes() != source.content:
        raise BundleSourceChangedError("Manifest changed after bundle validation")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".orket-bundle-", suffix=".tmp", dir=destination.parent)
    temporary = Path(name)
    try:
        os.close(fd)
        hashes = _write_archive(temporary, entries)
        manifest_name = source.path.relative_to(source.root).as_posix().replace("\\", "/")
        with zipfile.ZipFile(temporary) as archive:
            if archive.read(manifest_name) != source.content:
                raise BundleSourceChangedError("Manifest changed while packing bundle")
        _verify_archive(temporary, hashes)
        temporary.replace(destination)
        _verify_archive(destination, hashes)
    finally:
        temporary.unlink(missing_ok=True)
    return destination, len(entries)
