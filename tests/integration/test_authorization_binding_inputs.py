"""Integration: native authorization observation retains input provenance and drift refusal."""
import asyncio
import json
from copy import deepcopy

import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY, BuiltInConnectorRegistry
from orket.application.services.outward_authorization_service import bind_authorization, validate_dispatch_authorization
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_authorization import canonical_json
from orket.core.domain.outward_runs import OutwardRunRecord
from tests.integration.test_async_file_invocation_inputs import hold_path_method

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def prepare_authorization(root):
    metadata = deepcopy(DEFAULT_BUILTIN_CONNECTOR_REGISTRY.get("write_file"))
    registry = BuiltInConnectorRegistry([metadata])
    service = OutwardConnectorService(connector_registry=registry, workspace_root=root)
    args = {"path": "original.json", "content": {"values": ["admitted"]}}
    run = OutwardRunRecord(run_id="run-inputs", status="running", namespace="proof", submitted_at="2026-09-21T00:00:00Z",
        current_turn=1, max_turns=3, execution_generation=1,
        task={"model_governed_tool_call": {"tool": "write_file", "args": args},
              "_outward_execution_state": {"step_index": 0}, "acceptance_contract": {"label": "admitted"}},
        policy_overrides={"approval_required_tools": ["write_file"], "limit": {"count": 1}})
    proposal = OutwardApprovalProposal(proposal_id="proposal-inputs", run_id=run.run_id, namespace=run.namespace,
        tool="write_file", args_preview={}, context_summary="Proof", risk_level="write",
        submitted_at=run.submitted_at, expires_at="2026-09-22T00:00:00Z")
    return service, args, run, proposal


async def test_authorization_binding_captures_arguments_and_nested_run_inputs(tmp_path, monkeypatch):
    service, args, run, proposal = prepare_authorization(tmp_path)
    expected_args = canonical_json(args)
    expected_policy = deepcopy(run.policy_overrides)
    state = hold_path_method(monkeypatch, "resolve", tmp_path / "original.json")
    task = asyncio.create_task(bind_authorization(proposal, run, args, service))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        args["path"] = "changed.json"
        args["content"]["values"].append("changed")
        run.policy_overrides["limit"]["count"] = 9
        run.task["_outward_execution_state"]["step_index"] = 9
        run.task["acceptance_contract"]["label"] = "changed"
        state.release.set()
        binding = await asyncio.wait_for(task, 5)
        assert binding.arguments_json == expected_args and binding.step_index == 0
        assert binding.target_ref == str(tmp_path / "original.json")
        policy = json.loads(binding.policy_json)
        assert policy["run_policy"] == expected_policy
        assert policy["acceptance_contract"] == {"label": "admitted"}
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)


async def test_context_captures_paths_metadata_and_allowlist_before_wait(tmp_path, monkeypatch):
    service, args, _run, _proposal = prepare_authorization(tmp_path)
    expected = await service.authorization_context("write_file", args)
    state = hold_path_method(monkeypatch, "resolve", tmp_path / "original.json")
    task = asyncio.create_task(service.authorization_context("write_file", args))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        args["path"] = "changed.json"
        service.executor.workspace_root = tmp_path / "changed"
        service.executor.file_tools.async_fs.workspace_root = tmp_path / "changed"
        service.executor.http_allowlist = ("changed.invalid",)
        metadata = service.connector_registry.get("write_file")
        metadata.args_schema["properties"]["path"]["title"] = "changed"
        state.release.set()
        assert await asyncio.wait_for(task, 5) == expected
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)


@pytest.mark.parametrize("connector", ["http_get", "http_post"])
async def test_http_context_retains_the_validated_url_and_allowlist(tmp_path, monkeypatch, connector):
    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path, http_allowlist=("admitted.invalid",))
    args = {"url": "https://admitted.invalid/original"}
    if connector == "http_post":
        args["body"] = {"values": ["admitted"]}
    expected = await service.authorization_context(connector, args)
    state = hold_path_method(monkeypatch, "resolve", tmp_path)
    task = asyncio.create_task(service.authorization_context(connector, args))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        args["url"] = "https://unadmitted.invalid/changed"
        service.executor.http_allowlist = ("changed.invalid",)
        state.release.set()
        assert await asyncio.wait_for(task, 5) == expected
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)


@pytest.mark.parametrize("connector", ["write_file", "http_get", "run_command"])
async def test_context_uses_the_registered_connector_name(tmp_path, connector):
    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path, http_allowlist=("admitted.invalid",))
    args = {"write_file": {"path": "target.txt", "content": "input"},
            "http_get": {"url": "https://admitted.invalid/input"},
            "run_command": {"command": ["not-executed"]}}[connector]
    assert await service.authorization_context(" " + connector + " ", args) == await service.authorization_context(connector, args)


async def test_dispatch_policy_mutation_during_observation_is_refused(tmp_path, monkeypatch):
    service, args, run, proposal = prepare_authorization(tmp_path)
    binding = await bind_authorization(proposal, run, args, service)
    state = hold_path_method(monkeypatch, "resolve", tmp_path / "original.json")
    task = asyncio.create_task(validate_dispatch_authorization(binding, run, service))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        run.policy_overrides["limit"]["count"] = 9
        state.release.set()
        with pytest.raises(RuntimeError, match="E_OUTWARD_AUTHORIZATION_POLICY_DRIFT"):
            await asyncio.wait_for(task, 5)
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)


async def test_dispatch_argument_mutation_during_observation_is_refused(tmp_path, monkeypatch):
    service, args, run, proposal = prepare_authorization(tmp_path)
    binding = await bind_authorization(proposal, run, args, service)
    state = hold_path_method(monkeypatch, "resolve", tmp_path / "original.json")
    task = asyncio.create_task(validate_dispatch_authorization(binding, run, service))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        run.task["model_governed_tool_call"]["args"]["content"]["values"].append("changed")
        state.release.set()
        with pytest.raises(RuntimeError, match="E_OUTWARD_AUTHORIZATION_ARGUMENT_DRIFT"):
            await asyncio.wait_for(task, 5)
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)
