#!/usr/bin/env python3
"""Validate the canonical external-extension release artifact and optional tag."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
import tomllib
from pathlib import Path, PurePosixPath

from orket_extension_sdk.manifest import load_manifest

ERROR_RELEASE_VERSION_MISMATCH = "E_EXT_RELEASE_VERSION_MISMATCH"
ERROR_RELEASE_TAG_VERSION_MISMATCH = "E_EXT_RELEASE_TAG_VERSION_MISMATCH"
ERROR_RELEASE_SDIST_MISSING = "E_EXT_RELEASE_SDIST_MISSING"
ERROR_RELEASE_SDIST_MULTIPLE = "E_EXT_RELEASE_SDIST_MULTIPLE"
ERROR_RELEASE_SDIST_NAME_MISMATCH = "E_EXT_RELEASE_SDIST_NAME_MISMATCH"
ERROR_RELEASE_SDIST_LAYOUT_INCOMPLETE = "E_EXT_RELEASE_SDIST_LAYOUT_INCOMPLETE"
ERROR_RELEASE_PROJECT_METADATA = "E_EXT_RELEASE_PROJECT_METADATA"
ERROR_RELEASE_MANIFEST_LOAD = "E_EXT_RELEASE_MANIFEST_LOAD"

MANIFEST_CANDIDATES = {"extension.yaml", "extension.yml", "extension.json"}
REQUIRED_RELATIVE_PATHS = {
    "pyproject.toml",
    "scripts/install.sh",
    "scripts/install.ps1",
    "scripts/validate.sh",
    "scripts/validate.ps1",
    "scripts/build-release.sh",
    "scripts/build-release.ps1",
    "scripts/verify-release.sh",
    "scripts/verify-release.ps1",
    "scripts/check_release.py",
}
REQUIRED_PREFIXES = ("src/", "tests/")


def _normalize_project_name(name: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[-.]+", "_", str(name or "").strip()).lower()).strip("_")


def _load_project_metadata(project_root: Path) -> tuple[str, str]:
    pyproject_path = project_root / "pyproject.toml"
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Could not read pyproject.toml: {exc}") from exc

    project = payload.get("project") or {}
    name = str(project.get("name") or "").strip()
    version = str(project.get("version") or "").strip()
    if not name or not version:
        raise ValueError("pyproject.toml must declare non-empty project.name and project.version")
    return name, version


def _resolve_single_sdist(dist_dir: Path) -> Path:
    artifacts = sorted(path for path in dist_dir.glob("*.tar.gz") if path.is_file())
    if not artifacts:
        raise ValueError(ERROR_RELEASE_SDIST_MISSING)
    if len(artifacts) != 1:
        raise ValueError(ERROR_RELEASE_SDIST_MULTIPLE)
    return artifacts[0]


def _resolve_manifest_path(project_root: Path) -> Path:
    for candidate in MANIFEST_CANDIDATES:
        path = project_root / candidate
        if path.is_file():
            return path
    raise FileNotFoundError("manifest not found: expected extension.yaml, extension.yml, or extension.json")


def _relative_sdist_paths(artifact_path: Path) -> tuple[str, set[str]]:
    with tarfile.open(artifact_path, "r:gz") as archive:
        names = sorted(
            name
            for name in archive.getnames()
            if name and not name.endswith("/") and not PurePosixPath(name).is_absolute()
        )
    roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    if len(roots) != 1:
        raise ValueError("source distribution must contain exactly one root directory")
    root = next(iter(roots))
    relative_paths = {
        str(PurePosixPath(name).relative_to(root))
        for name in names
        if len(PurePosixPath(name).parts) > 1
    }
    return str(root), relative_paths


def _build_result(
    *,
    ok: bool,
    project_name: str,
    version: str,
    tag: str,
    artifact_path: str,
    error_code: str = "",
    detail: str = "",
) -> dict[str, object]:
    expected_tag = f"v{version}" if version else ""
    errors: list[dict[str, str]] = []
    if not ok:
        errors.append(
            {
                "code": error_code,
                "location": "release",
                "message": detail,
            }
        )
    return {
        "ok": ok,
        "project_name": project_name,
        "version": version,
        "authoritative_artifact_family": "sdist",
        "authoritative_artifact_path": artifact_path,
        "expected_tag": expected_tag,
        "provided_tag": tag,
        "error_count": len(errors),
        "errors": errors,
    }


def check_release(*, project_root: Path, dist_dir: Path, tag: str) -> dict[str, object]:
    try:
        project_name, version = _load_project_metadata(project_root)
    except ValueError as exc:
        return _build_result(
            ok=False,
            project_name="",
            version="",
            tag=tag,
            artifact_path="",
            error_code=ERROR_RELEASE_PROJECT_METADATA,
            detail=str(exc),
        )

    try:
        manifest = load_manifest(_resolve_manifest_path(project_root))
    except Exception as exc:
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path="",
            error_code=ERROR_RELEASE_MANIFEST_LOAD,
            detail=str(exc),
        )

    if version != manifest.extension_version:
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path="",
            error_code=ERROR_RELEASE_VERSION_MISMATCH,
            detail=f"project.version='{version}' manifest.extension_version='{manifest.extension_version}'",
        )

    if tag and tag != f"v{version}":
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path="",
            error_code=ERROR_RELEASE_TAG_VERSION_MISMATCH,
            detail=f"tag='{tag}' expected='v{version}'",
        )

    try:
        artifact_path = _resolve_single_sdist(dist_dir)
    except ValueError as exc:
        code = str(exc)
        detail = f"dist_dir='{dist_dir}'"
        if code not in {ERROR_RELEASE_SDIST_MISSING, ERROR_RELEASE_SDIST_MULTIPLE}:
            code = ERROR_RELEASE_SDIST_MISSING
            detail = str(exc)
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path="",
            error_code=code,
            detail=detail,
        )

    normalized_name = _normalize_project_name(project_name)
    expected_prefix = f"{normalized_name}-{version}"
    if artifact_path.name != f"{expected_prefix}.tar.gz":
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path=str(artifact_path),
            error_code=ERROR_RELEASE_SDIST_NAME_MISMATCH,
            detail=f"artifact='{artifact_path.name}' expected='{expected_prefix}.tar.gz'",
        )

    try:
        root_dir, relative_paths = _relative_sdist_paths(artifact_path)
    except ValueError as exc:
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path=str(artifact_path),
            error_code=ERROR_RELEASE_SDIST_LAYOUT_INCOMPLETE,
            detail=str(exc),
        )

    if root_dir != expected_prefix:
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path=str(artifact_path),
            error_code=ERROR_RELEASE_SDIST_NAME_MISMATCH,
            detail=f"root_dir='{root_dir}' expected='{expected_prefix}'",
        )

    manifest_rel = next((name for name in MANIFEST_CANDIDATES if name in relative_paths), "")
    if not manifest_rel:
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path=str(artifact_path),
            error_code=ERROR_RELEASE_SDIST_LAYOUT_INCOMPLETE,
            detail="source distribution is missing a root-level extension manifest",
        )

    missing_paths = sorted(path for path in REQUIRED_RELATIVE_PATHS if path not in relative_paths)
    missing_prefixes = sorted(prefix for prefix in REQUIRED_PREFIXES if not any(path.startswith(prefix) for path in relative_paths))
    if missing_paths or missing_prefixes:
        detail_parts: list[str] = []
        if missing_paths:
            detail_parts.append(f"missing_paths={','.join(missing_paths)}")
        if missing_prefixes:
            detail_parts.append(f"missing_prefixes={','.join(missing_prefixes)}")
        return _build_result(
            ok=False,
            project_name=project_name,
            version=version,
            tag=tag,
            artifact_path=str(artifact_path),
            error_code=ERROR_RELEASE_SDIST_LAYOUT_INCOMPLETE,
            detail="; ".join(detail_parts),
        )

    return _build_result(
        ok=True,
        project_name=project_name,
        version=version,
        tag=tag,
        artifact_path=str(artifact_path),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the canonical external-extension release artifact.")
    parser.add_argument("--project-root", default=".", help="Extension project root containing pyproject.toml.")
    parser.add_argument("--dist-dir", default="dist", help="Distribution directory containing the source distribution.")
    parser.add_argument("--tag", default="", help="Optional release tag to validate against the package version.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    dist_dir = Path(args.dist_dir).resolve()
    result = check_release(project_root=project_root, dist_dir=dist_dir, tag=str(args.tag or "").strip())
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("OK" if result["ok"] else "FAIL")
        if result["errors"]:
            print(result["errors"][0]["message"])
    return 0 if bool(result["ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
