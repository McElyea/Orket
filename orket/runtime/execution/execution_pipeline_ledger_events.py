from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.logging import log_event
from orket.runtime.protocol_receipt_materializer import materialize_protocol_receipts


class ExecutionPipelineLedgerEventsMixin:
    if TYPE_CHECKING:
        workspace: Path
        run_ledger: Any

    async def _record_packet1_emission_failure_at(
        self,
        *,
        run_id: str,
        stage: str,
        error_type: str,
        error: str,
        ledger: Any,
        workspace: Path,
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
        if hasattr(ledger, "append_event"):
            await _append_optional_event(
                ledger, session_id=str(run_id), kind="packet1_emission_failure",
                payload={"packet1_facts": payload["packet1_conformance"], **payload},
            )
        log_event("packet1_emission_failure", payload, workspace=workspace)

    async def _record_packet2_facts_at(
        self,
        *,
        run_id: str,
        packet2_facts: dict[str, Any],
        ledger: Any,
    ) -> None:
        captured_run_id = str(run_id)
        captured_facts = deepcopy(packet2_facts)
        if not hasattr(ledger, "append_event"):
            return
        await _append_optional_event(
            ledger, session_id=captured_run_id, kind="packet2_fact",
            payload={"packet2_facts": captured_facts},
        )

    async def _record_artifact_provenance_facts_at(
        self,
        *,
        run_id: str,
        artifact_provenance_facts: dict[str, Any],
        ledger: Any,
    ) -> None:
        captured_run_id = str(run_id)
        captured_facts = deepcopy(artifact_provenance_facts)
        if not hasattr(ledger, "append_event"):
            return
        await _append_optional_event(
            ledger, session_id=captured_run_id, kind="artifact_provenance_fact",
            payload={"artifact_provenance_facts": captured_facts},
        )

    async def _materialize_protocol_receipts(self, *, run_id: str) -> dict[str, Any] | None:
        ledger = self.run_ledger
        if not hasattr(ledger, "append_receipt"):
            return None
        if not hasattr(ledger, "append_event"):
            return None
        if not hasattr(ledger, "list_events"):
            return None
        workspace, = capture_file_roots([self.workspace])
        captured_run_id = str(run_id)
        try:
            summary = await materialize_protocol_receipts(
                workspace=workspace,
                session_id=captured_run_id,
                run_ledger=ledger,
            )
            if int(summary.get("source_receipts") or 0) > 0:
                log_event(
                    "protocol_receipts_materialized",
                    {
                        "run_id": captured_run_id,
                        **dict(summary),
                    },
                    workspace=workspace,
                )
            return summary
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
            log_event(
                "protocol_receipt_materialization_failed",
                {
                    "run_id": captured_run_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                workspace=workspace,
            )
            raise


async def _append_optional_event(
    ledger: Any, *, session_id: str, kind: str, payload: dict[str, Any],
) -> None:
    async def append() -> None:
        try:
            await ledger.append_event(session_id=session_id, kind=kind, payload=payload)
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
            return

    await run_owned_io(append, label=f"run-ledger-{kind}", preserve_failure=True)
