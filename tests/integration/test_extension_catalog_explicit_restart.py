"""Integration: explicit generic contract refs survive Git install and restart."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.extension_catalog_roundtrip_profiles import EXPLICIT_PROFILE
from tests.integration.test_extension_catalog_roundtrip_restart import (
    _exercise_roundtrip,
    _git,
    _prepare_source,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _prepare_explicit_source(fixture_root: Path) -> tuple[Path, str]:
    source, _initial_commit = _prepare_source(fixture_root)
    original_module = source / "sdk_json_extension.py"
    original_module.replace(source / EXPLICIT_PROFILE.module_filename)
    manifest_path = source / "extension.json"
    manifest = json.loads(manifest_path.read_bytes().decode("utf-8"))
    manifest["extension_id"] = EXPLICIT_PROFILE.extension_id
    manifest["extension_version"] = EXPLICIT_PROFILE.extension_version
    workload = manifest["workloads"][0]
    workload.update(
        workload_id=EXPLICIT_PROFILE.workload_id,
        entrypoint=EXPLICIT_PROFILE.entrypoint,
        input_contract=EXPLICIT_PROFILE.input_contract,
        output_contract=EXPLICIT_PROFILE.output_contract,
    )
    manifest_path.write_bytes(json.dumps(manifest, indent=2, ensure_ascii=True).encode("ascii"))
    _git(source, "add", "-A")
    _git(
        source, "-c", "user.email=test@example.com", "-c", "user.name=Test",
        "commit", "-m", "explicit generic contract references",
    )
    return source, _git(source, "rev-parse", "HEAD")


# Layer: integration. Distinct real Git source and owned children prove explicit references across restart.
async def test_generic_sdk_explicit_contract_refs_survive_git_install_and_restart(
    tmp_path_factory: Any, record_property: Any,
) -> None:
    observation = await _exercise_roundtrip(
        tmp_path_factory=tmp_path_factory, record_property=record_property, profile=EXPLICIT_PROFILE,
        source_factory=_prepare_explicit_source, fixture_prefix="sdkexplicitroundtrip",
        cancellation_event="extension_catalog_explicit_cancelled",
        property_name="extension_catalog_explicit_restart_observation",
        label_prefix="extension-catalog-explicit",
    )
    install, restart = observation["install_child"], observation["restart_child"]
    records = [
        install["parser_record"], install["installed_record"],
        install["same_manager_records"][0], restart["records"][0],
    ]
    assert all(record == records[0] for record in records[1:])
    physical_entry = install["physical"]["catalog"]["payload"]["extensions"][0]["manifest_entries"][0]
    assert physical_entry["input_contract"] == EXPLICIT_PROFILE.input_contract
    assert physical_entry["output_contract"] == EXPLICIT_PROFILE.output_contract
