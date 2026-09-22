"""Layer: integration. Actual protocol failure cannot abandon a governance engine."""

import asyncio

import pytest

from orket.adapters.storage import async_protocol_run_ledger
from orket.application.services.runtime_result_projection import RuntimeOutcomeError
from orket.orchestration.engine import OrchestrationEngine
from scripts.governance import record_truthful_runtime_artifact_provenance_live_proof as provenance
from scripts.governance import record_truthful_runtime_packet2_repair_live_proof as repair
from tests.helpers import odr_provider_server
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("deterministic_turn_clock")]


@pytest.mark.parametrize("command", [provenance, repair])
def test_governance_http_failure_closes_actual_engine(tmp_path, monkeypatch, command, deterministic_turn_clock):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setenv("ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL", "false")
    monkeypatch.setenv("ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL", "false")
    monkeypatch.setattr(async_protocol_run_ledger, "_default_event_timestamp", deterministic_turn_clock)
    created, closed = [], []
    original_init, original_close = OrchestrationEngine.__init__, OrchestrationEngine.close

    def construct(owner, *args, **kwargs):
        original_init(owner, *args, **kwargs)
        created.append(owner)

    async def close(owner):
        await original_close(owner)
        closed.append(owner)

    monkeypatch.setattr(OrchestrationEngine, "__init__", construct)
    monkeypatch.setattr(OrchestrationEngine, "close", close)
    monkeypatch.setattr(odr_provider_server, "MODEL", "qwen2.5:7b")
    with odr_provider_server.provider_server(mode="inference-failure") as (endpoint, calls):
        monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", endpoint)
        record = (
            provenance.record_truthful_runtime_artifact_provenance_live_proof
            if command is provenance
            else repair.record_truthful_runtime_packet2_repair_live_proof
        )
        try:
            with pytest.raises(RuntimeOutcomeError) as failed:
                record(model="qwen2.5:7b", provider="openai_compat", epic_id="owned_failure")
            assert any(call[0] == "POST" for call in calls), failed.value.result.reason
            assert len(created) == len(closed) == 1
            assert created[0]._closed and created[0]._pipeline._closed
        finally:
            for owner in created:
                if not owner._closed:
                    asyncio.run(original_close(owner))
