import importlib
import json
from pathlib import Path

import pytest

from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.runtime_context import OrketRuntimeContext


class _FakePipeline:
    def __init__(self):
        self.calls = []

    async def run_epic(self, epic_id, build_id=None, session_id=None, driver_steered=False):
        self.calls.append(("run_epic", epic_id, build_id, session_id, driver_steered))
        return []

    async def run_issue(self, issue_id, build_id=None, session_id=None, driver_steered=False):
        self.calls.append(("run_issue", issue_id, build_id, session_id, driver_steered))
        return {}

    async def run_card(
        self,
        card_id,
        build_id=None,
        session_id=None,
        driver_steered=False,
        target_issue_id=None,
        model_override=None,
    ):
        self.calls.append(("run_card", card_id, build_id, session_id, driver_steered, target_issue_id, model_override))
        return []


class _FakeLoader:
    def __init__(self, *_args, **_kwargs):
        pass

    def load_organization(self):
        return None


class _FakeKernelGateway:
    def __init__(self):
        self.calls = []

    def start_run(self, request):
        self.calls.append(("start_run", request))
        return {"kind": "start", "request": request}

    def execute_turn(self, request):
        self.calls.append(("execute_turn", request))
        return {"kind": "execute", "request": request}

    def finish_run(self, request):
        self.calls.append(("finish_run", request))
        return {"kind": "finish", "request": request}

    def resolve_capability(self, request):
        self.calls.append(("resolve_capability", request))
        return {"kind": "resolve", "request": request}

    def authorize_tool_call(self, request):
        self.calls.append(("authorize_tool_call", request))
        return {"kind": "authorize", "request": request}

    def replay_run(self, request):
        self.calls.append(("replay_run", request))
        return {"kind": "replay", "request": request}

    def compare_runs(self, request):
        self.calls.append(("compare_runs", request))
        return {"kind": "compare", "request": request}


@pytest.mark.asyncio
async def test_engine_explicit_calls(monkeypatch):
    """Layer: unit. Verifies the surviving compatibility wrappers collapse back to the canonical engine run_card surface."""
    workspace = Path("./test_workspace")
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orchestration.engine.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orchestration.engine.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(workspace)

    await engine.run_epic("my-epic", target_issue_id="ISSUE-1")
    await engine.run_issue("my-issue")
    await engine.run_rock("my-rock")

    assert ("run_card", "my-epic", None, None, False, "ISSUE-1", None) in fake_pipeline.calls
    assert ("run_card", "my-issue", None, None, False, None, None) in fake_pipeline.calls
    assert ("run_card", "my-rock", None, None, False, None, None) in fake_pipeline.calls
    assert not any(call[0] == "run_epic" for call in fake_pipeline.calls)
    assert not any(call[0] == "run_issue" for call in fake_pipeline.calls)
    assert not any(call[0] == "run_rock" for call in fake_pipeline.calls)


@pytest.mark.asyncio
async def test_engine_run_card_is_canonical_public_surface(monkeypatch):
    """Layer: unit. Verifies the canonical card path reaches the generic pipeline surface."""
    workspace = Path("./test_workspace")
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orchestration.engine.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orchestration.engine.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(workspace)

    await engine.run_card("some-card", target_issue_id="I1")

    assert ("run_card", "some-card", None, None, False, "I1", None) in fake_pipeline.calls


@pytest.mark.asyncio
async def test_engine_run_card_forwards_model_override(monkeypatch):
    """Layer: unit. Verifies card execution preserves an explicit model override for downstream runtime selection."""
    workspace = Path("./test_workspace")
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orchestration.engine.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orchestration.engine.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(workspace)

    await engine.run_card("some-card", model_override="google/gemma-4-26b-a4b")

    assert ("run_card", "some-card", None, None, False, None, "google/gemma-4-26b-a4b") in fake_pipeline.calls


def test_engine_replay_turn_reads_artifacts(monkeypatch, tmp_path):
    """Layer: unit. Verifies replay diagnostics are explicitly artifact-only on both the canonical and compatibility surfaces."""
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orchestration.engine.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orchestration.engine.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    turn_dir = tmp_path / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    turn_dir.mkdir(parents=True)
    (turn_dir / "checkpoint.json").write_text(json.dumps({"run_id": "run-1"}), encoding="utf-8")
    (turn_dir / "messages.json").write_text(json.dumps([{"role": "system", "content": "x"}]), encoding="utf-8")
    (turn_dir / "model_response.txt").write_text("response", encoding="utf-8")
    (turn_dir / "parsed_tool_calls.json").write_text(json.dumps([{"tool": "write_file"}]), encoding="utf-8")

    engine = OrchestrationEngine(tmp_path)
    replay = engine.replay_turn_diagnostics(
        session_id="run-1",
        issue_id="ISSUE-1",
        turn_index=1,
        role="developer",
    )
    compatibility_replay = engine.replay_turn(
        session_id="run-1",
        issue_id="ISSUE-1",
        turn_index=1,
        role="developer",
    )

    assert replay["diagnostics_class"] == "artifact_observability_only"
    assert replay["checkpoint"]["run_id"] == "run-1"
    assert replay["messages"][0]["role"] == "system"
    assert replay["model_response"] == "response"
    assert replay["parsed_tool_calls"][0]["tool"] == "write_file"
    assert compatibility_replay["diagnostics_class"] == "artifact_observability_only"


def test_engine_uses_explicit_control_plane_service_composition(monkeypatch, tmp_path):
    """Layer: unit. Verifies engine control-plane dependencies are composed through the extracted service builder."""
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orchestration.engine.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orchestration.engine.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    fake_services = type(
        "_FakeControlPlaneServices",
        (),
        {
            "pending_gates": object(),
            "control_plane_repository": object(),
            "control_plane_execution_repository": object(),
            "control_plane_publication": object(),
            "tool_approval_control_plane_operator": object(),
            "kernel_action_control_plane": object(),
            "kernel_action_control_plane_operator": object(),
            "kernel_action_control_plane_view": object(),
        },
    )()

    monkeypatch.setattr(
        "orket.orchestration.engine.build_engine_control_plane_services",
        lambda db_path: fake_services,
    )

    engine = OrchestrationEngine(tmp_path)

    assert engine.pending_gates is fake_services.pending_gates
    assert engine.control_plane_repository is fake_services.control_plane_repository
    assert engine.control_plane_execution_repository is fake_services.control_plane_execution_repository
    assert engine.control_plane_publication is fake_services.control_plane_publication
    assert engine.tool_approval_control_plane_operator is fake_services.tool_approval_control_plane_operator
    assert engine.kernel_action_control_plane is fake_services.kernel_action_control_plane
    assert engine.kernel_action_control_plane_operator is fake_services.kernel_action_control_plane_operator
    assert engine.kernel_action_control_plane_view is fake_services.kernel_action_control_plane_view


def test_engine_kernel_gateway_path(monkeypatch, tmp_path):
    fake_pipeline = _FakePipeline()
    fake_gateway = _FakeKernelGateway()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orchestration.engine.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orchestration.engine.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(tmp_path, kernel_gateway=fake_gateway)
    request = {"contract_version": "kernel_api/v1", "workflow_id": "wf-engine"}

    start = engine.kernel_start_run(request)
    execute = engine.kernel_execute_turn({"contract_version": "kernel_api/v1"})
    finish = engine.kernel_finish_run({"contract_version": "kernel_api/v1"})
    resolve = engine.kernel_resolve_capability({"contract_version": "kernel_api/v1"})
    authorize = engine.kernel_authorize_tool_call({"contract_version": "kernel_api/v1"})
    replay = engine.kernel_replay_run({"contract_version": "kernel_api/v1"})
    compare = engine.kernel_compare_runs({"contract_version": "kernel_api/v1"})

    assert start["kind"] == "start"
    assert execute["kind"] == "execute"
    assert finish["kind"] == "finish"
    assert resolve["kind"] == "resolve"
    assert authorize["kind"] == "authorize"
    assert replay["kind"] == "replay"
    assert compare["kind"] == "compare"
    assert [name for name, _ in fake_gateway.calls] == [
        "start_run",
        "execute_turn",
        "finish_run",
        "resolve_capability",
        "authorize_tool_call",
        "replay_run",
        "compare_runs",
    ]


def test_engine_kernel_lifecycle_and_compare_boundary_with_real_gateway(monkeypatch, tmp_path):
    fake_pipeline = _FakePipeline()
    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orchestration.engine.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orchestration.engine.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(tmp_path)
    lifecycle = engine.kernel_run_lifecycle(
        workflow_id="wf-engine-lifecycle",
        execute_turn_requests=[
            {
                "turn_id": "turn-0001",
                "commit_intent": "stage_only",
                "turn_input": {},
            }
        ],
        finish_outcome="PASS",
    )
    assert lifecycle["start"]["contract_version"] == "kernel_api/v1"
    assert lifecycle["finish"]["outcome"] == "PASS"

    compare = engine.kernel_compare_runs(
        {
            "contract_version": "kernel_api/v1",
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [{"turn_id": "turn-0001", "turn_result_digest": "0" * 64}],
                "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "PASS"}],
                "issues": [],
                "events": [],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [{"turn_id": "turn-0001", "turn_result_digest": "1" * 64}],
                "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "PASS"}],
                "issues": [],
                "events": [],
            },
            "compare_mode": "structural_parity",
        }
    )
    assert compare["outcome"] == "FAIL"
    assert compare["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"


def test_engine_module_reload_import_smoke():
    """Layer: unit. Verifies the engine module imports directly without routing through the legacy runtime shim."""
    import orket.orchestration.engine as engine_module

    reloaded = importlib.reload(engine_module)

    assert hasattr(reloaded, "OrchestrationEngine")


def test_engine_reuses_shared_runtime_context(monkeypatch, tmp_path):
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orchestration.engine.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orchestration.engine.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(tmp_path)

    assert isinstance(engine.runtime_context, OrketRuntimeContext)
    assert engine.runtime_context.run_ledger is engine.run_ledger
    assert engine.runtime_context.cards_repo is engine.cards
