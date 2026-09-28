"""Layer: integration. real child/HTTP/SQLite selected time."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from orket.application.services.fixture_verification_service import FixtureVerificationService
from orket.application.services.sandbox_verification_service import SandboxVerificationService
from orket.core.domain.sandbox import SandboxStatus
from orket.orchestration.engine import OrchestrationEngine
from tests.adapters.test_sandbox_command_runner import _sandbox
from tests.helpers.fixture_input_controls import NOW, prepare_native
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock
from tests.integration.test_system_acceptance_flow import _build_assets

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("boundary", ["fixture", "http"])
@pytest.mark.parametrize("invalid", [datetime(2042, 6, 15, 12), "2042-06-15T12:00:00+00:00"])
async def test_verification_refuses_invalid_selected_time_before_effects(tmp_path, boundary, invalid):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    verification.scenarios[0].input_data["endpoint"] = "/probe"

    async def respond(_request):
        return 200, 7

    async with observed_http_server(respond) as (url, requests):
        with pytest.raises(ValueError, match="^E_VERIFICATION_TIME_REQUIRES_AWARE_DATETIME$"):
            if boundary == "fixture":
                await FixtureVerificationService(tmp_path, utc_now=lambda: invalid, environment={}).verify(verification)
            else:
                await SandboxVerificationService(utc_now=lambda: invalid).verify_sandbox(
                    SimpleNamespace(id="clock", api_url=url), verification)
        assert not requests and verification.scenarios[0].status == "pending"
        assert not await asyncio.to_thread((tmp_path / "verification/observed.json").exists)


@pytest.mark.parametrize("boundary", ["fixture", "http"])
@pytest.mark.parametrize("offset", [timedelta(), timedelta(hours=5, minutes=30)], ids=["utc", "explicit-offset"])
async def test_verification_samples_once_and_normalizes_explicit_offset(tmp_path, boundary, offset):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    verification.scenarios[0].input_data["endpoint"] = "/probe"
    selected = NOW.replace(tzinfo=timezone(offset))
    samples = []

    def clock():
        samples.append(selected)
        return selected

    async def respond(_request):
        return 200, 7

    async with observed_http_server(respond) as (url, requests):
        if boundary == "fixture":
            result = await FixtureVerificationService(tmp_path, utc_now=clock, environment={}).verify(verification)
            assert result.process_lifetime["cleanup_confirmed"]
            assert not requests
        else:
            result = await SandboxVerificationService(utc_now=clock).verify_sandbox(
                SimpleNamespace(id="clock", api_url=url), verification)
            assert len(requests) == 1
        assert samples == [selected]
        assert result.timestamp == selected.astimezone(UTC).isoformat() and result.passed == 1


class RecordingClock(ProtocolLedgerClock):
    def __init__(self):
        super().__init__()
        self.samples = []

    def utc_now(self):
        value = super().utc_now()
        self.samples.append(value)
        return value


async def _exercise_selected_orchestrator(engine, url, workspace, monkeypatch, clock, release, entered):
    verification = await asyncio.to_thread(prepare_native, workspace)
    verification.scenarios[0].input_data["endpoint"] = "/probe"
    await engine.cards.save({"id": "CLOCK", "summary": "selected observations", "seat": "developer",
        "build_id": "CLOCK-BUILD", "verification": verification.model_dump()})
    orchestrator = engine._pipeline.orchestrator
    sandbox = _sandbox(workspace).model_copy(update={"id": "sandbox-CLOCK-BUILD", "rock_id": "CLOCK-BUILD",
                                                "status": SandboxStatus.RUNNING, "api_url": url})
    orchestrator.sandbox_orchestrator.registry.register(sandbox)
    original_read = engine.cards.get_by_id

    async def held_read(identity):
        if identity == "CLOCK" and not entered.is_set():
            entered.set()
            await asyncio.wait_for(release.wait(), 5)
        return await original_read(identity)

    monkeypatch.setattr(engine.cards, "get_by_id", held_read)
    clock.samples.clear()
    clock.current = NOW
    task = asyncio.create_task(orchestrator.verify_issue("CLOCK"))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        orchestrator.turn_clock = lambda: pytest.fail("replacement orchestrator clock selected")
        release.set()
        result = await task
        retained = (await engine.cards.get_by_id("CLOCK")).verification
        assert len(clock.samples) == 2
        fixture_time, http_time = [sample.astimezone(UTC).isoformat() for sample in clock.samples]
        assert result.timestamp == fixture_time
        assert any(f"Started at {fixture_time}" in line for line in result.logs)
        assert any(f"at {http_time}" in line and "Sandbox" in line for line in result.logs)
        assert result.passed == 2 and result.failed == 0 and result.process_lifetime["cleanup_confirmed"]
        assert retained["last_run"] == result.model_dump() and retained["scenarios"][0]["actual_output"] == 7
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_real_orchestrator_binds_selected_clock_before_first_card_await(tmp_path, monkeypatch, record_property):
    await asyncio.to_thread(_build_assets, tmp_path, with_guard=False, epic_id="selected_verification_clock")
    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")
    clock, entered, release = RecordingClock(), asyncio.Event(), asyncio.Event()

    async def respond(_request):
        return 200, 7

    async with observed_http_server(respond) as (url, requests):
        async with OrchestrationEngine.open(tmp_path / "workspace", department="core",
            db_path=str(tmp_path / "cards.db"), config_root=tmp_path, runtime_inputs=clock) as engine:
            await _exercise_selected_orchestrator(engine, url, tmp_path / "workspace", monkeypatch, clock, release, entered)
        assert engine._closed and len(requests) == 1
        record_property("selected_clock_engine_closed", engine._closed)
