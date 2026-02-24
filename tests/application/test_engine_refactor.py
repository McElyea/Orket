import pytest
from pathlib import Path
import json

from orket.orchestration.engine import OrchestrationEngine


class _FakePipeline:
    def __init__(self):
        self.calls = []

    async def run_epic(self, epic_id, build_id=None, session_id=None, driver_steered=False):
        self.calls.append(("run_epic", epic_id, build_id, session_id, driver_steered))
        return []

    async def run_rock(self, rock_id, build_id=None, session_id=None, driver_steered=False):
        self.calls.append(("run_rock", rock_id, build_id, session_id, driver_steered))
        return {}

    async def run_card(self, card_id, build_id=None, session_id=None, driver_steered=False, target_issue_id=None):
        self.calls.append(("run_card", card_id, build_id, session_id, driver_steered, target_issue_id))
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
    workspace = Path("./test_workspace")
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orket.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orket.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(workspace)

    await engine.run_epic("my-epic")
    await engine.run_rock("my-rock")
    await engine.run_issue("my-issue")

    assert ("run_epic", "my-epic", None, None, False) in fake_pipeline.calls
    assert ("run_rock", "my-rock", None, None, False) in fake_pipeline.calls
    assert ("run_card", "my-issue", None, None, False, None) in fake_pipeline.calls


@pytest.mark.asyncio
async def test_engine_run_card_deprecated(monkeypatch):
    workspace = Path("./test_workspace")
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orket.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orket.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    engine = OrchestrationEngine(workspace)

    await engine.run_card("some-card", target_issue_id="I1")

    assert ("run_card", "some-card", None, None, False, "I1") in fake_pipeline.calls


def test_engine_replay_turn_reads_artifacts(monkeypatch, tmp_path):
    fake_pipeline = _FakePipeline()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orket.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orket.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

    turn_dir = tmp_path / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    turn_dir.mkdir(parents=True)
    (turn_dir / "checkpoint.json").write_text(json.dumps({"run_id": "run-1"}), encoding="utf-8")
    (turn_dir / "messages.json").write_text(json.dumps([{"role": "system", "content": "x"}]), encoding="utf-8")
    (turn_dir / "model_response.txt").write_text("response", encoding="utf-8")
    (turn_dir / "parsed_tool_calls.json").write_text(json.dumps([{"tool": "write_file"}]), encoding="utf-8")

    engine = OrchestrationEngine(tmp_path)
    replay = engine.replay_turn(session_id="run-1", issue_id="ISSUE-1", turn_index=1, role="developer")

    assert replay["checkpoint"]["run_id"] == "run-1"
    assert replay["messages"][0]["role"] == "system"
    assert replay["model_response"] == "response"
    assert replay["parsed_tool_calls"][0]["tool"] == "write_file"


def test_engine_kernel_gateway_path(monkeypatch, tmp_path):
    fake_pipeline = _FakePipeline()
    fake_gateway = _FakeKernelGateway()

    monkeypatch.setattr("orket.settings.load_env", lambda: None)
    monkeypatch.setattr("orket.orket.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.orket.ExecutionPipeline", lambda *args, **kwargs: fake_pipeline)

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

