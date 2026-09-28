"""Layer: integration. Real fixture children and held native admission metadata."""
import asyncio
import json

import pytest

from orket.application.services.fixture_verification_service import FixtureVerificationService
from orket.schema import IssueVerification, VerificationScenario
from tests.helpers.fixture_input_controls import selected_time
from tests.helpers.runtime_verification_hold import (
    cancel_while_held,
    hold_path,
    settle,
    timeout_while_held,
    wait_entered,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

SOURCE = """import json, os
from pathlib import Path
def verify(data):
    Path('observed.json').write_text(json.dumps({'input': data, 'policy': os.environ['FIXTURE_CAPTURE_VALUE']}))
    return data['nested']['value']
"""


def prepare_native(root):
    directory = root / "verification"
    directory.mkdir()
    (directory / "fixture.py").write_text(SOURCE, encoding="utf-8")
    return IssueVerification(fixture_path="verification/fixture.py", scenarios=[
        VerificationScenario(id="S1", description="original scenario",
                             input_data={"nested": {"value": 7}}, expected_output=7)])


def child_observation(root):
    return json.loads((root / "verification/observed.json").read_text(encoding="utf-8"))


async def test_fixture_detaches_nested_scenario_before_metadata_wait(tmp_path, monkeypatch):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    service = FixtureVerificationService(tmp_path, utc_now=selected_time, environment={"FIXTURE_CAPTURE_VALUE": "original"})
    hold = hold_path(monkeypatch, "is_file", tmp_path / "verification/fixture.py")
    task = asyncio.create_task(service.verify(verification))
    try:
        await wait_entered(hold)
        verification.scenarios[0].input_data["nested"]["value"] = 99
        verification.scenarios[0].expected_output = 99
        verification.scenarios[0].description = "later mutation"
        hold.release.set()
        result = await task
        observed = await asyncio.to_thread(child_observation, tmp_path)
        assert observed["input"] == {"nested": {"value": 7}}
        assert result.passed == 1 and result.process_lifetime["cleanup_confirmed"]
        assert verification.scenarios[0].description == "original scenario"
        assert verification.scenarios[0].actual_output == 7
    finally:
        await settle(task, hold)


async def test_fixture_captures_selected_environment_before_metadata_wait(tmp_path, monkeypatch):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    service = FixtureVerificationService(tmp_path, utc_now=selected_time, environment={"FIXTURE_CAPTURE_VALUE": "original"})
    hold = hold_path(monkeypatch, "is_file", tmp_path / "verification/fixture.py")
    task = asyncio.create_task(service.verify(verification))
    try:
        await wait_entered(hold)
        service.environment["FIXTURE_CAPTURE_VALUE"] = "later mutation"
        hold.release.set()
        result = await task
        observed = await asyncio.to_thread(child_observation, tmp_path)
        assert observed["policy"] == "original"
        assert result.passed == 1 and result.process_lifetime["cleanup_confirmed"]
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_fixture_metadata_stays_owned_through_interruption(tmp_path, monkeypatch, record_property, stop):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    service = FixtureVerificationService(tmp_path, utc_now=selected_time, environment={"FIXTURE_CAPTURE_VALUE": "original"})
    hold = hold_path(monkeypatch, "is_file", tmp_path / "verification/fixture.py")
    task = asyncio.create_task(service.verify(verification))
    try:
        interrupt = cancel_while_held if stop == "cancel" else timeout_while_held
        await interrupt(task, hold, tmp_path / "response.sqlite3", record_property)
        assert verification.scenarios[0].status == "pending"
        assert not await asyncio.to_thread((tmp_path / "verification/observed.json").exists)
    finally:
        await settle(task, hold)


async def test_fixture_healthy_child_retains_real_result(tmp_path):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    service = FixtureVerificationService(tmp_path, utc_now=selected_time, environment={"FIXTURE_CAPTURE_VALUE": "original"})
    result = await service.verify(verification)
    assert result.passed == 1 and result.failed == 0
    assert result.process_lifetime["cleanup_confirmed"]
    assert await asyncio.to_thread(child_observation, tmp_path) == {
        "input": {"nested": {"value": 7}}, "policy": "original"}
