from __future__ import annotations

from pathlib import Path

import pytest

from orket_extension_sdk.manifest import load_manifest


def test_load_manifest_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "extension.json"
    manifest_path.write_text(
        '{"manifest_version":"v0","extension_id":"demo","extension_version":"1.0.0","workloads":[{"workload_id":"w1","entrypoint":"pkg.mod:run","required_capabilities":["fs.read"]}]}'
    )

    manifest = load_manifest(manifest_path)

    assert manifest.extension_id == "demo"
    assert manifest.workloads[0].workload_id == "w1"


def test_load_manifest_yaml(tmp_path: Path) -> None:
    manifest_path = tmp_path / "extension.yaml"
    manifest_path.write_text(
        """
manifest_version: v0
extension_id: demo
extension_version: 1.0.0
workloads:
  - workload_id: w1
    entrypoint: pkg.mod:run
    required_capabilities:
      - fs.read
""".strip()
    )

    manifest = load_manifest(manifest_path)

    assert manifest.extension_version == "1.0.0"


def test_load_manifest_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="E_SDK_MANIFEST_NOT_FOUND"):
        load_manifest(tmp_path / "missing.json")


def test_load_manifest_schema_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "extension.json"
    manifest_path.write_text('{"manifest_version":"v0"}')

    with pytest.raises(ValueError, match="E_SDK_MANIFEST_SCHEMA"):
        load_manifest(manifest_path)
