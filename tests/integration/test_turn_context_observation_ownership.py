"""Upstream context capture: physical integration and separately marked prompt contract proof."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orket.application.services.orchestrator_prompt_preparation_service import (
    OrchestratorPromptPreparationService,
)
from orket.schema import CardStatus, DialectConfig, IssueConfig, RoleConfig
from tests.integration.test_direct_metadata_lifetime import held_metadata
from tests.integration.test_dispatch_input_admission import _dispatch_context

pytestmark = pytest.mark.asyncio


class _OpaqueUnusedValue:
    def __deepcopy__(self, _memo):
        raise AssertionError("unused context value was traversed")


class _ReadPolicy:
    def required_read_paths_for_seat(self, _inputs):
        return ["held.txt"]


class _Memory:
    async def search(self, _query):
        return [{"content": "captured memory", "metadata": {"trust_level": "advisory"}}]


class _PromptSupport:
    def __init__(self):
        self.observed = None

    def resolve_prompt(self, **kwargs):
        self.observed = kwargs
        return SimpleNamespace(
            system_prompt="captured system prompt",
            metadata={"prompt_id": "captured"},
            layers={"role_base": {"name": "captured"}},
        )


@pytest.mark.integration
@pytest.mark.parametrize("empty_sinks", [False, True])
async def test_context_assembly_captures_values_and_retains_output_sinks(tmp_path, monkeypatch, empty_sinks) -> None:
    _repo, issue, _team, orch = await _dispatch_context(tmp_path, SimpleNamespace())
    orch.loop_policy_node = _ReadPolicy()
    target = orch.workspace / "held.txt"
    await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(target.write_text, "held\n", encoding="utf-8")
    issue.params["turn_contract"] = {
        "required_write_paths": ["captured-write.txt"], "unused_resource": _OpaqueUnusedValue(),
    }
    roles = ["coder"]
    scenario = {"marker": ["captured"]}
    cards_runtime = {
        "profile_traits": {"runtime_verifier_allowed": True},
        "scenario_truth": scenario,
        "unused_resource": _OpaqueUnusedValue(),
    }
    prompt_metadata = {} if empty_sinks else {"seed": "original"}
    prompt_layers = {} if empty_sinks else {"seed": "original"}
    state = held_metadata(monkeypatch, target, "exists", False)
    task = asyncio.create_task(orch._build_turn_context(
        run_id="run", issue=issue, seat_name="developer", roles_to_load=roles,
        turn_status=CardStatus.IN_PROGRESS, selected_model="fixture",
        prompt_metadata=prompt_metadata, prompt_layers=prompt_layers, cards_runtime=cards_runtime,
    ))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        roles[0] = "replacement"
        scenario["marker"][0] = "replacement"
        issue.params["turn_contract"]["required_write_paths"][0] = "replacement.txt"
        prompt_metadata["published"] = "after-observation"
        prompt_layers["published"] = "after-observation"
        state.release.set()
        context = await asyncio.wait_for(task, 5)
        assert context["roles"] == ["coder"]
        assert context["scenario_truth"] == {"marker": ["captured"]}
        assert context["required_write_paths"] == ["captured-write.txt"]
        assert context["verification_scope"]["active_context"] == ["held.txt"]
        assert context["prompt_metadata"] is prompt_metadata
        assert context["prompt_layers"] is prompt_layers
    finally:
        state.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert state.finished.is_set()


@pytest.mark.contract
async def test_prompt_selection_inputs_stay_bound_across_context_observation() -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    support = _PromptSupport()
    organization = SimpleNamespace(process_rules={
        "runtime_guard_rule_ids": ["HALLUCINATION.FILE_NOT_FOUND"],
        "prompt_guard_layers": ["captured-guard"],
    })
    dialect = DialectConfig(
        model_family="fixture", dsl_format="text", constraints=[], hallucination_guard="guard",
        prompt_metadata={"owned_rule_ids": ["dialect-captured"]},
    )
    role = RoleConfig(
        id="coder", summary="Coder", description="Implement", tools=[],
        prompt_metadata={"owned_rule_ids": ["role-captured"]},
    )
    cards_runtime = {"suppress_reference_context": False}

    async def build_context(**_kwargs):
        entered.set()
        await release.wait()
        return {"stage_gate_mode": "auto", "required_action_tools": [], "required_statuses": [],
                "required_read_paths": [], "required_write_paths": [], "protocol_governed_enabled": False}

    async def load_asset(_category, _name, _model_type):
        return dialect

    service = OrchestratorPromptPreparationService(
        organization=organization, memory=_Memory(), support_services=support,
        build_turn_context=build_context, resolve_prompt_resolver_mode=lambda: "resolver",
        resolve_prompt_selection_policy=lambda: "captured-policy",
        resolve_prompt_selection_strict=lambda: True, resolve_prompt_version_exact=lambda: "",
        resolve_prompt_patch=lambda: "", resolve_prompt_patch_label=lambda: "",
        should_suppress_reference_context_for_cards_runtime=lambda value: bool(value.get("suppress_reference_context")),
        load_asset=load_asset,
    )
    task = asyncio.create_task(service.build(
        issue=IssueConfig(id="I1", summary="Prompt", seat="coder"), epic=SimpleNamespace(),
        model_selection=SimpleNamespace(select_dialect=lambda _model: "fixture"), run_id="run",
        seat_name="coder", roles_to_load=["coder"], turn_status=CardStatus.IN_PROGRESS,
        selected_model="fixture", dependency_context={}, runtime_result=None, resume_mode=False,
        cards_runtime=cards_runtime, role_config=role,
    ))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        role.prompt_metadata["owned_rule_ids"][0] = "role-replacement"
        dialect.prompt_metadata["owned_rule_ids"][0] = "dialect-replacement"
        organization.process_rules["runtime_guard_rule_ids"][:] = ["SECURITY.PATH_TRAVERSAL"]
        organization.process_rules["prompt_guard_layers"][:] = ["replacement-guard"]
        cards_runtime["suppress_reference_context"] = True
        service.support_services = SimpleNamespace(resolve_prompt=lambda **_kwargs: pytest.fail("late service"))
        release.set()
        context, system_prompt = await asyncio.wait_for(task, 5)
        observed = support.observed
        assert observed["context"]["prompt_rule_ids"] == ["role-captured", "dialect-captured"]
        assert observed["context"]["runtime_guard_rule_ids"] == ["HALLUCINATION.FILE_NOT_FOUND"]
        assert observed["guards"] == ["captured-guard"]
        assert "captured memory" in system_prompt
        assert context["prompt_metadata"]["prompt_id"] == "captured"
        assert context["prompt_layers"] == {"role_base": {"name": "captured"}}
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
