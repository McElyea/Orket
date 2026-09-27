"""Generic SDK contract references survive the public physical catalog route."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.extensions.catalog import ExtensionCatalog
from orket.extensions.manifest_parser import ManifestParser

pytestmark = pytest.mark.asyncio
INPUT_CONTRACT = "contracts/generic-request.v1.json"
OUTPUT_CONTRACT = "contracts/generic-result.v1.json"
MANIFEST = {
    "manifest_version": "v0",
    "extension_id": "generic.explicit.contracts",
    "extension_version": "1.2.3",
    "workloads": [{
        "workload_id": "generic-explicit-v1",
        "entrypoint": "generic_explicit_workload:run",
        "required_capabilities": ["workspace.root"],
        "workload_kind": "generic",
        "input_contract": INPUT_CONTRACT,
        "output_contract": OUTPUT_CONTRACT,
    }],
}


def _exercise_public_roundtrip(
    root: Path, references: tuple[str | None, str | None] | None = None,
) -> dict[str, Any]:
    source = root / "source"
    source.mkdir()
    manifest_path = source / "extension.json"
    payload = MANIFEST
    if references is not None:
        workload = MANIFEST["workloads"][0] | dict(zip(("input_contract", "output_contract"), references, strict=True))
        payload = MANIFEST | {"workloads": [workload]}
    manifest_raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    manifest_path.write_bytes(manifest_raw)
    manifest_sha256 = hashlib.sha256(manifest_raw).hexdigest()

    parser = ManifestParser()
    loaded = parser.load_manifest(source)
    record = parser.record_from_manifest(
        loaded.payload,
        source="fixture://generic-explicit-contracts",
        path=source,
        contract_style=loaded.contract_style,
        manifest_path=loaded.manifest_path,
        manifest_digest_sha256=manifest_sha256,
    )
    catalog_path = root / "extensions_catalog.json"
    catalog = ExtensionCatalog(catalog_path)
    catalog.publish_record(record)

    catalog_raw = catalog_path.read_bytes()
    catalog_payload = json.loads(catalog_raw.decode("ascii"))
    listed = catalog.list_extensions()
    assert len(record.manifest_entries) == len(listed) == 1
    assert len(listed[0].manifest_entries) == 1
    physical_extension = catalog_payload["extensions"][0]
    return {
        "manifest_sha256": manifest_sha256,
        "record_manifest_sha256": record.manifest_digest_sha256,
        "listed_manifest_sha256": listed[0].manifest_digest_sha256,
        "catalog_sha256": hashlib.sha256(catalog_raw).hexdigest(),
        "catalog_payload": catalog_payload,
        "parser_entry": asdict(record.manifest_entries[0]),
        "physical_entry": physical_extension["manifest_entries"][0],
        "physical_manifest_sha256": physical_extension["manifest_digest_sha256"],
        "reader_entry": asdict(listed[0].manifest_entries[0]),
    }


@pytest.mark.integration
# Layer: integration. Public SDK parsing, verified catalog bytes, and public reading are real.
async def test_generic_explicit_contract_refs_survive_physical_catalog_roundtrip(
    tmp_path: Path,
    record_property: Any,
) -> None:
    observation = await run_owned_thread(
        partial(_exercise_public_roundtrip, tmp_path),
        label="extension-catalog-explicit-reference-roundtrip",
    )
    record_property(
        "extension_catalog_explicit_reference_observation",
        json.dumps(observation, sort_keys=True),
    )

    expected_entry = {
        "workload_id": "generic-explicit-v1",
        "workload_version": "1.2.3",
        "entrypoint": "generic_explicit_workload:run",
        "required_capabilities": ("workspace.root",),
        "contract_style": "sdk_v0",
        "workload_kind": "generic",
        "input_contract": INPUT_CONTRACT,
        "output_contract": OUTPUT_CONTRACT,
        "agent_declaration": {},
    }
    assert observation["parser_entry"] == expected_entry
    assert observation["record_manifest_sha256"] == observation["manifest_sha256"]
    assert observation["physical_manifest_sha256"] == observation["manifest_sha256"]
    assert observation["listed_manifest_sha256"] == observation["manifest_sha256"]
    expected_refs = {"input_contract": INPUT_CONTRACT, "output_contract": OUTPUT_CONTRACT}
    assert {key: observation["physical_entry"].get(key) for key in expected_refs} == expected_refs
    assert observation["reader_entry"] == observation["parser_entry"]


@pytest.mark.integration
# Layer: integration. Each public SDK parse crosses the physical writer and public reader.
@pytest.mark.parametrize(
    ("references", "expected_refs"),
    [
        pytest.param((INPUT_CONTRACT, None), {"input_contract": INPUT_CONTRACT}, id="input-only"),
        pytest.param((None, OUTPUT_CONTRACT), {"output_contract": OUTPUT_CONTRACT}, id="output-only"),
        pytest.param((None, None), {}, id="null-pair"),
        pytest.param(("", ""), {}, id="empty-pair"),
        pytest.param((" \t", "\n "), {}, id="whitespace-pair"),
        pytest.param(("None", "None"), {"input_contract": "None", "output_contract": "None"},
                     id="literal-none-pair"),
        pytest.param((" " + INPUT_CONTRACT + " ", " " + OUTPUT_CONTRACT + " "),
                     {"input_contract": INPUT_CONTRACT, "output_contract": OUTPUT_CONTRACT},
                     id="trimmed-pair"),
    ],
)
async def test_generic_optional_contract_refs_keep_exact_compact_physical_shape(
    tmp_path: Path,
    references: tuple[str | None, str | None],
    expected_refs: dict[str, str],
) -> None:
    observation = await run_owned_thread(
        partial(_exercise_public_roundtrip, tmp_path, references),
        label="extension-catalog-optional-reference-roundtrip",
    )
    expected_row = {
        "workload_id": "generic-explicit-v1",
        "workload_version": "1.2.3",
        "entrypoint": "generic_explicit_workload:run",
        "required_capabilities": ["workspace.root"],
        "contract_style": "sdk_v0",
        **expected_refs,
    }
    assert observation["physical_entry"] == expected_row
    assert observation["reader_entry"] == observation["parser_entry"]
    assert observation["record_manifest_sha256"] == observation["physical_manifest_sha256"]
    assert observation["listed_manifest_sha256"] == observation["manifest_sha256"]
