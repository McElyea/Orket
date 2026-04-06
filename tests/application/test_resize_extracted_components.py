from __future__ import annotations

import pytest

from orket.core.domain.fixture_verifier import FixtureVerifier
from orket.core.domain.sandbox_verifier import SandboxVerifier
from orket.orchestration.engine_services import KernelGatewayFacade
from orket.orchestration.orchestration_config import OrchestrationConfig
from orket.schema import IssueVerification, VerificationScenario


def test_fixture_verifier_mark_all_failed() -> None:
    verifier = FixtureVerifier()
    verification = IssueVerification(
        fixture_path="",
        scenarios=[VerificationScenario(id="S1", description="d", input_data={}, expected_output={})],
    )
    failed = verifier.mark_all_failed(verification)
    assert failed == 1
    assert verification.scenarios[0].status == "fail"


@pytest.mark.asyncio
async def test_sandbox_verifier_skips_non_endpoint_scenarios() -> None:
    class _Sandbox:
        id = "sbx"
        api_url = "http://localhost"

    verifier = SandboxVerifier()
    verification = IssueVerification(
        fixture_path="",
        scenarios=[VerificationScenario(id="S1", description="d", input_data={}, expected_output={})],
    )
    result = await verifier.verify_sandbox(_Sandbox(), verification)
    assert result.total_scenarios == 1


def test_orchestration_config_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "sqlite")
    cfg = OrchestrationConfig(org=None)
    assert cfg.resolve_state_backend_mode() == "local"


def test_kernel_gateway_facade_delegates_calls() -> None:
    class _Gateway:
        def __init__(self) -> None:
            self.called = []

        def start_run(self, request):
            self.called.append(("start", request))
            return {"ok": True}

        def execute_turn(self, request):
            self.called.append(("turn", request))
            return {"ok": True}

        def finish_run(self, request):
            self.called.append(("finish", request))
            return {"ok": True}

        def resolve_capability(self, request):
            self.called.append(("cap", request))
            return {"ok": True}

        def authorize_tool_call(self, request):
            self.called.append(("auth", request))
            return {"ok": True}

        def replay_run(self, request):
            self.called.append(("replay", request))
            return {"ok": True}

        def compare_runs(self, request):
            self.called.append(("compare", request))
            return {"ok": True}

        def projection_pack(self, request):
            self.called.append(("projection_pack", request))
            return {"ok": True}

        def admit_proposal(self, request):
            self.called.append(("admit_proposal", request))
            return {"ok": True}

        def commit_proposal(self, request):
            self.called.append(("commit_proposal", request))
            return {"ok": True}

        def end_session(self, request):
            self.called.append(("end_session", request))
            return {"ok": True}

        def run_lifecycle(self, **kwargs):
            self.called.append(("lifecycle", kwargs))
            return {"ok": True}

    gateway = _Gateway()
    facade = KernelGatewayFacade(gateway)
    assert facade.start_run({"a": 1})["ok"] is True
    assert facade.execute_turn({"b": 2})["ok"] is True
    assert facade.finish_run({"c": 3})["ok"] is True
    assert facade.resolve_capability({"d": 4})["ok"] is True
    assert facade.authorize_tool_call({"e": 5})["ok"] is True
    assert facade.replay_run({"f": 6})["ok"] is True
    assert facade.compare_runs({"g": 7})["ok"] is True
    assert facade.projection_pack({"h": 8})["ok"] is True
    assert facade.admit_proposal({"i": 9})["ok"] is True
    assert facade.commit_proposal({"j": 10})["ok"] is True
    assert facade.end_session({"k": 11})["ok"] is True
    assert facade.run_lifecycle(workflow_id="w", execute_turn_requests=[])["ok"] is True
    assert len(gateway.called) == 12
