"""Native contract admission over copied canonical assets, never modified defaults."""
import asyncio
import json
from functools import partial

import pytest
import pytest_asyncio
import yaml

from orket.adapters.execution.owned_io import run_owned_thread
from orket.runtime.config import contract_assets
from orket.runtime.registry.contract_bootstrap import load_runtime_contract_snapshots, write_runtime_contract_snapshots

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def sources(tmp_path):
    assets = {
        "artifact_schema_registry_path": contract_assets.DEFAULT_ARTIFACT_SCHEMA_REGISTRY_PATH,
        "tool_registry_path": contract_assets.DEFAULT_TOOL_REGISTRY_PATH,
        "compatibility_map_schema_path": contract_assets.DEFAULT_COMPATIBILITY_MAP_SCHEMA_PATH,
        "compatibility_map_path": contract_assets.DEFAULT_COMPATIBILITY_MAP_PATH,
    }
    paths, payloads = {}, {}
    for key, asset in assets.items():
        raw = await asyncio.to_thread(asset.read_bytes)
        paths[key] = tmp_path / asset.name
        await asyncio.to_thread(paths[key].write_bytes, raw)
        payloads[key] = yaml.safe_load(raw)
    return paths, payloads


async def _load(paths):
    return await run_owned_thread(partial(load_runtime_contract_snapshots, **paths), label="bootstrap-admission")


@pytest.mark.parametrize("source,keys,value,error", [
    ("artifact_schema_registry", ("registry_version",), "", "artifact registry_version is required"),
    ("artifact_schema_registry", ("artifacts",), {}, "artifacts must be a non-empty mapping"),
    ("artifact_schema_registry", ("artifacts",), {"": "1.0"}, "empty artifact name"),
    ("tool_registry", ("tools",), [], "tools must be a non-empty list"),
    ("tool_registry", ("tools",), [None], "entry 0 must be an object"),
    ("tool_registry", ("tools", 0, "tool_name"), "", "empty tool_name"),
    ("tool_registry", ("tools", 0, "ring"), "unknown", "unsupported ring"),
    ("tool_registry", ("tools", 0, "determinism_class"), "unknown", "unsupported determinism_class"),
    ("compatibility_map_schema", ("allowed_determinism_classes",), ["unknown"], "unsupported determinism class"),
    ("compatibility_map_schema", ("allowed_target_ring",), "unknown", "unsupported allowed_target_ring"),
    ("compatibility_map_schema", ("required_fields",), [], "required_fields must be a non-empty list"),
    ("compatibility_map_schema", ("required_fields",), [""], r"required_fields\[0\] must be a non-empty string"),
    ("compatibility_map", ("schema_version",), "2.0", "does not match expected"),
    ("compatibility_map", ("mappings",), [], "mappings must be a mapping"),
    ("compatibility_map", ("mappings",), {"": {}}, "empty compat_tool_name"),
    ("compatibility_map", ("mappings",), {"fixture": []}, "must be an object"),
    ("compatibility_map", ("mappings",), {"fixture": {}}, "missing fields"),
    ("compatibility_map", ("mappings", "openclaw.file_edit", "mapping_version"), 0, "invalid mapping_version"),
    ("compatibility_map", ("mappings", "openclaw.file_edit", "mapped_core_tools"), ["unknown"], "references unknown tool"),
    ("tool_registry", ("tools", 0, "ring"), "compatibility", "maps to non-core tool"),
    ("compatibility_map", ("mappings", "openclaw.file_edit", "determinism_class"), "unknown", "unsupported determinism_class"),
    ("compatibility_map", ("mappings", "openclaw.file_edit", "schema_compatibility_range"), " ", "requires schema_compatibility_range"),
])
async def test_invalid_native_contract_input_refuses_without_repair(sources, source, keys, value, error):
    paths, payloads = sources
    key = source + "_path"
    target = payloads[key]
    for part in keys[:-1]:
        target = target[part]
    target[keys[-1]] = value
    await asyncio.to_thread(paths[key].write_text, yaml.safe_dump(payloads[key]), encoding="utf-8")
    before = {name: await asyncio.to_thread(path.read_bytes) for name, path in paths.items()}
    with pytest.raises(ValueError, match=error):
        await _load(paths)
    assert {name: await asyncio.to_thread(path.read_bytes) for name, path in paths.items()} == before


@pytest.mark.parametrize("raw,error", [("[invalid", "runtime_contract_parse:"), ("[]", "root payload must be a mapping")])
async def test_yaml_parse_and_root_shape_failures_keep_original_bytes(sources, raw, error):
    paths, _ = sources
    path = paths["artifact_schema_registry_path"]
    await asyncio.to_thread(path.write_text, raw, encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        await _load(paths)
    assert await asyncio.to_thread(path.read_text, encoding="utf-8") == raw


async def test_missing_native_source_and_duplicate_tool_identity_are_explicit(sources, tmp_path):
    paths, payloads = sources
    with pytest.raises(ValueError, match="runtime_contract_load:") as failed:
        await _load({**paths, "artifact_schema_registry_path": tmp_path / "missing.yaml"})
    assert isinstance(failed.value.__cause__, OSError)
    tools = payloads["tool_registry_path"]["tools"]
    tools.append(dict(tools[0]))
    await asyncio.to_thread(paths["tool_registry_path"].write_text,
                            yaml.safe_dump(payloads["tool_registry_path"]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate tool_name"):
        await _load(paths)


async def test_duplicate_lists_preserve_canonical_snapshot_hashes_and_native_publication(sources, tmp_path):
    paths, payloads = sources
    baseline = await _load(paths)
    schema = payloads["compatibility_map_schema_path"]
    schema["required_fields"].append(schema["required_fields"][0])
    mapped = payloads["compatibility_map_path"]["mappings"]["openclaw.file_edit"]["mapped_core_tools"]
    mapped.append(mapped[0])
    for name in ("compatibility_map_schema_path", "compatibility_map_path"):
        await asyncio.to_thread(paths[name].write_text, yaml.safe_dump(payloads[name]), encoding="utf-8")
    snapshots = await _load(paths)
    assert snapshots.as_ledger_artifacts() == baseline.as_ledger_artifacts()
    destination = tmp_path / "snapshots"
    outputs = await run_owned_thread(partial(write_runtime_contract_snapshots,
        snapshots=snapshots, output_dir=destination), label="bootstrap-fixture-publication")
    expected = snapshots.as_ledger_artifacts()
    assert set(outputs) == {key + "_path" for key in expected}
    for key, payload in expected.items():
        path = destination / (key + ".json")
        assert outputs[key + "_path"] == str(path)
        assert json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8")) == payload
