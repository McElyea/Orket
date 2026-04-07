from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.logging import log_event
from orket.runtime.protocol_receipt_materializer import materialize_protocol_receipts


class ExecutionPipelineLedgerEventsMixin:
    if TYPE_CHECKING:
        workspace: Path
        run_ledger: Any

    async def _record_packet1_emission_failure(
        self,
        *,
        run_id: str,
        stage: str,
        error_type: str,
        error: str,
    ) -> None:
        payload = {
            "session_id": str(run_id),
            "run_id": str(run_id),
            "stage": str(stage),
            "error_type": str(error_type),
            "error": str(error),
            "packet1_conformance": {
                "status": "non_conformant",
                "reasons": ["packet1_emission_failure"],
            },
        }
        if hasattr(self.run_ledger, "append_event"):
            with contextlib.suppress(RuntimeError, ValueError, TypeError, OSError, AttributeError):
                await self.run_ledger.append_event(
                    session_id=str(run_id),
                    kind="packet1_emission_failure",
                    payload={"packet1_facts": payload["packet1_conformance"], **payload},
                )
        log_event("packet1_emission_failure", payload, workspace=self.workspace)

    async def _record_packet2_facts(
        self,
        *,
        run_id: str,
        packet2_facts: dict[str, Any],
    ) -> None:
        if not hasattr(self.run_ledger, "append_event"):
            return
        try:
            await self.run_ledger.append_event(
                session_id=str(run_id),
                kind="packet2_fact",
                payload={"packet2_facts": dict(packet2_facts)},
            )
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
            return

    async def _record_artifact_provenance_facts(
        self,
        *,
        run_id: str,
        artifact_provenance_facts: dict[str, Any],
    ) -> None:
        if not hasattr(self.run_ledger, "append_event"):
            return
        try:
            await self.run_ledger.append_event(
                session_id=str(run_id),
                kind="artifact_provenance_fact",
                payload={"artifact_provenance_facts": dict(artifact_provenance_facts)},
            )
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
            return

    async def _materialize_protocol_receipts(self, *, run_id: str) -> dict[str, Any] | None:
        if not hasattr(self.run_ledger, "append_receipt"):
            return None
        if not hasattr(self.run_ledger, "append_event"):
            return None
        if not hasattr(self.run_ledger, "list_events"):
            return None
        try:
            summary = await materialize_protocol_receipts(
                workspace=self.workspace,
                session_id=str(run_id),
                run_ledger=self.run_ledger,
            )
            if int(summary.get("source_receipts") or 0) > 0:
                log_event(
                    "protocol_receipts_materialized",
                    {
                        "run_id": str(run_id),
                        **dict(summary),
                    },
                    workspace=self.workspace,
                )
            return summary
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
            log_event(
                "protocol_receipt_materialization_failed",
                {
                    "run_id": str(run_id),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                workspace=self.workspace,
            )
            return None
