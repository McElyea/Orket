#!/usr/bin/env python3
"""Ensure an SDK release tag matches the SDK package version."""

from __future__ import annotations

import argparse
from pathlib import Path


def _load_sdk_version(repo_root: Path) -> str:
    version_path = (repo_root / "orket_extension_sdk" / "__version__.py").resolve()
    if not version_path.is_file():
        raise FileNotFoundError(f"SDK version file not found: {version_path}")
    namespace: dict[str, object] = {}
    exec(version_path.read_text(encoding="utf-8"), namespace)
    version = str(namespace.get("__version__") or "").strip()
    if not version:
        raise ValueError(f"Missing __version__ value in {version_path}")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate sdk-vX.Y.Z tag against SDK package version.")
    parser.add_argument("--tag", required=True, help="Release tag (for example sdk-v0.1.0).")
    parser.add_argument("--repo-root", default=".", help="Repository root containing orket_extension_sdk.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    sdk_version = _load_sdk_version(repo_root)
    expected_tag = f"sdk-v{sdk_version}"
    actual_tag = str(args.tag or "").strip()
    if actual_tag != expected_tag:
        print(
            "E_SDK_TAG_VERSION_MISMATCH: "
            f"tag='{actual_tag}' expected='{expected_tag}' version='{sdk_version}'"
        )
        return 1

    print(f"OK: tag '{actual_tag}' matches SDK version '{sdk_version}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
