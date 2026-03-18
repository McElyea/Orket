from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from .artifacts import MarshallerArtifacts
from .attempt_runtime import AttemptResult, AttemptRuntime
from .contracts import RunRequest
from .ledger import LedgerWriter
from .rejection_codes import SCHEMA_INVALID
from .runner_support import build_run_summary, build_triage_payload


@dataclass(frozen=True)
class MarshallerRunOutcome:
    run_id: str
    accept: bool
    rejection_codes: tuple[str, ...]
    primary_rejection_code: str | None
    run_root_digest: str
    run_path: str
    decision_path: str
    attempt_count: int
    accepted_attempt_index: int | None
    summary_path: str


class MarshallerRunner:
    """Marshaller v0 run orchestrator with multi-attempt execution support."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    async def execute_once(
        self,
        *,
        run_id: str,
        run_request_payload: Mapping[str, Any],
        proposal_payload: Mapping[str, Any],
        allowed_paths: Sequence[str] = (),
    ) -> MarshallerRunOutcome:
        return await self.execute(
            run_id=run_id,
            run_request_payload=run_request_payload,
            proposal_payloads=[proposal_payload],
            allowed_paths=allowed_paths,
        )

    async def execute(
        self,
        *,
        run_id: str,
        run_request_payload: Mapping[str, Any],
        proposal_payloads: Sequence[Mapping[str, Any]],
        allowed_paths: Sequence[str] = (),
    ) -> MarshallerRunOutcome:
        run_request = self._parse_run_request(run_request_payload)
        proposals = [dict(payload) for payload in proposal_payloads]
        if not proposals:
            raise ValueError("At least one proposal payload is required")

        artifacts = MarshallerArtifacts(self.workspace_root, run_id)
        await artifacts.ensure_layout()
        ledger = LedgerWriter(artifacts.run_root / "ledger.jsonl")
        started_at = datetime.now(UTC)

        run_json = {
            "run_contract_version": "marshaller.run.v0",
            "run_id": run_id,
            "created_at": started_at.isoformat(),
            "request": run_request.model_dump(mode="json"),
            "proposal_count": len(proposals),
        }
        await artifacts.write_run_json(run_json)
        await ledger.append(
            "run_started",
            {
                "run_id": run_id,
                "run_contract_version": run_json["run_contract_version"],
                "max_attempts": run_request.max_attempts,
                "proposal_count": len(proposals),
            },
        )

        runtime = AttemptRuntime(
            run_id=run_id,
            run_request=run_request,
            artifacts=artifacts,
            allowed_paths=allowed_paths,
        )
        limit = min(run_request.max_attempts, len(proposals))
        attempt_results: list[AttemptResult] = []
        accepted: AttemptResult | None = None
        for index, payload in enumerate(proposals[:limit], start=1):
            result = await runtime.execute_attempt(
                ledger=ledger,
                attempt_index=index,
                proposal_payload=payload,
            )
            attempt_results.append(result)
            if result.accept:
                accepted = result
                break

        duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        summary = build_run_summary(
            run_id=run_id,
            attempts=attempt_results,
            max_attempts=run_request.max_attempts,
            total_proposals_received=len(proposals),
            duration_ms=duration_ms,
        )
        triage = build_triage_payload(run_id=run_id, attempts=attempt_results)
        terminal = accepted if accepted is not None else attempt_results[-1]
        await ledger.append(
            "run_completed",
            {
                "run_id": run_id,
                "accept": summary["accepted"],
                "attempt_count": summary["attempt_count"],
                "accepted_attempt_index": summary["accepted_attempt_index"],
                "primary_rejection_code": terminal.primary_rejection_code,
            },
        )
        summary["run_root_digest"] = ledger.current_digest
        await artifacts.write_summary(summary)
        await artifacts.write_triage(triage)

        return MarshallerRunOutcome(
            run_id=run_id,
            accept=bool(summary["accepted"]),
            rejection_codes=() if terminal.accept else terminal.rejection_codes,
            primary_rejection_code=terminal.primary_rejection_code,
            run_root_digest=ledger.current_digest,
            run_path=str(artifacts.run_root),
            decision_path=terminal.decision_path,
            attempt_count=int(summary["attempt_count"]),
            accepted_attempt_index=summary["accepted_attempt_index"],
            summary_path=str(artifacts.run_root / "summary.json"),
        )

    @staticmethod
    def _parse_run_request(payload: Mapping[str, Any]) -> RunRequest:
        try:
            return RunRequest.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"{SCHEMA_INVALID}: {exc}") from exc
