from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import aiofiles

from orket.core.domain.sandbox_lifecycle import TerminalReason
from orket.runtime_paths import resolve_sandbox_terminal_evidence_root


class SandboxTerminalEvidenceService:
    """Exports terminal evidence outside sandbox-managed Docker resources."""

    def __init__(self, *, evidence_root: str | Path | None = None) -> None:
        self.evidence_root = resolve_sandbox_terminal_evidence_root(evidence_root)

    async def export(
        self,
        *,
        sandbox_id: str,
        terminal_reason: TerminalReason,
        created_at: str,
        payload: dict[str, object],
    ) -> str:
        path = self._evidence_path(
            sandbox_id=sandbox_id,
            terminal_reason=terminal_reason,
            created_at=created_at,
            payload=payload,
        )
        document = {
            "sandbox_id": sandbox_id,
            "terminal_reason": terminal_reason.value,
            "created_at": created_at,
            "payload": payload,
        }
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(document, indent=2, sort_keys=True))
        return str(path)

    def _evidence_path(
        self,
        *,
        sandbox_id: str,
        terminal_reason: TerminalReason,
        created_at: str,
        payload: dict[str, object],
    ) -> Path:
        digest = hashlib.sha256(
            json.dumps(
                {
                    "sandbox_id": sandbox_id,
                    "terminal_reason": terminal_reason.value,
                    "created_at": created_at,
                    "payload": payload,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return self.evidence_root / sandbox_id / f"{terminal_reason.value}-{digest[:16]}.json"
