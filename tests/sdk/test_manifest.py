from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from orket_extension_sdk.manifest import WorkloadManifest, load_manifest


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
allowed_stdlib_modules:
  - json
  - pathlib
workloads:
  - workload_id: w1
    entrypoint: pkg.mod:run
    required_capabilities:
      - fs.read
config_sections:
  - appearance
""".strip()
    )

    manifest = load_manifest(manifest_path)

    assert manifest.extension_version == "1.0.0"
    assert manifest.config_sections == ["appearance"]
    assert manifest.allowed_stdlib_modules == ["json", "pathlib"]


def test_load_manifest_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="E_SDK_MANIFEST_NOT_FOUND"):
        load_manifest(tmp_path / "missing.json")


def test_load_manifest_schema_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "extension.json"
    manifest_path.write_text('{"manifest_version":"v0"}')

    with pytest.raises(ValueError, match="E_SDK_MANIFEST_SCHEMA"):
        load_manifest(manifest_path)


def test_load_manifest_rejects_unsupported_manifest_version(tmp_path: Path) -> None:
    manifest_path = tmp_path / "extension.yaml"
    manifest_path.write_text(
        """
manifest_version: v1
extension_id: demo
extension_version: 1.0.0
workloads:
  - workload_id: w1
    entrypoint: pkg.mod:run
    required_capabilities: []
""".strip()
    )

    with pytest.raises(ValueError, match="E_SDK_MANIFEST_VERSION_UNSUPPORTED"):
        load_manifest(manifest_path)

# Layer: contract
def test_agent_manifest_requires_explicit_contracts_capability_and_features() -> None:
    """Layer: contract. Matching agent declarations are additive within manifest v0."""
    workload = WorkloadManifest.model_validate(
        {
            "workload_id": "governed-agent-loop",
            "entrypoint": "demo.agent:run",
            "required_capabilities": ["agent.iteration.v1"],
            "workload_kind": "agent",
            "input_contract": "agent_iteration_request.v1",
            "output_contract": "agent_iteration_result.v1",
            "agent": {
                "contract_version": "governed_agent_loop.v1",
                "required_host_features": ["governed_agent_loop.v1", "agent_stdio_ipc.v1", "agent_model_use_receipt.v2"],
                "model_profiles": [{"role": "planner", "profile_ref": "local.default"}],
                "resource_requirements": {"max_model_calls_per_iteration": 2},
            },
        }
    )

    assert workload.workload_kind == "agent"
    assert workload.agent is not None
    assert workload.agent.contract_version == "governed_agent_loop.v1"

@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ({"required_capabilities": []}, "E_SDK_AGENT_CAPABILITY_REQUIRED"),
        ({"input_contract": "generic.v0"}, "E_SDK_AGENT_INPUT_CONTRACT_UNSUPPORTED"),
        (
            {"agent": {"required_host_features": ["governed_agent_loop.v1"]}},
            "E_SDK_AGENT_HOST_FEATURE_REQUIRED",
        ),
        ({"agent": {"misspelled_recovery_policy": "continue"}}, "extra_forbidden"),
    ],
)
# Layer: contract
def test_agent_manifest_fails_closed_on_incomplete_or_unknown_contract(
    mutation: dict[str, object], error_code: str
) -> None:
    """Layer: contract. Agent-only declarations do not inherit v0's permissive unknown-field behavior."""
    payload: dict[str, object] = {
        "workload_id": "governed-agent-loop",
        "entrypoint": "demo.agent:run",
        "required_capabilities": ["agent.iteration.v1"],
        "workload_kind": "agent",
        "input_contract": "agent_iteration_request.v1",
        "output_contract": "agent_iteration_result.v1",
        "agent": {
            "contract_version": "governed_agent_loop.v1",
            "required_host_features": ["governed_agent_loop.v1", "agent_stdio_ipc.v1", "agent_model_use_receipt.v2"],
            "model_profiles": [{"role": "planner", "profile_ref": "local.default"}],
            "resource_requirements": {"max_model_calls_per_iteration": 2},
        },
    }
    for key, value in mutation.items():
        if key == "agent" and isinstance(value, dict):
            payload["agent"] = {**dict(payload["agent"]), **value}  # type: ignore[arg-type]
        else:
            payload[key] = value

    with pytest.raises(ValidationError, match=error_code):
        WorkloadManifest.model_validate(payload)


def test_existing_generic_manifest_shape_remains_valid() -> None:
    """Layer: contract. Existing non-agent declarations preserve their manifest-v0 behavior."""
    workload = WorkloadManifest.model_validate(
        {
            "workload_id": "generic-v0",
            "entrypoint": "demo.generic:run",
            "required_capabilities": ["workspace.root"],
            "legacy_optional_metadata": "ignored-under-v0",
        }
    )

    assert workload.workload_kind == "generic"
    assert workload.agent is None


@pytest.mark.parametrize(
    "marker",
    [
        {"workload_id": "governed-agent-loop"},
        {"required_capabilities": ["agent.iteration.v1"]},
        {"input_contract": "agent_iteration_request.v1"},
        {"output_contract": "agent_iteration_result.v1"},
        {"agent_contract_version": "governed_agent_loop.v1"},
    ],
)
def test_generic_manifest_rejects_every_agent_discriminator(marker: dict[str, object]) -> None:
    payload = {
        "workload_id": "generic-v0",
        "entrypoint": "demo.generic:run",
        "required_capabilities": [],
        **marker,
    }

    with pytest.raises(ValidationError, match="E_SDK_AGENT_"):
        WorkloadManifest.model_validate(payload)

# Layer: contract
def test_agent_manifest_rejects_duplicate_roles() -> None:
    payload = {
        "workload_id": "governed-agent-loop",
        "entrypoint": "demo.agent:run",
        "required_capabilities": ["agent.iteration.v1"],
        "workload_kind": "agent",
        "input_contract": "agent_iteration_request.v1",
        "output_contract": "agent_iteration_result.v1",
        "agent": {
            "contract_version": "governed_agent_loop.v1",
            "required_host_features": ["governed_agent_loop.v1", "agent_stdio_ipc.v1", "agent_model_use_receipt.v2"],
            "model_profiles": [
                {"role": "planner", "profile_ref": "local.a"},
                {"role": "planner", "profile_ref": "local.b"},
            ],
            "resource_requirements": {"max_model_calls_per_iteration": 2},
        },
    }

    with pytest.raises(ValidationError, match="E_SDK_AGENT_ROLE_DUPLICATE"):
        WorkloadManifest.model_validate(payload)
