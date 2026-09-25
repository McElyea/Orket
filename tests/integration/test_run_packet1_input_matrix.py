"""Integration coverage for Packet-1 construction ownership and precedence."""
from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path

import pytest

from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_result_lifetime import open_runtime_owner
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.runtime.run_summary import PACKET1_MISSING_TOKEN
from tests.helpers import ledger_pipeline_fixture
from tests.integration.packet1_input_support import (
    CONTROLLED_TELEMETRY,
    ENVIRONMENT_A,
    ENVIRONMENT_B,
    ENVIRONMENT_C,
    run_controlled_packet1,
    set_packet1_environment,
    write_epic_assets,
)

pytestmark = pytest.mark.integration
_pipeline = ledger_pipeline_fixture.ledger_pipeline


def _provenance(observation: dict) -> dict:
    return observation["summary"]["truthful_runtime_packet1"]["provenance"]


def _assert_observation_intent(
    observation: dict,
    *,
    provider: str,
    start_profile: str,
    final_profile: str,
) -> None:
    provenance = _provenance(observation)
    physical = observation["physical"]["truthful_runtime_packet1"]["provenance"]
    assert observation["started"]["intended_provider"] == provider
    assert observation["started"]["intended_profile"] == start_profile
    assert provenance["intended_provider"] == provider
    assert provenance["intended_profile"] == final_profile
    assert physical["intended_provider"] == provider
    assert physical["intended_profile"] == final_profile
    assert observation["ledger"]["status"] == "done"
    assert observation["physical"] == observation["summary"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("captured", "expected_provider", "start_profile", "final_profile"),
    [
        pytest.param(
            {
                "ORKET_LLM_PROVIDER": "LMStudio",
                "ORKET_MODEL_PROVIDER": "ollama",
                "ORKET_LOCAL_PROMPTING_PROFILE_ID": "configured-profile",
                "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID": "fallback-profile",
            },
            "lmstudio",
            "configured-profile",
            "configured-profile",
            id="preferred-provider-and-configured-profile",
        ),
        pytest.param(
            {
                "ORKET_MODEL_PROVIDER": "OpenAI_Compat",
                "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID": "fallback-profile",
            },
            "openai_compat",
            "default",
            "fallback-profile",
            id="provider-alias-and-observed-fallback",
        ),
        pytest.param(
            {
                "ORKET_LLM_PROVIDER": "",
                "ORKET_MODEL_PROVIDER": "",
                "ORKET_LOCAL_PROMPTING_PROFILE_ID": " ",
                "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID": "",
            },
            "llama_cpp",
            "default",
            "packet1-controlled-profile",
            id="blank-values-use-existing-defaults",
        ),
    ],
)
async def test_packet1_provider_and_profile_precedence_use_captured_environment(
    _pipeline,
    test_root: Path,
    workspace: Path,
    db_path: str,
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[str, str],
    expected_provider: str,
    start_profile: str,
    final_profile: str,
) -> None:
    await write_epic_assets(test_root, "packet1_precedence")
    set_packet1_environment(monkeypatch, captured)
    pipeline = await _pipeline(test_root, workspace, db_path)
    set_packet1_environment(monkeypatch, ENVIRONMENT_C)

    construction_inputs = pipeline.runtime_context.construction_inputs
    assert construction_inputs is not None
    started = pipeline._build_packet1_facts(
        construction_inputs=construction_inputs, intended_model="fixed-model",
    )
    finalized = pipeline._build_packet1_facts(
        construction_inputs=construction_inputs,
        intended_model=None,
        runtime_telemetry=CONTROLLED_TELEMETRY,
    )

    assert started["intended_provider"] == expected_provider
    assert started["intended_profile"] == start_profile
    assert finalized["intended_provider"] == expected_provider
    assert finalized["intended_profile"] == final_profile
    assert finalized["actual_provider"] == CONTROLLED_TELEMETRY["provider_backend"]
    assert finalized["actual_model"] == CONTROLLED_TELEMETRY["model"]
    assert finalized["actual_profile"] == CONTROLLED_TELEMETRY["profile_id"]


@pytest.mark.asyncio
async def test_packet1_without_telemetry_preserves_captured_defaults_and_physical_parity(
    _pipeline,
    test_root: Path,
    workspace: Path,
    db_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    epic_id = "packet1_no_telemetry"
    await write_epic_assets(test_root, epic_id)
    set_packet1_environment(monkeypatch, {"ORKET_LLM_PROVIDER": "LMStudio"})
    pipeline = await _pipeline(test_root, workspace, db_path)
    set_packet1_environment(monkeypatch, ENVIRONMENT_C)
    observation = await run_controlled_packet1(
        pipeline,
        monkeypatch,
        workspace=workspace,
        epic_id=epic_id,
        run_id="sess-packet1-no-telemetry",
        telemetry=None,
    )

    _assert_observation_intent(
        observation,
        provider="lmstudio",
        start_profile="default",
        final_profile="default",
    )
    provenance = _provenance(observation)
    assert provenance["actual_provider"] == "lmstudio"
    assert provenance["actual_profile"] == "default"
    assert provenance["actual_model"] == observation["started"]["actual_model"]
    assert provenance["actual_model"] != PACKET1_MISSING_TOKEN
    assert provenance["fallback_occurred"] is False
    assert provenance["retry_occurred"] is False
    assert provenance["execution_profile"] == "normal"


@pytest.mark.asyncio
async def test_concurrent_packet1_runs_keep_independent_construction_snapshots(
    _pipeline,
    test_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_a = test_root / "workspace-packet1-a"
    workspace_b = test_root / "workspace-packet1-b"
    await write_epic_assets(test_root, "packet1_concurrent_a")
    await write_epic_assets(test_root, "packet1_concurrent_b")
    set_packet1_environment(monkeypatch, ENVIRONMENT_A)
    pipeline_a = await _pipeline(test_root, workspace_a, str(test_root / "packet1-a.db"))
    set_packet1_environment(monkeypatch, ENVIRONMENT_B)
    pipeline_b = await _pipeline(test_root, workspace_b, str(test_root / "packet1-b.db"))
    assert pipeline_a.runtime_inputs.current == pipeline_b.runtime_inputs.current
    set_packet1_environment(monkeypatch, ENVIRONMENT_C)

    telemetry_a = {**CONTROLLED_TELEMETRY, "model": "controlled-a", "profile_id": "actual-a"}
    telemetry_b = {
        **CONTROLLED_TELEMETRY,
        "provider_backend": "ollama",
        "model": "controlled-b",
        "profile_id": "actual-b",
    }
    observation_a, observation_b = await asyncio.gather(
        run_controlled_packet1(
            pipeline_a,
            monkeypatch,
            workspace=workspace_a,
            epic_id="packet1_concurrent_a",
            run_id="sess-packet1-concurrent-a",
            telemetry=telemetry_a,
        ),
        run_controlled_packet1(
            pipeline_b,
            monkeypatch,
            workspace=workspace_b,
            epic_id="packet1_concurrent_b",
            run_id="sess-packet1-concurrent-b",
            telemetry=telemetry_b,
        ),
    )

    _assert_observation_intent(
        observation_a,
        provider="llama_cpp",
        start_profile="default",
        final_profile="packet1-profile-a",
    )
    _assert_observation_intent(
        observation_b,
        provider="lmstudio",
        start_profile="default",
        final_profile="packet1-profile-b",
    )
    provenance_a = _provenance(observation_a)
    provenance_b = _provenance(observation_b)
    assert (provenance_a["actual_provider"], provenance_a["actual_model"], provenance_a["actual_profile"]) == (
        "openai_compat",
        "controlled-a",
        "actual-a",
    )
    assert (provenance_b["actual_provider"], provenance_b["actual_model"], provenance_b["actual_profile"]) == (
        "ollama",
        "controlled-b",
        "actual-b",
    )
    assert pipeline_a.runtime_inputs.current == pipeline_b.runtime_inputs.current


@pytest.mark.asyncio
async def test_native_pipeline_captures_or_reuses_one_construction_owner(
    test_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await write_epic_assets(test_root, "packet1_native_capture")
    set_packet1_environment(monkeypatch, ENVIRONMENT_A)
    native_construct = partial(
        ExecutionPipeline,
        test_root / "workspace-native-capture",
        "core",
        db_path=str(test_root / "packet1-native.db"),
        config_root=test_root,
    )
    async with open_runtime_owner(native_construct, label="packet1-native-capture") as native:
        captured = native.runtime_context.construction_inputs
        assert captured is not None
        assert captured.environment["ORKET_LLM_PROVIDER"] == "llama_cpp"
        assert native.pipeline_wiring_service.construction_inputs is captured
        set_packet1_environment(monkeypatch, ENVIRONMENT_C)
        assert native._build_packet1_facts(
            construction_inputs=captured, intended_model="fixed",
        )["intended_provider"] == "llama_cpp"

    set_packet1_environment(monkeypatch, ENVIRONMENT_B)
    explicit = await RuntimeConstructionInputs.capture_async()
    set_packet1_environment(monkeypatch, ENVIRONMENT_C)
    explicit_construct = partial(
        ExecutionPipeline,
        test_root / "workspace-explicit-capture",
        "core",
        db_path=str(test_root / "packet1-explicit.db"),
        config_root=test_root,
        construction_inputs=explicit,
    )
    async with open_runtime_owner(explicit_construct, label="packet1-explicit-capture") as configured:
        assert configured.runtime_context.construction_inputs is explicit
        assert configured.pipeline_wiring_service.construction_inputs is explicit
        assert configured._build_packet1_facts(
            construction_inputs=explicit, intended_model="fixed",
        )["intended_provider"] == "lmstudio"

    async with OrchestrationEngine.open(
        test_root / "workspace-context-capture",
        db_path=str(test_root / "packet1-context.db"),
        config_root=test_root,
        construction_inputs=explicit,
    ) as engine:
        assert engine.runtime_context.construction_inputs is explicit
        assert engine._pipeline.runtime_context is engine.runtime_context
        assert engine._pipeline.runtime_context.construction_inputs is explicit
        assert engine._pipeline.pipeline_wiring_service.construction_inputs is explicit
