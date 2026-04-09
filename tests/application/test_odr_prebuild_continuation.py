from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.workflows.orchestrator import Orchestrator
from orket.application.workflows.turn_executor import TurnResult
from orket.schema import CardStatus, IssueConfig

pytestmark = pytest.mark.integration


class AsyncSpy:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.return_value


class FakeCards:
    def __init__(self):
        self.get_by_build = AsyncSpy(return_value=[])
        self.get_independent_ready_issues = AsyncSpy(return_value=[])
        self.get_by_id = AsyncSpy(return_value=SimpleNamespace(status=CardStatus.DONE))
        self.update_status = AsyncSpy(return_value=None)
        self.save = AsyncSpy(return_value=None)


class FakeSnapshots:
    def __init__(self):
        self.record = AsyncSpy(return_value=None)


class FakeLoader:
    def __init__(self, workspace_root: Path):
        self._assets: list[object] = []
        self.file_tools = SimpleNamespace(write_file=self._write_file)
        self._workspace_root = workspace_root

    def queue_assets(self, assets: list[object]) -> None:
        self._assets = list(assets)

    def load_asset(self, category, name, model):
        if not self._assets:
            raise RuntimeError(f"No queued asset for {category}:{name}")
        return self._assets.pop(0)

    async def _write_file(self, path: str, content: str) -> str:
        target = self._workspace_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)


class FakeSandbox:
    def __init__(self):
        self.registry = SimpleNamespace(get=lambda _sid: None)


@pytest.fixture
def orchestrator(tmp_path: Path):
    cards = FakeCards()
    snapshots = FakeSnapshots()
    loader = FakeLoader(tmp_path)
    org = SimpleNamespace(process_rules={}, architecture=SimpleNamespace(idesign_threshold=10))
    orch = Orchestrator(
        workspace=tmp_path,
        async_cards=cards,
        snapshots=snapshots,
        org=org,
        config_root=tmp_path,
        db_path="test.db",
        loader=loader,
        sandbox_orchestrator=FakeSandbox(),
    )
    return orch, cards, loader


@pytest.mark.asyncio
async def test_execute_issue_turn_continues_after_valid_max_rounds_odr_prebuild(
    orchestrator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch, cards, loader = orchestrator
    issue = IssueConfig(
        id="I-ODR",
        seat="coder",
        summary="Write agent_output/out.py",
        params={
            "execution_profile": "odr_prebuild_builder_guard_v1",
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": "agent_output/out.py",
                "required_write_paths": ["agent_output/out.py"],
            },
        },
    )
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-ODR", name="Epic ODR")
    team = SimpleNamespace(seats={"coder": SimpleNamespace(roles=["coder"])})
    env = SimpleNamespace(temperature=0.0, timeout=30)

    loader.queue_assets(
        [
            SimpleNamespace(name="coder", description="Role", tools=["write_file", "update_issue_status"], prompt_metadata={}),
            SimpleNamespace(
                model_family="generic",
                dsl_format="json",
                constraints=[],
                hallucination_guard="none",
                prompt_metadata={},
            ),
        ]
    )

    class _Memory:
        async def search(self, _query):
            return []

        async def remember(self, content, metadata):
            return None

    class _Provider:
        async def clear_context(self):
            return None

        async def close(self):
            return None

    class _ModelClientNode:
        def create_provider(self, selected_model, env):
            return _Provider()

        def create_client(self, provider):
            return SimpleNamespace()

    class _PromptStrategy:
        def select_model(self, role, asset_config):
            return "dummy-model"

        def select_dialect(self, model):
            return "generic"

    captured: dict[str, object] = {}

    class _Executor:
        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            captured["context"] = context
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    async def _noop(*args, **kwargs):
        return None

    async def _fake_odr_prebuild(**kwargs):
        odr_result = {
            "odr_run_id": str(kwargs["run_id"]),
            "odr_valid": True,
            "odr_pending_decisions": 0,
            "odr_stop_reason": "MAX_ROUNDS",
            "odr_artifact_path": "observability/run-1/I-ODR/odr_refinement.json",
            "odr_requirement": "Write agent_output/out.py with a deterministic add(a, b) function.",
            "odr_rounds_completed": 8,
            "odr_accepted": True,
        }
        kwargs["issue"].params["odr_result"] = dict(odr_result)
        return odr_result

    monkeypatch.setattr("orket.application.workflows.orchestrator.PromptCompiler.compile", lambda skill, dialect, **kwargs: "SYSTEM")
    monkeypatch.setattr(
        "orket.application.services.orchestrator_turn_preparation_service.run_cards_odr_prebuild",
        _fake_odr_prebuild,
    )

    orch.memory = _Memory()
    orch.model_client_node = _ModelClientNode()
    orch._save_checkpoint = _noop
    orch._trigger_sandbox = _noop
    orch._request_issue_transition = AsyncSpy(return_value=None)
    cards.get_by_id = AsyncSpy(return_value=SimpleNamespace(status=CardStatus.DONE))

    await orch._execute_issue_turn(
        issue_data=issue_data,
        epic=epic,
        team=team,
        env=env,
        run_id="run-1",
        active_build="build-1",
        prompt_strategy_node=_PromptStrategy(),
        executor=_Executor(),
        toolbox=SimpleNamespace(),
    )

    assert captured["context"]["odr_active"] is True
    assert captured["context"]["odr_stop_reason"] == "MAX_ROUNDS"
    assert captured["context"]["odr_valid"] is True
    assert captured["context"]["odr_pending_decisions"] == 0
    assert captured["context"]["odr_requirement"] == "Write agent_output/out.py with a deterministic add(a, b) function."
    reasons = [kwargs.get("reason") for _args, kwargs in orch._request_issue_transition.calls]
    assert "odr_prebuild_failed" not in reasons
    assert "turn_dispatch" in reasons


@pytest.mark.asyncio
async def test_execute_issue_turn_uses_configured_odr_auditor_model(
    orchestrator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch, cards, loader = orchestrator
    issue = IssueConfig(
        id="I-ODR-AUD",
        seat="coder",
        summary="Write agent_output/out.py",
        params={
            "execution_profile": "odr_prebuild_builder_guard_v1",
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": "agent_output/out.py",
                "required_write_paths": ["agent_output/out.py"],
            },
            "cards_runtime": {
                "odr_auditor_model": "auditor-model",
            },
        },
    )
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-ODR-AUD", name="Epic ODR Auditor")
    team = SimpleNamespace(seats={"coder": SimpleNamespace(roles=["coder"])})
    env = SimpleNamespace(temperature=0.0, timeout=30)

    loader.queue_assets(
        [
            SimpleNamespace(name="coder", description="Role", tools=["write_file", "update_issue_status"], prompt_metadata={}),
            SimpleNamespace(
                model_family="generic",
                dsl_format="json",
                constraints=[],
                hallucination_guard="none",
                prompt_metadata={},
            ),
        ]
    )

    class _Memory:
        async def search(self, _query):
            return []

        async def remember(self, content, metadata):
            return None

    class _Provider:
        def __init__(self, model: str) -> None:
            self.model = model
            self.close_calls = 0

        async def clear_context(self):
            return None

        async def close(self):
            self.close_calls += 1
            return None

    class _Client:
        def __init__(self, provider: _Provider) -> None:
            self.provider = provider

    class _ModelClientNode:
        def __init__(self) -> None:
            self.provider_models: list[str] = []
            self.providers: list[_Provider] = []

        def create_provider(self, selected_model, env):
            provider = _Provider(str(selected_model))
            self.provider_models.append(str(selected_model))
            self.providers.append(provider)
            return provider

        def create_client(self, provider):
            return _Client(provider)

    class _PromptStrategy:
        def select_model(self, role, asset_config):
            return "dummy-model"

        def select_dialect(self, model):
            return "generic"

    captured: dict[str, object] = {}

    class _Executor:
        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    async def _noop(*args, **kwargs):
        return None

    async def _fake_odr_prebuild(**kwargs):
        captured.update(kwargs)
        odr_result = {
            "odr_run_id": str(kwargs["run_id"]),
            "odr_valid": True,
            "odr_pending_decisions": 0,
            "odr_stop_reason": "MAX_ROUNDS",
            "odr_artifact_path": "observability/run-1/I-ODR-AUD/odr_refinement.json",
            "odr_requirement": "Write agent_output/out.py with a deterministic add(a, b) function.",
            "odr_rounds_completed": 8,
            "odr_accepted": True,
        }
        kwargs["issue"].params["odr_result"] = dict(odr_result)
        return odr_result

    monkeypatch.setattr("orket.application.workflows.orchestrator.PromptCompiler.compile", lambda skill, dialect, **kwargs: "SYSTEM")
    monkeypatch.setattr(
        "orket.application.services.orchestrator_turn_preparation_service.run_cards_odr_prebuild",
        _fake_odr_prebuild,
    )

    model_client_node = _ModelClientNode()
    orch.memory = _Memory()
    orch.model_client_node = model_client_node
    orch._save_checkpoint = _noop
    orch._trigger_sandbox = _noop
    orch._request_issue_transition = AsyncSpy(return_value=None)
    cards.get_by_id = AsyncSpy(return_value=SimpleNamespace(status=CardStatus.DONE))

    await orch._execute_issue_turn(
        issue_data=issue_data,
        epic=epic,
        team=team,
        env=env,
        run_id="run-1",
        active_build="build-1",
        prompt_strategy_node=_PromptStrategy(),
        executor=_Executor(),
        toolbox=SimpleNamespace(),
    )

    model_client = captured["model_client"]
    auditor_client = captured["auditor_client"]
    assert model_client is not auditor_client
    assert model_client.provider.model == "dummy-model"
    assert auditor_client.provider.model == "auditor-model"
    assert model_client_node.provider_models[:2] == ["dummy-model", "auditor-model"]
    assert model_client_node.providers[1].close_calls == 1
