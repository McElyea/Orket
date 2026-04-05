from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import orket.runtime.execution_pipeline as execution_pipeline_module
from orket.runtime.execution_pipeline import ExecutionPipeline


@pytest.mark.asyncio
async def test_run_card_routes_atomic_issue_via_normalized_dispatcher() -> None:
    """Layer: unit. Verifies the canonical card surface dispatches through one normalized resolver."""
    pipeline = object.__new__(ExecutionPipeline)
    seen: dict[str, object] = {}

    async def _resolve(card_id: str):  # type: ignore[no-untyped-def]
        seen["resolved_card_id"] = card_id
        return "issue", "parent-epic"

    async def _run_issue_entry(issue_id: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["issue_id"] = issue_id
        seen["kwargs"] = kwargs
        return {"issue_id": issue_id}

    pipeline._resolve_run_card_target = _resolve  # type: ignore[method-assign]
    pipeline._run_issue_entry = _run_issue_entry  # type: ignore[method-assign]

    result = await ExecutionPipeline.run_card(
        pipeline,
        "ISSUE-42",
        build_id="build-42",
        session_id="session-42",
        driver_steered=True,
    )

    assert seen == {
        "resolved_card_id": "ISSUE-42",
        "issue_id": "ISSUE-42",
        "kwargs": {
            "build_id": "build-42",
            "session_id": "session-42",
            "driver_steered": True,
            "parent_epic_name": "parent-epic",
        },
    }
    assert result == {"issue_id": "ISSUE-42"}


@pytest.mark.asyncio
async def test_run_issue_wrapper_routes_through_run_card() -> None:
    """Layer: unit. Verifies the compatibility issue wrapper does not own dispatch logic."""
    pipeline = object.__new__(ExecutionPipeline)
    seen: dict[str, object] = {}

    async def _run_card(card_id: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["card_id"] = card_id
        seen["kwargs"] = kwargs
        return {"card_id": card_id}

    pipeline.run_card = _run_card  # type: ignore[method-assign]

    result = await ExecutionPipeline.run_issue(
        pipeline,
        "ISSUE-42",
        build_id="build-42",
        session_id="session-42",
        driver_steered=True,
        resume_token="resume-42",
    )

    assert seen == {
        "card_id": "ISSUE-42",
        "kwargs": {
            "build_id": "build-42",
            "session_id": "session-42",
            "driver_steered": True,
            "resume_token": "resume-42",
        },
    }
    assert result == {"card_id": "ISSUE-42"}


@pytest.mark.asyncio
async def test_run_epic_wrapper_routes_through_run_card() -> None:
    """Layer: unit. Verifies the compatibility epic wrapper does not own dispatch logic."""
    pipeline = object.__new__(ExecutionPipeline)
    seen: dict[str, object] = {}

    async def _run_card(card_id: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["card_id"] = card_id
        seen["kwargs"] = kwargs
        return {"card_id": card_id}

    pipeline.run_card = _run_card  # type: ignore[method-assign]

    result = await ExecutionPipeline.run_epic(
        pipeline,
        "EPIC-42",
        build_id="build-42",
        session_id="session-42",
        driver_steered=True,
        target_issue_id="ISSUE-42",
        resume_token="resume-42",
    )

    assert seen == {
        "card_id": "EPIC-42",
        "kwargs": {
            "build_id": "build-42",
            "session_id": "session-42",
            "driver_steered": True,
            "target_issue_id": "ISSUE-42",
            "resume_token": "resume-42",
        },
    }
    assert result == {"card_id": "EPIC-42"}


@pytest.mark.asyncio
async def test_run_rock_wrapper_routes_through_run_card() -> None:
    """Layer: unit. Verifies the compatibility rock wrapper does not own dispatch logic."""
    pipeline = object.__new__(ExecutionPipeline)
    seen: dict[str, object] = {}

    async def _run_card(card_id: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["card_id"] = card_id
        seen["kwargs"] = kwargs
        return {"card_id": card_id}

    pipeline.run_card = _run_card  # type: ignore[method-assign]

    result = await ExecutionPipeline.run_rock(
        pipeline,
        "demo-rock",
        build_id="build-42",
        session_id="session-42",
        driver_steered=True,
        resume_token="resume-42",
    )

    assert seen == {
        "card_id": "demo-rock",
        "kwargs": {
            "build_id": "build-42",
            "session_id": "session-42",
            "driver_steered": True,
            "resume_token": "resume-42",
        },
    }
    assert result == {"card_id": "demo-rock"}


@pytest.mark.asyncio
async def test_issue_dispatch_keeps_cards_epic_workload_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies issue dispatch still reaches the cards-epic workload path after normalization."""
    pipeline = object.__new__(ExecutionPipeline)
    pipeline.workspace = Path("workspace/default")
    seen: dict[str, object] = {}

    async def _run_epic_entry(epic_name: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["epic_name"] = epic_name
        seen["kwargs"] = kwargs
        return [{"epic": epic_name}]

    pipeline._run_epic_entry = _run_epic_entry  # type: ignore[method-assign]
    monkeypatch.setattr(execution_pipeline_module, "log_event", lambda *_args, **_kwargs: None)

    result = await ExecutionPipeline._run_issue_entry(
        pipeline,
        "ISSUE-42",
        build_id="build-42",
        session_id="session-42",
        driver_steered=True,
        parent_epic_name="parent-epic",
        resume_token="resume-42",
    )

    assert seen == {
        "epic_name": "parent-epic",
        "kwargs": {
            "build_id": "build-42",
            "session_id": "session-42",
            "driver_steered": True,
            "target_issue_id": "ISSUE-42",
            "resume_token": "resume-42",
        },
    }
    assert result == [{"epic": "parent-epic"}]


@pytest.mark.asyncio
async def test_issue_dispatch_ignores_forwarded_target_issue_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies issue-card dispatch does not forward a duplicate target_issue_id into epic execution."""

    pipeline = object.__new__(ExecutionPipeline)
    pipeline.workspace = Path("workspace/default")
    seen: dict[str, object] = {}

    async def _run_epic_entry(epic_name: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["epic_name"] = epic_name
        seen["kwargs"] = kwargs
        return [{"epic": epic_name}]

    pipeline._run_epic_entry = _run_epic_entry  # type: ignore[method-assign]
    monkeypatch.setattr(execution_pipeline_module, "log_event", lambda *_args, **_kwargs: None)

    result = await ExecutionPipeline._run_issue_entry(
        pipeline,
        "ISSUE-42",
        build_id="build-42",
        session_id="session-42",
        driver_steered=True,
        parent_epic_name="parent-epic",
        target_issue_id="WRONG-ISSUE",
        resume_token="resume-42",
    )

    assert seen == {
        "epic_name": "parent-epic",
        "kwargs": {
            "build_id": "build-42",
            "session_id": "session-42",
            "driver_steered": True,
            "target_issue_id": "ISSUE-42",
            "resume_token": "resume-42",
        },
    }
    assert result == [{"epic": "parent-epic"}]


@pytest.mark.asyncio
async def test_epic_collection_entry_returns_collection_shaped_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies the internal collection path no longer returns a rock-shaped payload."""
    pipeline = object.__new__(ExecutionPipeline)
    pipeline.workspace = Path("workspace/default")
    seen: dict[str, object] = {"sub_calls": []}

    class _Loader:
        async def load_asset_async(self, asset_kind: str, asset_name: str, _model: object) -> object:
            seen["load"] = (asset_kind, asset_name)
            return SimpleNamespace(
                id="collection-1",
                name="demo-collection",
                epics=(
                    {"epic": "EPIC-1", "department": "core"},
                    {"epic": "EPIC-2", "department": "infra"},
                ),
            )

    class _RuntimeNode:
        def select_epic_collection_session_id(self, session_id: str | None) -> str:
            seen["session_id"] = session_id
            return "collection-session"

        def select_epic_collection_build_id(
            self,
            build_id: str | None,
            collection_name: str,
            _sanitize_name: object,
        ) -> str:
            seen["build"] = (build_id, collection_name)
            return "collection-build"

    class _SubPipeline:
        def __init__(self, *, department: str, epic_workspace: Path) -> None:
            self._department = department
            self._epic_workspace = epic_workspace

        async def run_card(self, epic_id: str, **kwargs) -> dict[str, object]:
            seen["sub_calls"].append((epic_id, self._department, self._epic_workspace, kwargs))
            return {"epic_id": epic_id, "department": self._department}

    class _PipelineWiringNode:
        def create_sub_pipeline(self, *, parent_pipeline: object, epic_workspace: Path, department: str) -> object:
            seen["parent_pipeline"] = parent_pipeline
            return _SubPipeline(department=department, epic_workspace=epic_workspace)

    class _BugFixManager:
        async def start_phase(self, collection_id: str) -> None:
            seen["bug_fix_phase"] = collection_id

    pipeline.loader = _Loader()
    pipeline.execution_runtime_node = _RuntimeNode()
    pipeline.pipeline_wiring_node = _PipelineWiringNode()
    pipeline.bug_fix_manager = _BugFixManager()
    monkeypatch.setattr(execution_pipeline_module, "log_event", lambda *_args, **_kwargs: None)

    result = await ExecutionPipeline._run_epic_collection_entry(
        pipeline,
        "demo-collection",
        build_id="requested-build",
        session_id="requested-session",
        driver_steered=True,
    )

    assert seen["load"] == ("rocks", "demo-collection")
    assert seen["session_id"] == "requested-session"
    assert seen["build"] == ("requested-build", "demo-collection")
    assert seen["bug_fix_phase"] == "collection-1"
    assert seen["sub_calls"] == [
        (
            "EPIC-1",
            "core",
            Path("workspace/default") / "EPIC-1",
            {
                "build_id": "collection-build",
                "session_id": "collection-session",
                "driver_steered": True,
            },
        ),
        (
            "EPIC-2",
            "infra",
            Path("workspace/default") / "EPIC-2",
            {
                "build_id": "collection-build",
                "session_id": "collection-session",
                "driver_steered": True,
            },
        ),
    ]
    assert result == {
        "collection": "demo-collection",
        "results": [
            {"epic": "EPIC-1", "transcript": {"epic_id": "EPIC-1", "department": "core"}},
            {"epic": "EPIC-2", "transcript": {"epic_id": "EPIC-2", "department": "infra"}},
        ],
    }
