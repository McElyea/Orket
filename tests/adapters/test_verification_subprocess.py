"""Fixture behavior through the canonical async application boundary."""
import asyncio

import pytest

from orket.application.services.fixture_verification_service import FixtureVerificationService
from orket.core.domain.verification import FixtureVerifier, VerificationEngine, VerificationSecurityError
from orket.schema import IssueVerification, VerificationScenario

pytestmark = pytest.mark.asyncio


def prepare(root, source="def verify(data):\n    return data['value']\n"):
    directory = root / "verification"
    directory.mkdir()
    (directory / "fixture.py").write_text(source, encoding="utf-8")
    return IssueVerification(fixture_path="verification/fixture.py", scenarios=[
        VerificationScenario(id="S1", description="fixture outcome", input_data={"value": 7}, expected_output=7)])


@pytest.mark.parametrize("source,passed,detail", [
    ("def verify(data):\n    return data['value']\n", 1, "PASS"),
    ("def verify(data):\n    return 8\n", 0, "Expected 7"),
    ("raise SystemExit(3)\n", 0, "subprocess exit code 3"),
    ("def verify(data)\n    return 7\n", 0, "SyntaxError"),
    ("def verify(data):\n    raise ValueError('fixture failure')\n", 0, "fixture failure"),
    ("x = 1\n", 0, "No verify function"),
])
# Layer: integration
async def test_fixture_outcomes(tmp_path, source, passed, detail):
    verification = await asyncio.to_thread(prepare, tmp_path, source)
    result = await FixtureVerificationService(tmp_path).verify(verification)
    assert (result.passed, result.failed) == (passed, 1 - passed)
    assert any(detail in line for line in result.logs)
    assert result.process_lifetime["cleanup_confirmed"] is True
    assert verification.scenarios[0].status == ("pass" if passed else "fail")


# Layer: integration
async def test_fixture_timeout(tmp_path, monkeypatch):
    verification = await asyncio.to_thread(prepare, tmp_path, "def verify(data):\n    while True: pass\n")
    monkeypatch.setenv("ORKET_VERIFY_TIMEOUT_SEC", "0.3")
    result = await FixtureVerificationService(tmp_path).verify(verification)
    assert result.failed == 1 and result.process_lifetime["reason"] == "timeout"
    assert result.process_lifetime["cleanup_confirmed"] is True


# Layer: integration
async def test_missing_fixture(tmp_path):
    verification = await asyncio.to_thread(prepare, tmp_path)
    verification.fixture_path = "verification/missing.py"
    result = await FixtureVerificationService(tmp_path).verify(verification)
    assert result.failed == 1 and result.process_lifetime is None
    assert any("not found" in line for line in result.logs)


# Layer: integration
async def test_fixture_path_containment(tmp_path):
    verification = await asyncio.to_thread(prepare, tmp_path)
    verification.fixture_path = "../outside.py"
    with pytest.raises(VerificationSecurityError, match="SECURITY VIOLATION"):
        await FixtureVerificationService(tmp_path).verify(verification)
    assert verification.scenarios[0].status == "pending"


@pytest.mark.parametrize("settings,detail", [
    ({"ORKET_RUNTIME_PROFILE": "production", "ORKET_VERIFY_ALLOW_UNSAFE_SUBPROCESS": "0"},
     "disabled in production profile"),
    ({"ORKET_VERIFY_EXECUTION_MODE": "typo"}, "Unknown verification execution mode"),
    ({"ORKET_VERIFY_TIMEOUT_SEC": "nan"}, "finite positive"),
])
# Layer: integration
async def test_invalid_admission_does_not_execute(tmp_path, monkeypatch, settings, detail):
    verification = await asyncio.to_thread(prepare, tmp_path,
        "from pathlib import Path\nPath('executed').touch()\ndef verify(data): return 7\n")
    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    result = await FixtureVerificationService(tmp_path).verify(verification)
    assert result.failed == 1 and result.process_lifetime is None
    assert any(detail in line for line in result.logs)
    assert not await asyncio.to_thread((tmp_path / "verification/executed").exists)


@pytest.mark.parametrize("entrypoint", [FixtureVerifier().verify, VerificationEngine.verify])
# Layer: contract
async def test_sync_entrypoint_requires_explicit_migration(tmp_path, entrypoint):
    verification = await asyncio.to_thread(prepare, tmp_path)
    with pytest.raises(RuntimeError, match="FixtureVerificationService"):
        entrypoint(verification, tmp_path)
    assert verification.scenarios[0].status == "pending"


# Layer: contract
async def test_pre_admission_oserror_is_failure(tmp_path, monkeypatch):
    verification = await asyncio.to_thread(prepare, tmp_path)
    service = FixtureVerificationService(tmp_path)

    async def unavailable(*args, **kwargs):
        raise OSError("controlled pre-admission failure")

    monkeypatch.setattr(service.supervisor, "run", unavailable)
    result = await service.verify(verification)
    assert result.failed == 1 and result.process_lifetime is None
    assert any("controlled pre-admission failure" in line for line in result.logs)
