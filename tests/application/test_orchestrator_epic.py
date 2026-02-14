import pytest
from types import SimpleNamespace

from orket.exceptions import CatastrophicFailure, ExecutionFailed
from orket.application.workflows.orchestrator import Orchestrator
from orket.application.workflows.turn_executor import TurnResult
from orket.schema import CardStatus, IssueConfig


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
    def __init__(self):
        self._assets = []

    def queue_assets(self, assets):
        self._assets = list(assets)

    def load_asset(self, category, name, model):
        if not self._assets:
            raise RuntimeError(f"No queued asset for {category}:{name}")
        return self._assets.pop(0)


class FakeSandbox:
    def __init__(self):
        self.registry = SimpleNamespace(get=lambda _sid: None)


@pytest.fixture
def orchestrator(tmp_path):
    cards = FakeCards()
    snapshots = FakeSnapshots()
    loader = FakeLoader()
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
    loader = FakeLoader()
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

