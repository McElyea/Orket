"""Layer: integration. Captured policy remains authoritative across real boundaries."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from orket import __version__
from orket.application.services.kernel_invocation_inputs import bind_kernel_invocation_root
from orket.application.services.kernel_runtime_owner import KernelRuntime
from orket.core.contracts.kernel_run_inputs import KernelWorkspaceInputs
from orket.kernel.v1.nervous_system_runtime import projection_pack_v1
from orket.kernel.v1.outbound_policy_gate import OutboundPolicyGate, load_outbound_policy_config_file
from tests.helpers.outbound_policy_probe import policy_app, version

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("field", ["allowed_output_fields", "pii_field_paths", "forbidden_patterns"])
def test_gate_detaches_borrowed_policy_values(field):
    borrowed = {
        "allowed_output_fields": {"default": ["keep"]},
        "pii_field_paths": ["hidden"],
        "forbidden_patterns": ["BLOCKME"],
    }
    gate = OutboundPolicyGate(**{field: borrowed[field]})
    payload = {"keep": "ok", "hidden": "BLOCKME"}
    expected = gate.filter("default", payload)
    if field == "allowed_output_fields":
        borrowed[field]["default"].append("hidden")
    else:
        borrowed[field].clear()
    assert gate.filter("default", payload) == expected


def test_gate_exposes_no_mutable_allowed_field_mapping():
    gate = OutboundPolicyGate(allowed_output_fields={"default": ("keep",)})
    with pytest.raises(TypeError):
        gate.allowed_output_fields["default"] = ("hidden",)


@pytest.mark.asyncio
async def test_direct_file_loading_refuses_event_loop_before_read(tmp_path, monkeypatch):
    path = tmp_path / "policy.json"
    await asyncio.to_thread(path.write_text, "{}", encoding="utf-8")
    original, observed = Path.read_bytes, []

    def read(selected):
        observed.append(selected)
        return original(selected)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(RuntimeError, match="E_OUTBOUND_POLICY_REQUIRES_ASYNC_OWNER"):
        load_outbound_policy_config_file(path)
    assert observed == []


def test_relative_policy_uses_admitted_root(tmp_path, monkeypatch):
    admitted, ambient = tmp_path / "admitted", tmp_path / "ambient"
    for root, marker in ((admitted, "admitted"), (ambient, "ambient")):
        root.mkdir()
        (root / "policy.json").write_text(json.dumps({"placeholder": marker}), encoding="utf-8")
    monkeypatch.chdir(ambient)
    with bind_kernel_invocation_root(KernelWorkspaceInputs(str(admitted))):
        assert load_outbound_policy_config_file("policy.json")["placeholder"] == "admitted"


def test_projection_captures_policy_before_observation_callback(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS", "hidden")
    owner = KernelRuntime(invocation_root=tmp_path)
    clock = owner.sources.utc_now

    def observe_time():
        monkeypatch.setenv("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS", "different")
        return clock()

    owner.sources = replace(owner.sources, utc_now=observe_time)
    try:
        with owner.activate():
            response = projection_pack_v1(
                {
                    "contract_version": "kernel_api/v1",
                    "session_id": "policy",
                    "trace_id": "trace",
                    "purpose": "action_path",
                    "policy_context": {"hidden": "one"},
                    "tool_context_summary": {"hidden": "two"},
                }
            )
        pack = response["projection_pack"]
        assert pack["tool_context_summary"] == {"hidden": "[REDACTED]"}
        assert pack["policy_summary"]["outbound_policy_gate"]["redaction_count"] == 2
    finally:
        owner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [True, False])
async def test_api_uses_construction_policy_environment(tmp_path, monkeypatch, explicit):
    environment = {"ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS": "version"} if explicit else {}
    app = policy_app(tmp_path, environment)
    monkeypatch.setenv("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS", "api" if explicit else "version")
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client,
    ):
        response = await version(client)
    assert response.status_code == 200, response.text
    assert response.json() == {"version": "[REDACTED]" if explicit else __version__, "api": "v1"}
    assert app.state.api_runtime_context.closed


@pytest.mark.asyncio
async def test_invalid_file_pattern_fails_preparation_before_admission(tmp_path):
    path = tmp_path / "policy.json"
    await asyncio.to_thread(path.write_text, '{"forbidden_patterns": ["["]}', encoding="utf-8")
    app = policy_app(tmp_path, {"ORKET_OUTBOUND_POLICY_CONFIG_PATH": "policy.json"})
    with pytest.raises(ValueError, match="E_OUTBOUND_POLICY_INVALID_PATTERN"):
        async with app.router.lifespan_context(app):
            pytest.fail("invalid policy reached API admission")
    assert not app.state.api_ready
