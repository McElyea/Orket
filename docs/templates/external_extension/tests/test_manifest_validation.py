from __future__ import annotations

import tomllib
from pathlib import Path

from orket_extension_sdk.manifest import load_manifest
from orket_extension_sdk.validate import validate_extension

TEMPLATE_ROOT = Path(__file__).resolve().parents[1]

def test_template_manifest_validates() -> None:
    """Layer: integration. Verifies the scaffolded template passes strict validation from its own repository root."""
    result = validate_extension(TEMPLATE_ROOT, strict=True)
    assert result["ok"] is True
    assert result["error_count"] == 0


def test_template_package_metadata_matches_manifest() -> None:
    """Layer: contract. Verifies the template package version and manifest version stay aligned."""
    pyproject = tomllib.loads((TEMPLATE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = load_manifest(TEMPLATE_ROOT / "extension.yaml")

    assert pyproject["project"]["version"] == manifest.extension_version
    assert manifest.workloads[0].entrypoint.startswith("companion_extension.")


def test_template_publish_surface_files_exist() -> None:
    """Layer: contract. Verifies the template carries the canonical publish-surface files."""
    required = [
        "MANIFEST.in",
        ".gitea/workflows/release.yml",
        "scripts/build-release.sh",
        "scripts/build-release.ps1",
        "scripts/verify-release.sh",
        "scripts/verify-release.ps1",
        "scripts/check_release.py",
    ]
    for relative in required:
        assert (TEMPLATE_ROOT / relative).is_file(), relative
