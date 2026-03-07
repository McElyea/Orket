from __future__ import annotations

from pathlib import Path

import pytest

from orket.runtime.contract_bootstrap import load_runtime_contract_snapshots


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Layer: unit
def test_load_runtime_contract_snapshots_parses_valid_contract_sources(tmp_path: Path) -> None:
    _write(
        tmp_path / "core" / "artifacts" / "schema_registry.yaml",
        """
registry_version: "1.0"
artifacts:
  run.json: "1.0"
  tool_call.json: "1.0"
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "tool_registry.yaml",
        """
tool_registry_version: "1.2.0"
tools:
  - tool_name: workspace.search
    ring: core
    tool_contract_version: "1.0.0"
    determinism_class: workspace
    capability_profile: workspace
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "compatibility_map_schema.yaml",
        """
schema_version: "1.0"
compatibility_map_version: "1.0"
required_fields:
  - mapping_version
  - mapped_core_tools
  - schema_compatibility_range
  - determinism_class
allowed_determinism_classes:
  - pure
  - workspace
  - external
allowed_target_ring: core
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "compatibility_map.yaml",
        """
schema_version: "1.0"
mappings:
  openclaw.file_search:
    mapping_version: 1
    mapped_core_tools:
      - workspace.search
    schema_compatibility_range: ">=1.0.0 <2.0.0"
    determinism_class: workspace
""".strip()
        + "\n",
    )

    snapshots = load_runtime_contract_snapshots(
        artifact_schema_registry_path=tmp_path / "core" / "artifacts" / "schema_registry.yaml",
        compatibility_map_path=tmp_path / "core" / "tools" / "compatibility_map.yaml",
        compatibility_map_schema_path=tmp_path / "core" / "tools" / "compatibility_map_schema.yaml",
        tool_registry_path=tmp_path / "core" / "tools" / "tool_registry.yaml",
    )

    assert snapshots.artifact_schema_snapshot["artifact_schema_registry_version"] == "1.0"
    assert snapshots.tool_registry_snapshot["tool_registry_version"] == "1.2.0"
    assert snapshots.tool_contract_snapshot["tool_contracts"][0]["tool_name"] == "workspace.search"
    assert snapshots.compatibility_map_schema_snapshot["mapping_count"] == 1
    assert snapshots.compatibility_map_snapshot["mapping_count"] == 1
    assert snapshots.compatibility_map_snapshot["mappings"]["openclaw.file_search"]["mapping_version"] == 1
    assert len(str(snapshots.tool_registry_snapshot["snapshot_hash"])) == 64


# Layer: contract
def test_load_runtime_contract_snapshots_fails_closed_on_invalid_artifact_schema_version(tmp_path: Path) -> None:
    _write(
        tmp_path / "core" / "artifacts" / "schema_registry.yaml",
        """
registry_version: "v1"
artifacts:
  run.json: "1.0"
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "tool_registry.yaml",
        """
tool_registry_version: "1.2.0"
tools:
  - tool_name: workspace.search
    ring: core
    tool_contract_version: "1.0.0"
    determinism_class: workspace
    capability_profile: workspace
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "compatibility_map_schema.yaml",
        """
schema_version: "1.0"
compatibility_map_version: "1.0"
required_fields:
  - mapping_version
  - mapped_core_tools
  - schema_compatibility_range
  - determinism_class
allowed_determinism_classes:
  - pure
  - workspace
allowed_target_ring: core
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "compatibility_map.yaml",
        """
schema_version: "1.0"
mappings: {}
""".strip()
        + "\n",
    )

    with pytest.raises(ValueError, match="artifact registry_version"):
        _ = load_runtime_contract_snapshots(
            artifact_schema_registry_path=tmp_path / "core" / "artifacts" / "schema_registry.yaml",
            compatibility_map_path=tmp_path / "core" / "tools" / "compatibility_map.yaml",
            compatibility_map_schema_path=tmp_path / "core" / "tools" / "compatibility_map_schema.yaml",
            tool_registry_path=tmp_path / "core" / "tools" / "tool_registry.yaml",
        )


# Layer: contract
def test_load_runtime_contract_snapshots_rejects_non_core_compatibility_mapping_targets(tmp_path: Path) -> None:
    _write(
        tmp_path / "core" / "artifacts" / "schema_registry.yaml",
        """
registry_version: "1.0"
artifacts:
  run.json: "1.0"
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "tool_registry.yaml",
        """
tool_registry_version: "1.2.0"
tools:
  - tool_name: compat.file_edit
    ring: compatibility
    tool_contract_version: "1.0.0"
    determinism_class: workspace
    capability_profile: workspace
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "compatibility_map_schema.yaml",
        """
schema_version: "1.0"
compatibility_map_version: "1.0"
required_fields:
  - mapping_version
  - mapped_core_tools
  - schema_compatibility_range
  - determinism_class
allowed_determinism_classes:
  - pure
  - workspace
  - external
allowed_target_ring: core
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "compatibility_map.yaml",
        """
schema_version: "1.0"
mappings:
  openclaw.file_edit:
    mapping_version: 1
    mapped_core_tools:
      - compat.file_edit
    schema_compatibility_range: ">=1.0.0 <2.0.0"
    determinism_class: workspace
""".strip()
        + "\n",
    )

    with pytest.raises(ValueError, match="non-core tool"):
        _ = load_runtime_contract_snapshots(
            artifact_schema_registry_path=tmp_path / "core" / "artifacts" / "schema_registry.yaml",
            compatibility_map_path=tmp_path / "core" / "tools" / "compatibility_map.yaml",
            compatibility_map_schema_path=tmp_path / "core" / "tools" / "compatibility_map_schema.yaml",
            tool_registry_path=tmp_path / "core" / "tools" / "tool_registry.yaml",
        )


# Layer: contract
def test_load_runtime_contract_snapshots_rejects_compat_mapping_determinism_elevation(tmp_path: Path) -> None:
    _write(
        tmp_path / "core" / "artifacts" / "schema_registry.yaml",
        """
registry_version: "1.0"
artifacts:
  run.json: "1.0"
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "tool_registry.yaml",
        """
tool_registry_version: "1.2.0"
tools:
  - tool_name: workspace.search
    ring: core
    tool_contract_version: "1.0.0"
    determinism_class: workspace
    capability_profile: workspace
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "compatibility_map_schema.yaml",
        """
schema_version: "1.0"
compatibility_map_version: "1.0"
required_fields:
  - mapping_version
  - mapped_core_tools
  - schema_compatibility_range
  - determinism_class
allowed_determinism_classes:
  - pure
  - workspace
  - external
allowed_target_ring: core
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "core" / "tools" / "compatibility_map.yaml",
        """
schema_version: "1.0"
mappings:
  openclaw.file_search:
    mapping_version: 1
    mapped_core_tools:
      - workspace.search
    schema_compatibility_range: ">=1.0.0 <2.0.0"
    determinism_class: pure
""".strip()
        + "\n",
    )

    with pytest.raises(ValueError, match="least mapped determinism"):
        _ = load_runtime_contract_snapshots(
            artifact_schema_registry_path=tmp_path / "core" / "artifacts" / "schema_registry.yaml",
            compatibility_map_path=tmp_path / "core" / "tools" / "compatibility_map.yaml",
            compatibility_map_schema_path=tmp_path / "core" / "tools" / "compatibility_map_schema.yaml",
            tool_registry_path=tmp_path / "core" / "tools" / "tool_registry.yaml",
        )
