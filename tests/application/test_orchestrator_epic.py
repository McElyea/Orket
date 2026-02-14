import json
import pytest
from types import SimpleNamespace

from orket.exceptions import CatastrophicFailure, ExecutionFailed
from orket.application.workflows.orchestrator import Orchestrator
from orket.application.workflows.turn_executor import TurnResult
from orket.schema import CardStatus, IssueConfig
from orket.application.services.scaffolder import ScaffoldValidationError
from orket.application.services.dependency_manager import DependencyValidationError
from orket.application.services.deployment_planner import DeploymentValidationError


class AsyncSpy:
    def __init__(self, return_value=None, side_effect=None):
        self.return_value = return_value
        self.side_effect = side_effect
        self.calls = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if callable(self.side_effect):
            return self.side_effect(*args, **kwargs)
        if isinstance(self.side_effect, list):
            if self.side_effect:
                return self.side_effect.pop(0)
            return self.return_value
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
    def __init__(self, workspace_root):
        self._assets = []
        self.file_tools = SimpleNamespace(write_file=self._write_file)

        self._workspace_root = workspace_root

    def queue_assets(self, assets):
        self._assets = list(assets)

    def load_asset(self, category, name, model):
        if not self._assets:
            raise RuntimeError(f"No queued asset for {category}:{name}")
        return self._assets.pop(0)

    async def _write_file(self, path, content):
        target = self._workspace_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)


class FakeSandbox:
    def __init__(self):
        self.registry = SimpleNamespace(get=lambda _sid: None)


@pytest.fixture
def orchestrator(tmp_path):
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
async def test_execute_epic_completion(orchestrator, tmp_path):
    orch, cards, _loader = orchestrator
    epic = SimpleNamespace(name="Test Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    # Existing completed backlog means no candidates and immediate completion path.
    cards.get_by_build.side_effect = [[SimpleNamespace(id="I1", status=CardStatus.DONE)]]
    cards.get_independent_ready_issues.side_effect = [[]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    await orch.execute_epic(
        active_build="build-1",
        run_id="run-1",
        epic=epic,
        team=team,
        env=env,
    )

    assert len(cards.get_independent_ready_issues.calls) == 1


@pytest.mark.asyncio
async def test_execute_epic_raises_when_no_candidates_and_backlog_incomplete(orchestrator, tmp_path):
    orch, cards, _loader = orchestrator
    epic = SimpleNamespace(name="Stalled Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    cards.get_by_build.side_effect = [[SimpleNamespace(id="I1", status=CardStatus.IN_PROGRESS)]]
    cards.get_independent_ready_issues.side_effect = [[]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    with pytest.raises(ExecutionFailed, match="No executable candidates while backlog incomplete"):
        await orch.execute_epic(
            active_build="build-stalled",
            run_id="run-stalled",
            epic=epic,
            team=team,
            env=env,
        )


@pytest.mark.asyncio
async def test_execute_epic_propagates_dependency_block_before_stall(orchestrator, tmp_path):
    orch, cards, _loader = orchestrator
    parent = SimpleNamespace(id="ARC-1", status=CardStatus.BLOCKED, depends_on=[])
    child = SimpleNamespace(id="COD-1", status=CardStatus.READY, depends_on=["ARC-1"])
    epic = SimpleNamespace(name="Dependency Block Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    cards.get_by_build.side_effect = [[parent, child], [parent, child]]
    cards.get_independent_ready_issues.side_effect = [[], []]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    await orch.execute_epic(
        active_build="build-dependency-block",
        run_id="run-dependency-block",
        epic=epic,
        team=team,
        env=env,
    )

    assert child.status == CardStatus.BLOCKED
    assert cards.update_status.calls[0][0] == ("COD-1", CardStatus.BLOCKED)
    assert cards.update_status.calls[0][1]["reason"] == "dependency_blocked"


@pytest.mark.asyncio
async def test_execute_epic_runs_scaffolder_stage(orchestrator, tmp_path, monkeypatch):
    orch, cards, _loader = orchestrator
    epic = SimpleNamespace(name="Scaffold Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)
    cards.get_by_build.side_effect = [[SimpleNamespace(id="I1", status=CardStatus.DONE)]]
    cards.get_independent_ready_issues.side_effect = [[]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    hit = {"count": 0}

    class _FakeScaffolder:
        def __init__(self, workspace_root, file_tools, organization):
            self.workspace_root = workspace_root

        async def ensure(self):
            hit["count"] += 1
            return {"created_directories": [], "created_files": []}

    monkeypatch.setattr("orket.application.workflows.orchestrator.Scaffolder", _FakeScaffolder)

    await orch.execute_epic(
        active_build="build-scaffold",
        run_id="run-scaffold",
        epic=epic,
        team=team,
        env=env,
    )

    assert hit["count"] == 1


@pytest.mark.asyncio
async def test_execute_epic_fails_on_scaffolder_validation_error(orchestrator, tmp_path, monkeypatch):
    orch, cards, _loader = orchestrator
    epic = SimpleNamespace(name="Scaffold Fail Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)
    cards.get_by_build.side_effect = [[SimpleNamespace(id="I1", status=CardStatus.DONE)]]
    cards.get_independent_ready_issues.side_effect = [[]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    class _BadScaffolder:
        def __init__(self, workspace_root, file_tools, organization):
            self.workspace_root = workspace_root

        async def ensure(self):
            raise ScaffoldValidationError("missing directories: agent_output/src")

    monkeypatch.setattr("orket.application.workflows.orchestrator.Scaffolder", _BadScaffolder)

    with pytest.raises(ExecutionFailed, match="Scaffolder validation failed"):
        await orch.execute_epic(
            active_build="build-scaffold-fail",
            run_id="run-scaffold-fail",
            epic=epic,
            team=team,
            env=env,
        )


@pytest.mark.asyncio
async def test_execute_epic_runs_dependency_manager_stage(orchestrator, tmp_path, monkeypatch):
    orch, cards, _loader = orchestrator
    epic = SimpleNamespace(name="Dependency Stage Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)
    cards.get_by_build.side_effect = [[SimpleNamespace(id="I1", status=CardStatus.DONE)]]
    cards.get_independent_ready_issues.side_effect = [[]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    hit = {"count": 0}

    class _FakeDependencyManager:
        def __init__(self, workspace_root, file_tools, organization):
            self.workspace_root = workspace_root

        async def ensure(self):
            hit["count"] += 1
            return {"created_files": []}

    monkeypatch.setattr(
        "orket.application.workflows.orchestrator.DependencyManager",
        _FakeDependencyManager,
    )

    await orch.execute_epic(
        active_build="build-deps",
        run_id="run-deps",
        epic=epic,
        team=team,
        env=env,
    )

    assert hit["count"] == 1


@pytest.mark.asyncio
async def test_execute_epic_fails_on_dependency_manager_validation_error(orchestrator, tmp_path, monkeypatch):
    orch, cards, _loader = orchestrator
    epic = SimpleNamespace(name="Dependency Stage Fail Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)
    cards.get_by_build.side_effect = [[SimpleNamespace(id="I1", status=CardStatus.DONE)]]
    cards.get_independent_ready_issues.side_effect = [[]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    class _BadDependencyManager:
        def __init__(self, workspace_root, file_tools, organization):
            self.workspace_root = workspace_root

        async def ensure(self):
            raise DependencyValidationError(
                "missing dependency files: agent_output/dependencies/pyproject.toml"
            )

    monkeypatch.setattr(
        "orket.application.workflows.orchestrator.DependencyManager",
        _BadDependencyManager,
    )

    with pytest.raises(ExecutionFailed, match="Dependency manager validation failed"):
        await orch.execute_epic(
            active_build="build-deps-fail",
            run_id="run-deps-fail",
            epic=epic,
            team=team,
            env=env,
        )


@pytest.mark.asyncio
async def test_execute_epic_runs_deployment_planner_stage(orchestrator, tmp_path, monkeypatch):
    orch, cards, _loader = orchestrator
    epic = SimpleNamespace(name="Deploy Stage Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)
    cards.get_by_build.side_effect = [[SimpleNamespace(id="I1", status=CardStatus.DONE)]]
    cards.get_independent_ready_issues.side_effect = [[]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    hit = {"count": 0}

    class _FakeDeploymentPlanner:
        def __init__(self, workspace_root, file_tools, organization):
            self.workspace_root = workspace_root

        async def ensure(self):
            hit["count"] += 1
            return {"created_files": []}

    monkeypatch.setattr(
        "orket.application.workflows.orchestrator.DeploymentPlanner",
        _FakeDeploymentPlanner,
    )

    await orch.execute_epic(
        active_build="build-deploy",
        run_id="run-deploy",
        epic=epic,
        team=team,
        env=env,
    )

    assert hit["count"] == 1


@pytest.mark.asyncio
async def test_execute_epic_fails_on_deployment_planner_validation_error(orchestrator, tmp_path, monkeypatch):
    orch, cards, _loader = orchestrator
    epic = SimpleNamespace(name="Deploy Stage Fail Epic", issues=[], references=[])
    team = SimpleNamespace(seats={})
    env = SimpleNamespace(temperature=0.1, timeout=30)
    cards.get_by_build.side_effect = [[SimpleNamespace(id="I1", status=CardStatus.DONE)]]
    cards.get_independent_ready_issues.side_effect = [[]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    class _BadDeploymentPlanner:
        def __init__(self, workspace_root, file_tools, organization):
            self.workspace_root = workspace_root

        async def ensure(self):
            raise DeploymentValidationError(
                "missing deployment files: agent_output/deployment/Dockerfile"
            )

    monkeypatch.setattr(
        "orket.application.workflows.orchestrator.DeploymentPlanner",
        _BadDeploymentPlanner,
    )

    with pytest.raises(ExecutionFailed, match="Deployment planner validation failed"):
        await orch.execute_epic(
            active_build="build-deploy-fail",
            run_id="run-deploy-fail",
            epic=epic,
            team=team,
            env=env,
        )


@pytest.mark.asyncio
async def test_handle_failure_retry_limit(orchestrator, monkeypatch):
    orch, cards, _loader = orchestrator
    issue = IssueConfig(id="I1", seat="dev", summary="Test", retry_count=3, max_retries=3)
    result = SimpleNamespace(error="Total failure", violations=[])

    class _Task:
        def cancel(self):
            return None

    async def _fake_get_task(_run_id):
        return _Task()

    monkeypatch.setattr("orket.state.runtime_state.get_task", _fake_get_task)

    with pytest.raises(CatastrophicFailure):
        await orch._handle_failure(issue, result, "run-1", ["dev"])

    assert cards.update_status.calls[-1][0] == ("I1", CardStatus.BLOCKED)
    assert cards.save.calls[-1][0][0]["retry_count"] == 4


@pytest.mark.asyncio
async def test_handle_failure_retry_increment(orchestrator):
    orch, cards, _loader = orchestrator
    issue = IssueConfig(id="I1", seat="dev", summary="Test", retry_count=0, max_retries=3)
    result = SimpleNamespace(error="Fixable error", violations=[])

    with pytest.raises(ExecutionFailed):
        await orch._handle_failure(issue, result, "run-1", ["dev"])

    assert cards.update_status.calls[-1][0] == ("I1", CardStatus.READY)
    assert cards.save.calls[-1][0][0]["retry_count"] == 1
    assert cards.save.calls[-1][0][0]["status"] == CardStatus.READY


@pytest.mark.asyncio
async def test_handle_failure_uses_evaluator_exception_policy(orchestrator):
    orch, _cards, _loader = orchestrator
    issue = IssueConfig(id="I1", seat="dev", summary="Test", retry_count=0, max_retries=3)
    result = SimpleNamespace(error="Fixable error", violations=[])

    class CustomEvaluator:
        def evaluate_failure(self, issue, result):
            return {"action": "retry", "next_retry_count": issue.retry_count + 1}

        def failure_exception_class(self, action):
            return RuntimeError

        def status_for_failure_action(self, action):
            return CardStatus.READY

        def failure_event_name(self, action):
            return None

        def retry_failure_message(self, issue_id, retry_count, max_retries, error):
            return f"CUSTOM RETRY {issue_id} {retry_count}/{max_retries}: {error}"

    orch.evaluator_node = CustomEvaluator()

    with pytest.raises(RuntimeError, match="CUSTOM RETRY I1 1/3: Fixable error"):
        await orch._handle_failure(issue, result, "run-1", ["dev"])


@pytest.mark.asyncio
async def test_execute_epic_honors_custom_loop_policy(orchestrator, tmp_path):
    orch, cards, _loader = orchestrator
    issue = SimpleNamespace(id="I1", status=CardStatus.READY, seat="dev")
    epic = SimpleNamespace(name="Policy Epic", issues=[issue], references=[])
    team = SimpleNamespace(seats={"dev": SimpleNamespace(roles=["dev"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    cards.get_by_build.side_effect = [[issue], [issue]]
    cards.get_independent_ready_issues.side_effect = [[issue]]
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    class CustomLoopPolicy:
        def concurrency_limit(self, organization):
            return 1

        def max_iterations(self, organization):
            return 1

        def is_backlog_done(self, backlog):
            return False

    hit = {"count": 0}

    async def _fake_execute_issue_turn(*args, **kwargs):
        hit["count"] += 1
        return None

    orch.loop_policy_node = CustomLoopPolicy()
    orch._execute_issue_turn = _fake_execute_issue_turn

    with pytest.raises(ExecutionFailed, match="Hyper-Loop exhausted iterations"):
        await orch.execute_epic(
            active_build="build-policy",
            run_id="run-policy",
            epic=epic,
            team=team,
            env=env,
        )

    assert hit["count"] == 1


@pytest.mark.asyncio
async def test_execute_issue_turn_uses_custom_model_client_node(orchestrator, monkeypatch):
    orch, cards, loader = orchestrator
    issue = IssueConfig(id="I1", seat="dev", summary="Test")
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1")
    team = SimpleNamespace(seats={"dev": SimpleNamespace(roles=["lead_architect"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    loader.queue_assets(
        [
            SimpleNamespace(name="dev", description="role", tools=[]),
            SimpleNamespace(model_family="generic", dsl_format="json", constraints=[], hallucination_guard="none"),
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

    class CustomModelClientNode:
        def __init__(self):
            self.provider_calls = 0
            self.client_calls = 0

        def create_provider(self, selected_model, env):
            self.provider_calls += 1
            return _Provider()

        def create_client(self, provider):
            self.client_calls += 1
            return SimpleNamespace()

    class _PromptStrategy:
        def select_model(self, role, asset_config):
            return "dummy-model"

        def select_dialect(self, model):
            return "generic"

    class _Executor:
        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("orket.application.workflows.orchestrator.PromptCompiler.compile", lambda skill, dialect: "SYSTEM")

    orch.memory = _Memory()
    orch._save_checkpoint = _noop
    orch._trigger_sandbox = _noop
    orch.model_client_node = CustomModelClientNode()
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

    assert orch.model_client_node.provider_calls == 1
    assert orch.model_client_node.client_calls == 1


@pytest.mark.asyncio
async def test_execute_issue_turn_skips_sandbox_when_policy_disabled(orchestrator, monkeypatch):
    orch, cards, loader = orchestrator
    issue = IssueConfig(id="I1", seat="dev", summary="Test")
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1")
    team = SimpleNamespace(seats={"dev": SimpleNamespace(roles=["lead_architect"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    loader.queue_assets(
        [
            SimpleNamespace(name="dev", description="role", tools=[]),
            SimpleNamespace(model_family="generic", dsl_format="json", constraints=[], hallucination_guard="none"),
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

    class _Executor:
        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    class _Evaluator:
        def evaluate_success(self, **_kwargs):
            return {}

        def success_post_actions(self, _success_eval):
            return {"trigger_sandbox": True, "next_status": None}

        def should_trigger_sandbox(self, success_actions):
            return bool(success_actions.get("trigger_sandbox"))

        def next_status_after_success(self, success_actions):
            return success_actions.get("next_status")

    async def _noop(*args, **kwargs):
        return None

    trigger_calls = {"count": 0}

    async def _fake_trigger(*args, **kwargs):
        trigger_calls["count"] += 1
        return None

    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setattr("orket.application.workflows.orchestrator.PromptCompiler.compile", lambda skill, dialect: "SYSTEM")

    orch.memory = _Memory()
    orch._save_checkpoint = _noop
    orch._trigger_sandbox = _fake_trigger
    orch.model_client_node = _ModelClientNode()
    orch.evaluator_node = _Evaluator()
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

    assert trigger_calls["count"] == 0


@pytest.mark.asyncio
async def test_execute_issue_turn_blocks_review_when_runtime_verifier_fails(orchestrator, monkeypatch):
    orch, cards, _loader = orchestrator
    issue = IssueConfig(id="REV-1", seat="code_reviewer", summary="Review", status=CardStatus.CODE_REVIEW)
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1")
    team = SimpleNamespace(seats={"code_reviewer": SimpleNamespace(roles=["code_reviewer"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    class _PromptStrategy:
        def select_model(self, role, asset_config):
            return "dummy-model"

        def select_dialect(self, model):
            return "generic"

    class _Executor:
        def __init__(self):
            self.calls = 0

        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            self.calls += 1
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    class _RuntimeVerifier:
        def __init__(self, workspace_root, organization=None):
            self.workspace_root = workspace_root

        async def verify(self):
            return SimpleNamespace(
                ok=False,
                checked_files=["agent_output/main.py"],
                errors=["SyntaxError: invalid syntax"],
            )

    monkeypatch.setattr("orket.application.workflows.orchestrator.RuntimeVerifier", _RuntimeVerifier)
    executor = _Executor()

    await orch._execute_issue_turn(
        issue_data=issue_data,
        epic=epic,
        team=team,
        env=env,
        run_id="run-1",
        active_build="build-1",
        prompt_strategy_node=_PromptStrategy(),
        executor=executor,
        toolbox=SimpleNamespace(),
    )

    assert executor.calls == 0
    saved_issue = cards.save.calls[-1][0][0]
    assert saved_issue["status"] == CardStatus.READY
    assert saved_issue["retry_count"] == 1
    report_path = orch.workspace / "agent_output" / "verification" / "runtime_verification.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is False
    assert report["issue_id"] == "REV-1"
    assert isinstance(report.get("command_results"), list)
    assert isinstance(report.get("failure_breakdown"), dict)
    assert report.get("guard_contract", {}).get("result") == "fail"
    assert report.get("guard_decision", {}).get("action") == "retry"


@pytest.mark.asyncio
async def test_execute_issue_turn_marks_terminal_failure_when_runtime_retries_exhausted(orchestrator, monkeypatch):
    orch, cards, _loader = orchestrator
    issue = IssueConfig(
        id="REV-1",
        seat="code_reviewer",
        summary="Review",
        status=CardStatus.CODE_REVIEW,
        retry_count=3,
        max_retries=3,
    )
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1")
    team = SimpleNamespace(seats={"code_reviewer": SimpleNamespace(roles=["code_reviewer"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    class _PromptStrategy:
        def select_model(self, role, asset_config):
            return "dummy-model"

        def select_dialect(self, model):
            return "generic"

    class _Executor:
        def __init__(self):
            self.calls = 0

        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            self.calls += 1
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    class _RuntimeVerifier:
        def __init__(self, workspace_root, organization=None):
            self.workspace_root = workspace_root

        async def verify(self):
            return SimpleNamespace(
                ok=False,
                checked_files=["agent_output/main.py"],
                errors=["SyntaxError: invalid syntax"],
            )

    monkeypatch.setattr("orket.application.workflows.orchestrator.RuntimeVerifier", _RuntimeVerifier)
    executor = _Executor()

    await orch._execute_issue_turn(
        issue_data=issue_data,
        epic=epic,
        team=team,
        env=env,
        run_id="run-1",
        active_build="build-1",
        prompt_strategy_node=_PromptStrategy(),
        executor=executor,
        toolbox=SimpleNamespace(),
    )

    assert executor.calls == 0
    saved_issue = cards.save.calls[-1][0][0]
    assert saved_issue["status"] == CardStatus.BLOCKED
    assert saved_issue["retry_count"] == 3
    report_path = orch.workspace / "agent_output" / "verification" / "runtime_verification.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report.get("guard_decision", {}).get("action") == "terminal_failure"


@pytest.mark.asyncio
async def test_execute_issue_turn_uses_prompt_resolver_when_policy_enabled(orchestrator, monkeypatch):
    orch, cards, loader = orchestrator
    orch.org.process_rules["prompt_resolver_mode"] = "resolver"
    issue = IssueConfig(id="I1", seat="architect", summary="Design")
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1")
    team = SimpleNamespace(seats={"architect": SimpleNamespace(roles=["architect"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    loader.queue_assets(
        [
            SimpleNamespace(
                name="architect",
                description="Role",
                tools=[],
                prompt_metadata={"id": "role.architect", "version": "2.1.0"},
            ),
            SimpleNamespace(
                model_family="generic",
                dsl_format="json",
                constraints=[],
                hallucination_guard="none",
                prompt_metadata={"id": "dialect.generic", "version": "1.3.0"},
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

    captured = {}

    class _Executor:
        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            captured["context"] = context
            captured["system_prompt"] = system_prompt
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    class _Resolution:
        def __init__(self):
            self.system_prompt = "RESOLVED PROMPT"
            self.metadata = {
                "prompt_id": "role.architect+dialect.generic",
                "prompt_version": "2.1.0/1.3.0",
                "prompt_checksum": "abc123",
                "resolver_policy": "resolver_v1",
            }
            self.layers = {
                "role_base": {"name": "architect", "version": "2.1.0"},
                "dialect_adapter": {"name": "generic", "version": "1.3.0", "prefix_applied": False},
                "guards": [],
                "context_profile": "default",
            }

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "orket.application.workflows.orchestrator.PromptResolver.resolve",
        lambda **kwargs: _Resolution(),
    )

    orch.memory = _Memory()
    orch.model_client_node = _ModelClientNode()
    orch._save_checkpoint = _noop
    orch._trigger_sandbox = _noop
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

    assert captured["system_prompt"] == "RESOLVED PROMPT"
    assert captured["context"]["prompt_metadata"]["prompt_id"] == "role.architect+dialect.generic"
    assert captured["context"]["prompt_metadata"]["resolver_policy"] == "resolver_v1"
    assert captured["context"]["prompt_layers"]["role_base"]["version"] == "2.1.0"


@pytest.mark.asyncio
async def test_execute_issue_turn_uses_prompt_compiler_when_resolver_disabled(orchestrator, monkeypatch):
    orch, cards, loader = orchestrator
    orch.org.process_rules["prompt_resolver_mode"] = "compiler"
    issue = IssueConfig(id="I1", seat="architect", summary="Design")
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1")
    team = SimpleNamespace(seats={"architect": SimpleNamespace(roles=["architect"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    loader.queue_assets(
        [
            SimpleNamespace(name="architect", description="Role", tools=[], prompt_metadata={}),
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

    captured = {}

    class _Executor:
        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            captured["context"] = context
            captured["system_prompt"] = system_prompt
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "orket.application.workflows.orchestrator.PromptCompiler.compile",
        lambda skill, dialect: "COMPILER PROMPT",
    )
    monkeypatch.setattr(
        "orket.application.workflows.orchestrator.PromptResolver.resolve",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("resolver should not be called")),
    )

    orch.memory = _Memory()
    orch.model_client_node = _ModelClientNode()
    orch._save_checkpoint = _noop
    orch._trigger_sandbox = _noop
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

    assert captured["system_prompt"] == "COMPILER PROMPT"
    assert captured["context"]["prompt_metadata"]["prompt_id"] == "legacy.prompt_compiler"
    assert captured["context"]["prompt_metadata"]["resolver_policy"] == "compiler"


@pytest.mark.asyncio
async def test_execute_issue_turn_passes_default_prompt_selection_policy(orchestrator, monkeypatch):
    orch, cards, loader = orchestrator
    orch.org.process_rules["prompt_resolver_mode"] = "resolver"
    issue = IssueConfig(id="I1", seat="architect", summary="Design")
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1")
    team = SimpleNamespace(seats={"architect": SimpleNamespace(roles=["architect"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    loader.queue_assets(
        [
            SimpleNamespace(name="architect", description="Role", tools=[], prompt_metadata={}),
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

    captured = {}

    class _Executor:
        async def execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
            return TurnResult(
                success=True,
                turn=SimpleNamespace(content="done", role=context["role"], issue_id=context["issue_id"], note=""),
            )

    class _Resolution:
        def __init__(self):
            self.system_prompt = "RESOLVED PROMPT"
            self.metadata = {
                "prompt_id": "role.architect+dialect.generic",
                "prompt_version": "1.0.0/1.0.0",
                "prompt_checksum": "abc123",
                "resolver_policy": "resolver_v1",
            }
            self.layers = {
                "role_base": {"name": "architect", "version": "1.0.0"},
                "dialect_adapter": {"name": "generic", "version": "1.0.0", "prefix_applied": False},
                "guards": [],
                "context_profile": "default",
            }

    async def _noop(*args, **kwargs):
        return None

    def _fake_resolve(**kwargs):
        captured["kwargs"] = kwargs
        return _Resolution()

    monkeypatch.setattr("orket.application.workflows.orchestrator.PromptResolver.resolve", _fake_resolve)

    orch.memory = _Memory()
    orch.model_client_node = _ModelClientNode()
    orch._save_checkpoint = _noop
    orch._trigger_sandbox = _noop
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

    assert captured["kwargs"]["selection_policy"] == "stable"
    assert captured["kwargs"]["context"]["prompt_selection_policy"] == "stable"
    assert captured["kwargs"]["context"]["prompt_selection_strict"] is True
    assert "required_action_tools" in captured["kwargs"]["context"]
    assert "required_statuses" in captured["kwargs"]["context"]
    assert "required_read_paths" in captured["kwargs"]["context"]
    assert "required_write_paths" in captured["kwargs"]["context"]
    assert captured["kwargs"]["guards"] == ["hallucination"]


@pytest.mark.asyncio
async def test_execute_epic_uses_custom_tool_strategy_node(tmp_path, monkeypatch):
    issue_ready = SimpleNamespace(
        id="I1",
        status=CardStatus.READY,
        seat="lead_architect",
        model_dump=lambda: {"id": "I1", "seat": "lead_architect", "summary": "Test", "status": "ready"},
    )
    issue_done = SimpleNamespace(id="I1", status=CardStatus.DONE, seat="lead_architect")

    cards = FakeCards()
    cards.get_by_build.side_effect = [[issue_ready], [issue_done]]
    cards.get_independent_ready_issues.side_effect = [[issue_ready], []]
    cards.get_by_id = AsyncSpy(return_value=SimpleNamespace(status=CardStatus.DONE))

    snapshots = FakeSnapshots()
    loader = FakeLoader(tmp_path)
    loader.queue_assets(
        [
            SimpleNamespace(name="lead_architect", description="Role", tools=["custom_noop"]),
            SimpleNamespace(model_family="generic", dsl_format="json", constraints=[], hallucination_guard="none"),
        ]
    )

    org = SimpleNamespace(process_rules={"tool_strategy_node": "custom-tool-strategy"})
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

    class CustomToolStrategy:
        def compose(self, toolbox):
            return {"custom_noop": lambda args, context=None: {"ok": True, "tool": "custom_noop", "args": args}}

    class _PromptStrategy:
        def select_model(self, role, asset_config):
            return "dummy-model"

        def select_dialect(self, model):
            return "generic"

    class _Provider:
        async def clear_context(self):
            return None

    class _ModelClient:
        def create_provider(self, selected_model, env):
            return _Provider()

        def create_client(self, provider):
            return SimpleNamespace()

    class _Memory:
        async def search(self, _query):
            return []

        async def remember(self, content, metadata):
            return None

    tool_strategy_hit = {"used": False}

    async def _fake_execute_turn(self, issue, role_config, client, toolbox, context, system_prompt=None):
        res = await toolbox.execute("custom_noop", {"x": 1}, context=context)
        tool_strategy_hit["used"] = res.get("ok") is True and res.get("tool") == "custom_noop"
        return TurnResult(
            success=True,
            turn=SimpleNamespace(role=context["role"], issue_id=context["issue_id"], content="done", note=""),
        )

    orch.decision_nodes.register_tool_strategy("custom-tool-strategy", CustomToolStrategy())
    orch.decision_nodes.resolve_prompt_strategy = lambda *_args, **_kwargs: _PromptStrategy()
    orch.model_client_node = _ModelClient()
    orch.memory = _Memory()
    orch._save_checkpoint = AsyncSpy(return_value=None)

    monkeypatch.setattr("orket.application.workflows.turn_executor.TurnExecutor.execute_turn", _fake_execute_turn)

    epic = SimpleNamespace(name="Tool Strategy Epic", references=[], issues=[], parent_id=None, id="EPIC-1")
    team = SimpleNamespace(seats={"lead_architect": SimpleNamespace(roles=["lead_architect"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)
    (tmp_path / "user_settings.json").write_text('{"models": {}}', encoding="utf-8")

    await orch.execute_epic(
        active_build="build-tool-strategy",
        run_id="run-tool-strategy",
        epic=epic,
        team=team,
        env=env,
    )

    assert tool_strategy_hit["used"] is True


def test_build_turn_context_includes_stage_gate_mode(orchestrator):
    orch, _cards, _loader = orchestrator
    issue = IssueConfig(id="I1", seat="integrity_guard", summary="Guard Review")
    context = orch._build_turn_context(
        run_id="run-1",
        issue=issue,
        seat_name="integrity_guard",
        roles_to_load=["integrity_guard"],
        turn_status=CardStatus.AWAITING_GUARD_REVIEW,
        selected_model="dummy-model",
        resume_mode=False,
    )
    assert context["stage_gate_mode"] == "review_required"
    assert context["approval_required_tools"] == []
    assert context["required_read_paths"] == []
    assert callable(context["create_pending_gate_request"])


def test_build_turn_context_promotes_gate_mode_when_approval_tools_present(orchestrator):
    orch, _cards, _loader = orchestrator
    issue = IssueConfig(id="I1", seat="coder", summary="Code Work")

    class _LoopPolicy:
        def required_action_tools_for_seat(self, seat_name, issue=None, turn_status=None):
            return ["write_file", "update_issue_status"]

        def required_statuses_for_seat(self, seat_name, issue=None, turn_status=None):
            return ["code_review"]

        def gate_mode_for_seat(self, seat_name, issue=None, turn_status=None):
            return "auto"

        def approval_required_tools_for_seat(self, seat_name, issue=None, turn_status=None):
            return ["write_file"]

        def required_read_paths_for_seat(self, seat_name, issue=None, turn_status=None):
            return []

    orch.loop_policy_node = _LoopPolicy()
    context = orch._build_turn_context(
        run_id="run-1",
        issue=issue,
        seat_name="coder",
        roles_to_load=["coder"],
        turn_status=CardStatus.IN_PROGRESS,
        selected_model="dummy-model",
        resume_mode=False,
    )

    assert context["approval_required_tools"] == ["write_file"]
    assert context["stage_gate_mode"] == "approval_required"


def test_build_turn_context_includes_required_read_paths_for_reviewer(orchestrator):
    orch, _cards, _loader = orchestrator
    issue = IssueConfig(id="REV-1", seat="code_reviewer", summary="Review")
    context = orch._build_turn_context(
        run_id="run-1",
        issue=issue,
        seat_name="code_reviewer",
        roles_to_load=["code_reviewer"],
        turn_status=CardStatus.IN_PROGRESS,
        selected_model="dummy-model",
        dependency_context={"depends_on": ["COD-1"], "dependency_count": 1, "dependency_statuses": {}, "unresolved_dependencies": []},
        resume_mode=False,
    )
    assert context["required_read_paths"] == [
        "agent_output/requirements.txt",
        "agent_output/main.py",
    ]
    assert context["required_write_paths"] == []


def test_build_turn_context_includes_required_write_paths_for_coder(orchestrator):
    orch, _cards, _loader = orchestrator
    issue = IssueConfig(id="COD-1", seat="coder", summary="Implement")
    context = orch._build_turn_context(
        run_id="run-1",
        issue=issue,
        seat_name="coder",
        roles_to_load=["coder"],
        turn_status=CardStatus.IN_PROGRESS,
        selected_model="dummy-model",
        resume_mode=False,
    )
    assert context["required_write_paths"] == ["agent_output/main.py"]


def test_build_turn_context_non_final_guard_requires_done_status(orchestrator):
    orch, _cards, _loader = orchestrator
    issue = IssueConfig(id="COD-1", seat="coder", summary="Guard handoff")
    context = orch._build_turn_context(
        run_id="run-1",
        issue=issue,
        seat_name="integrity_guard",
        roles_to_load=["integrity_guard"],
        turn_status=CardStatus.AWAITING_GUARD_REVIEW,
        selected_model="dummy-model",
        resume_mode=False,
    )
    assert context["required_statuses"] == ["done"]
    assert context["required_action_tools"] == ["update_issue_status"]
    assert context["required_read_paths"] == []


def test_build_turn_context_final_guard_includes_read_contract(orchestrator):
    orch, _cards, _loader = orchestrator
    issue = IssueConfig(id="REV-1", seat="code_reviewer", summary="Final guard review")
    context = orch._build_turn_context(
        run_id="run-1",
        issue=issue,
        seat_name="integrity_guard",
        roles_to_load=["integrity_guard"],
        turn_status=CardStatus.AWAITING_GUARD_REVIEW,
        selected_model="dummy-model",
        runtime_verifier_ok=True,
        resume_mode=False,
    )
    assert context["required_statuses"] == ["done", "blocked"]
    assert context["required_action_tools"] == ["read_file", "update_issue_status"]
    assert context["required_read_paths"] == [
        "agent_output/requirements.txt",
        "agent_output/design.txt",
        "agent_output/main.py",
        "agent_output/verification/runtime_verification.json",
    ]
    assert context["runtime_verifier_ok"] is True


def test_build_turn_context_includes_architecture_contract_for_architect(orchestrator):
    orch, _cards, _loader = orchestrator
    orch.org = SimpleNamespace(
        process_rules={
            "architecture_mode": "force_microservices",
            "frontend_framework_mode": "force_angular",
        }
    )
    issue = IssueConfig(id="ARC-1", seat="architect", summary="Design architecture")
    context = orch._build_turn_context(
        run_id="run-1",
        issue=issue,
        seat_name="architect",
        roles_to_load=["architect"],
        turn_status=CardStatus.IN_PROGRESS,
        selected_model="dummy-model",
        resume_mode=False,
    )
    assert context["architecture_mode"] == "force_microservices"
    assert context["architecture_decision_required"] is True
    assert context["architecture_decision_path"] == "agent_output/design.txt"
    assert context["architecture_forced_pattern"] == "microservices"
    assert context["frontend_framework_mode"] == "force_angular"
    assert context["frontend_framework_forced"] == "angular"
    assert "angular" in context["frontend_framework_allowed"]
    assert "monolith" in context["architecture_allowed_patterns"]
    assert "microservices" in context["architecture_allowed_patterns"]


@pytest.mark.asyncio
async def test_build_turn_context_pending_gate_callback_creates_tool_approval_request(orchestrator):
    orch, _cards, _loader = orchestrator
    issue = IssueConfig(id="I1", seat="coder", summary="Code Work")

    class _PendingRepo:
        def __init__(self):
            self.calls = []

        async def create_request(self, **kwargs):
            self.calls.append(kwargs)
            return "REQ-TOOL-42"

    class _LoopPolicy:
        def required_action_tools_for_seat(self, seat_name, issue=None, turn_status=None):
            return ["write_file", "update_issue_status"]

        def required_statuses_for_seat(self, seat_name, issue=None, turn_status=None):
            return ["code_review"]

        def gate_mode_for_seat(self, seat_name, issue=None, turn_status=None):
            return "auto"

        def approval_required_tools_for_seat(self, seat_name, issue=None, turn_status=None):
            return ["write_file"]

    orch.pending_gates = _PendingRepo()
    orch.loop_policy_node = _LoopPolicy()
    context = orch._build_turn_context(
        run_id="run-1",
        issue=issue,
        seat_name="coder",
        roles_to_load=["coder"],
        turn_status=CardStatus.IN_PROGRESS,
        selected_model="dummy-model",
        resume_mode=False,
    )

    request_id = await context["create_pending_gate_request"](
        tool_name="write_file",
        tool_args={"path": "out.txt", "content": "ok"},
    )

    assert request_id == "REQ-TOOL-42"
    assert len(orch.pending_gates.calls) == 1
    req = orch.pending_gates.calls[0]
    assert req["session_id"] == "run-1"
    assert req["issue_id"] == "I1"
    assert req["seat_name"] == "coder"
    assert req["gate_mode"] == "approval_required"
    assert req["request_type"] == "tool_approval"
    assert req["reason"] == "approval_required_tool:write_file"
    assert req["payload"]["tool"] == "write_file"


def test_validate_guard_rejection_payload_default_logic(orchestrator):
    orch, _cards, _loader = orchestrator

    invalid = orch._validate_guard_rejection_payload(
        SimpleNamespace(rationale="", remediation_actions=["Do something"])
    )
    assert invalid == {"valid": False, "reason": "missing_rationale"}

    invalid_actions = orch._validate_guard_rejection_payload(
        SimpleNamespace(rationale="Needs remediation.", remediation_actions=[])
    )
    assert invalid_actions == {"valid": False, "reason": "missing_remediation_actions"}

    valid = orch._validate_guard_rejection_payload(
        SimpleNamespace(rationale="Needs remediation.", remediation_actions=["Fix issue"])
    )
    assert valid == {"valid": True, "reason": None}


@pytest.mark.asyncio
async def test_create_pending_gate_request_uses_policy_gate_mode(orchestrator):
    orch, _cards, _loader = orchestrator

    class _PendingRepo:
        def __init__(self):
            self.calls = []

        async def create_request(self, **kwargs):
            self.calls.append(kwargs)
            return "REQ-1234"

    class _LoopPolicy:
        def gate_mode_for_seat(self, seat_name, issue=None, turn_status=None):
            return "review_required" if seat_name == "integrity_guard" else "auto"

    orch.pending_gates = _PendingRepo()
    orch.loop_policy_node = _LoopPolicy()

    request_id = await orch._create_pending_gate_request(
        run_id="run-1",
        issue_id="ISSUE-1",
        seat_name="integrity_guard",
        reason="missing_rationale",
        payload={"rationale": "", "remediation_actions": []},
        issue=IssueConfig(id="ISSUE-1", seat="integrity_guard", summary="Guard Review"),
        turn_status=CardStatus.AWAITING_GUARD_REVIEW,
    )

    assert request_id == "REQ-1234"
    assert len(orch.pending_gates.calls) == 1
    call = orch.pending_gates.calls[0]
    assert call["session_id"] == "run-1"
    assert call["gate_mode"] == "review_required"
    assert call["request_type"] == "guard_rejection_payload"


@pytest.mark.asyncio
async def test_build_dependency_context_resolves_dependency_statuses(orchestrator):
    orch, cards, _loader = orchestrator
    issue = IssueConfig(
        id="COD-1",
        seat="coder",
        summary="Implement",
        depends_on=["ARC-1", "REQ-1", "MISSING-1"],
    )

    def _get_by_id(card_id):
        if card_id == "ARC-1":
            return SimpleNamespace(status=CardStatus.DONE)
        if card_id == "REQ-1":
            return SimpleNamespace(status=CardStatus.CODE_REVIEW)
        return None

    cards.get_by_id.side_effect = _get_by_id
    context = await orch._build_dependency_context(issue)

    assert context["dependency_count"] == 3
    assert context["dependency_statuses"]["ARC-1"] == "done"
    assert context["dependency_statuses"]["REQ-1"] == "code_review"
    assert context["dependency_statuses"]["MISSING-1"] == "missing"
    assert set(context["unresolved_dependencies"]) == {"REQ-1", "MISSING-1"}


