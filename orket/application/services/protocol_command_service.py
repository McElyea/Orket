"""Application dispatch and strict-result policy for operator protocol commands."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.application.services.protocol_replay_service import ProtocolReplayService


@dataclass(frozen=True)
class ProtocolCommand:
    action: str
    workspace: Path
    invocation_root: Path
    run_a: str = ""
    run_b: str = ""
    events_a: str | None = None
    events_b: str | None = None
    artifacts_a: str | None = None
    artifacts_b: str | None = None
    runs_root: str | None = None
    campaign_run_ids: tuple[str, ...] = ()
    baseline_run_id: str | None = None
    parity_session_ids: tuple[str, ...] = ()
    discover_limit: int = 200
    sqlite_db: str | None = None
    strict: bool = False
    max_parity_mismatches: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign_run_ids", tuple(str(value) for value in self.campaign_run_ids))
        object.__setattr__(self, "parity_session_ids", tuple(str(value) for value in self.parity_session_ids))


@dataclass(frozen=True)
class ProtocolCommandResult:
    payload: dict[str, Any]
    strict_failure: str | None


def _validate_command(request: ProtocolCommand) -> None:
    if request.action in {"replay", "parity"} and not request.run_a.strip():
        raise ValueError(f"protocol {request.action} requires target run_id "
                         f"(e.g. 'orket runtime protocol {request.action} <run_id>').")
    if request.action == "compare" and (not request.run_a.strip() or not request.run_b.strip()):
        raise ValueError("protocol compare requires run A target and --protocol-run-b <run_id> "
                         "(e.g. 'orket runtime protocol compare <run_a> --protocol-run-b <run_b>').")
    if request.action not in {"replay", "compare", "parity", "campaign", "parity-campaign"}:
        raise ValueError("Supported protocol commands: 'orket runtime protocol replay <run_id>', "
                         "'orket runtime protocol compare <run_a> --protocol-run-b <run_b>', or "
                         "'orket runtime protocol parity <run_id> [--protocol-sqlite-db <path>]', or "
                         "'orket runtime protocol campaign [--protocol-runs-root <path>] "
                         "[--protocol-campaign-run-id <run_id>] [--protocol-baseline-run-id <run_id>]', or "
                         "'orket runtime protocol parity-campaign [--protocol-sqlite-db <path>] "
                         "[--protocol-parity-session-id <id>]'.")


def _strict_failure(request: ProtocolCommand, payload: dict[str, Any]) -> str | None:
    if not request.strict:
        return None
    conditions = {
        "compare": (bool(payload.get("deterministic_match")), "Protocol replay mismatch"),
        "parity": (bool(payload.get("parity_ok")), "Run ledger parity mismatch"),
        "campaign": (bool(payload.get("all_match")), "Protocol replay campaign mismatch"),
        "parity-campaign": (int(payload.get("mismatch_count") or 0) <= max(0, request.max_parity_mismatches),
                            "Run ledger parity campaign mismatch"),
    }
    passed, label = conditions.get(request.action, (True, ""))
    return None if passed else f"{label} detected under --protocol-strict."


async def execute_protocol_command(request: ProtocolCommand) -> ProtocolCommandResult:
    _validate_command(request)
    service = ProtocolReplayService(workspace_root=request.workspace, operator_invocation_root=request.invocation_root)
    if request.action == "replay":
        payload = await service.replay_protocol_run(run_id=request.run_a, events_path=request.events_a,
                                                   artifact_root=request.artifacts_a)
    elif request.action == "compare":
        payload = await service.compare_protocol_replays(run_a=request.run_a, run_b=request.run_b,
            events_a=request.events_a, events_b=request.events_b,
            artifacts_a=request.artifacts_a, artifacts_b=request.artifacts_b)
    elif request.action == "parity":
        payload = await service.compare_protocol_and_sqlite_run_ledgers(run_id=request.run_a,
                                                                      sqlite_db_path=request.sqlite_db)
    elif request.action == "campaign":
        payload = await service.compare_protocol_determinism_campaign(run_ids=list(request.campaign_run_ids),
            baseline_run=request.baseline_run_id, runs_root=request.runs_root)
    else:
        payload = await service.compare_protocol_ledger_parity_campaign(session_ids=list(request.parity_session_ids),
            sqlite_db_path=request.sqlite_db, discover_limit=request.discover_limit)
    return ProtocolCommandResult(payload, _strict_failure(request, payload))
