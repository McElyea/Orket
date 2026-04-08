from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from orket.runtime.epic_run_orchestrator import EpicRunOrchestrator
from orket.runtime.epic_run_types import EpicRunCallbacks


@dataclass
class _IssueRecord:
    id: str
    status: str
    build_id: str
    params: dict[str, Any]
    seat: str = "coder"
    priority: str = "High"
    depends_on: list[str] | None = None

    def model_dump(self, by_alias: bool = True) -> dict[str, Any]:
        del by_alias
        return {
            "id": self.id,
            "summary": self.id,
            "seat": self.seat,
            "priority": self.priority,
            "depends_on": list(self.depends_on or []),
            "params": dict(self.params),
        }


class _CardsRepo:
    def __init__(self) -> None:
        self._rows: list[_IssueRecord] = []

    async def get_by_build(self, build_id: str) -> list[_IssueRecord]:
        return [row for row in self._rows if row.build_id == build_id]

    async def reset_build(self, build_id: str) -> None:
        self._rows = [row for row in self._rows if row.build_id != build_id]

    async def save(self, payload: dict[str, Any]) -> None:
        self._rows.append(
            _IssueRecord(
                id=str(payload["id"]),
                status=str(payload["status"]),
                build_id=str(payload["build_id"]),
                params=dict(payload.get("params") or {}),
            )
        )


class _SessionsRepo:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.completed: dict[str, dict[str, Any]] = {}

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self.sessions.get(session_id)

    async def start_session(self, session_id: str, payload: dict[str, Any]) -> None:
        self.sessions[session_id] = dict(payload)

    async def complete_session(self, session_id: str, status: str, transcript: list[dict[str, Any]]) -> None:
        self.completed[session_id] = {"status": status, "transcript": list(transcript)}


class _SnapshotsRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def record(self, session_id: str, payload: dict[str, Any], transcript: list[dict[str, Any]]) -> None:
        self.calls.append({"session_id": session_id, "payload": dict(payload), "transcript": list(transcript)})


class _SuccessRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def record_success(self, **kwargs: Any) -> None:
        self.calls.append(dict(kwargs))


class _RunLedger:
    def __init__(self) -> None:
        self.started: dict[str, Any] | None = None
        self.finalized: dict[str, Any] | None = None

    async def start_run(self, **kwargs: Any) -> None:
        self.started = dict(kwargs)

    async def finalize_run(self, **kwargs: Any) -> None:
        self.finalized = dict(kwargs)


class _Loader:
    def __init__(self, epic: Any, team: Any, env: Any) -> None:
        self._assets = {
            ("epics", epic.name): epic,
            ("teams", team.name): team,
            ("environments", env.name): env,
        }

    async def load_asset_async(self, asset_kind: str, asset_name: str, _model: object) -> Any:
        return self._assets[(asset_kind, asset_name)]

    async def load_environment_asset_async(self, asset_name: str) -> Any:
        return self._assets[("environments", asset_name)]


class _ControlPlaneRecord:
    def __init__(self, value: str) -> None:
        self.value = value
        self.run_id = value

    def model_dump(self, mode: str = "json") -> dict[str, str]:
        del mode
        return {"id": self.value}


class _ControlPlaneService:
    async def begin_execution(self, **_: Any) -> tuple[_ControlPlaneRecord, _ControlPlaneRecord, _ControlPlaneRecord]:
        return (
            _ControlPlaneRecord("run-record"),
            _ControlPlaneRecord("attempt-record"),
            _ControlPlaneRecord("step-record"),
        )

    async def finalize_execution(self, **_: Any) -> tuple[_ControlPlaneRecord, _ControlPlaneRecord]:
        return (_ControlPlaneRecord("run-record"), _ControlPlaneRecord("attempt-record"))


class _WorkloadShell:
    async def execute(self, *, contract_payload: dict[str, Any], execute_fn: Any) -> None:
        await execute_fn(contract_payload)


class _Orchestrator:
    def __init__(self) -> None:
        self.transcript: list[Any] = []
        self.active_capabilities_allowed: list[str] = []
        self.active_run_determinism_class = ""
        self.active_compatibility_mappings: dict[str, Any] = {}

    async def execute_epic(self, **_: Any) -> None:
        return None


async def _no_op(*_args: Any, **_kwargs: Any) -> None:
    return None


async def _no_receipts(**_kwargs: Any) -> None:
    return None


async def _materialize_summary(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            "run_id": kwargs["run_id"],
            "status": kwargs["session_status"],
            "is_degraded": False,
        },
        dict(kwargs["artifacts"]),
    )


async def _no_export(**_kwargs: Any) -> None:
    return None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_epic_run_orchestrator_runs_with_isolated_collaborators(tmp_path: Path) -> None:
    """Layer: integration. Verifies epic orchestration now consumes explicit runtime inputs outside the decision-node layer."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    cards_repo = _CardsRepo()
    sessions_repo = _SessionsRepo()
    snapshots_repo = _SnapshotsRepo()
    success_repo = _SuccessRepo()
    run_ledger = _RunLedger()
    orchestrator = _Orchestrator()
    transcripts: list[Any] = []

    issue = _IssueRecord(id="ISSUE-1", status="ready", build_id="", params={})
    epic = SimpleNamespace(
        name="epic-orchestrator",
        team="standard",
        environment="standard-env",
        description="Epic orchestrator extraction test",
        architecture_governance=SimpleNamespace(idesign=False),
        issues=[issue],
        params={},
        model_dump=lambda: {"name": "epic-orchestrator"},
    )
    team = SimpleNamespace(name="standard", model_dump=lambda: {"name": "standard"})
    env = SimpleNamespace(
        name="standard-env",
        model="dummy-model",
        model_dump=lambda: {"model": "dummy-model"},
        model_copy=lambda update: SimpleNamespace(
            name="standard-env",
            model=str(update.get("model") or "dummy-model"),
            model_dump=lambda: {"model": str(update.get("model") or "dummy-model")},
            model_copy=lambda next_update: env.model_copy(next_update),
        ),
    )

    epic_runner = EpicRunOrchestrator(
        workspace=workspace,
        department="core",
        organization=SimpleNamespace(architecture=SimpleNamespace(idesign_threshold=10)),
        runtime_input_service=SimpleNamespace(create_session_id=lambda: "sess-epic-runner"),
        execution_runtime_node=SimpleNamespace(
            select_run_id=lambda session_id: str(session_id),
            select_epic_build_id=lambda build_id, epic_name, sanitize_fn: str(
                build_id or f"build-{sanitize_fn(epic_name)}"
            ),
        ),
        pipeline_wiring_service=SimpleNamespace(),
        cards_repo=cards_repo,
        sessions_repo=sessions_repo,
        snapshots_repo=snapshots_repo,
        success_repo=success_repo,
        run_ledger=run_ledger,
        cards_epic_control_plane=_ControlPlaneService(),
        loader=_Loader(epic=epic, team=team, env=env),
        orchestrator=orchestrator,
        workload_shell=_WorkloadShell(),
        callbacks=EpicRunCallbacks(
            resolve_idesign_mode=lambda: "force_none",
            resume_stalled_issues=_no_op,
            resume_target_issue_if_existing=_no_op,
            run_artifact_refs=lambda run_id: {"run_root": f"runs/{run_id}"},
            build_packet1_facts=lambda intended_model: {"intended_model": intended_model},
            materialize_protocol_receipts=_no_receipts,
            materialize_run_summary=_materialize_summary,
            export_run_artifacts=_no_export,
            set_transcript=lambda rows: transcripts.extend(rows),
        ),
    )

    transcript = await epic_runner.run("epic-orchestrator", session_id="sess-epic-runner")

    assert transcript == []
    assert sessions_repo.completed["sess-epic-runner"]["status"] == "incomplete"
    assert run_ledger.started is not None
    assert run_ledger.finalized is not None
    assert run_ledger.finalized["status"] == "incomplete"
    assert run_ledger.finalized["summary"]["is_degraded"] is False
    assert snapshots_repo.calls[0]["session_id"] == "sess-epic-runner"
    assert success_repo.calls == []
    assert transcripts == []
