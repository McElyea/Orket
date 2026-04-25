from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from orket.core.contracts import WorkloadContractV1
from orket.runtime.workload_shell import SharedWorkloadShell


class CardsRepository(Protocol):
    async def get_by_build(self, build_id: str) -> list[Any]: ...

    async def reset_build(self, build_id: str) -> None: ...

    async def save(self, payload: dict[str, Any]) -> None: ...


class SessionsRepository(Protocol):
    async def get_session(self, session_id: str) -> Any: ...

    async def start_session(self, session_id: str, payload: dict[str, Any]) -> None: ...

    async def complete_session(self, session_id: str, status: str, transcript: list[dict[str, Any]]) -> None: ...


class SnapshotsRepository(Protocol):
    async def record(self, session_id: str, payload: dict[str, Any], transcript: list[dict[str, Any]]) -> None: ...


class SuccessRepository(Protocol):
    async def record_success(
        self,
        *,
        session_id: str,
        success_type: str,
        artifact_ref: str,
        human_ack: Any,
    ) -> None: ...


class RunLedger(Protocol):
    async def start_run(
        self,
        *,
        session_id: str,
        run_type: str,
        run_name: str,
        department: str,
        build_id: str | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> None: ...

    async def finalize_run(
        self,
        *,
        session_id: str,
        status: str,
        failure_class: str | None = None,
        failure_reason: str | None = None,
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        finalized_at: str | None = None,
    ) -> None: ...


class WorkloadShell(Protocol):
    async def execute(
        self,
        *,
        contract_payload: dict[str, Any],
        execute_fn: Callable[[WorkloadContractV1], Awaitable[None]],
    ) -> Any: ...


@dataclass(frozen=True)
class EpicRunCallbacks:
    resolve_idesign_mode: Callable[[], str]
    resume_stalled_issues: Callable[..., Awaitable[None]]
    resume_target_issue_if_existing: Callable[..., Awaitable[None]]
    run_artifact_refs: Callable[[str], dict[str, Any]]
    build_packet1_facts: Callable[..., dict[str, Any]]
    materialize_protocol_receipts: Callable[..., Awaitable[Any]]
    materialize_run_summary: Callable[..., Awaitable[tuple[dict[str, Any], dict[str, Any]]]]
    export_run_artifacts: Callable[..., Awaitable[Any]]
    set_transcript: Callable[[list[Any]], None]


@dataclass(frozen=True)
class EpicRunSetup:
    epic: Any
    team: Any
    env: Any
    run_id: str
    build_id: str
    target_issue_id: str | None
    resume_mode: bool
    model_override: str
    phase_c_truth_policy: dict[str, Any]
    cards_workload_contract: dict[str, Any]
    control_plane_workload_record: Any


@dataclass(frozen=True)
class EpicRunContext:
    setup: EpicRunSetup
    deterministic_mode_contract: dict[str, Any]
    route_decision_artifact: dict[str, Any]
    control_plane_run: Any
    control_plane_attempt: Any
    control_plane_start_step: Any
    control_plane_checkpoint: Any
    control_plane_checkpoint_acceptance: Any
    run_contract_artifacts: dict[str, Any]


EpicWorkloadShell = SharedWorkloadShell | WorkloadShell
