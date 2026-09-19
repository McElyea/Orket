"""Application authority for verified interaction commit and trace publication."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from orket.adapters.storage.interaction_artifact_store import InteractionArtifactStore
from orket.core.contracts.interaction_stream import CommitIntent


class CommitOrchestrator:
    def __init__(self, *, project_root: Path) -> None:
        self.store = InteractionArtifactStore(project_root)

    async def commit(self, *, session_id: str, turn_id: str, intents: list[CommitIntent]) -> dict:
        values = [intent.model_dump() for intent in intents]
        payload = {"session_id": session_id, "turn_id": turn_id, "intents": values}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        content = json.dumps({"authoritative": True, "commit_digest": digest, **payload}, indent=2, sort_keys=True)
        path = await self.store.publish(session_id, turn_id, name="authority_commit.json", content=content.encode("utf-8"))
        issues = [value["ref"][len("fail_closed:"):] for value in values
                  if value["type"] == "decision" and value["ref"].startswith("fail_closed:")]
        return {"authoritative": True, "commit_digest": digest, "commit_outcome": "fail_closed" if issues else "ok",
                "issues": issues, "artifact_refs": [str(path)], "commit_id": f"commit-{digest[:12]}"}

    async def trace(self, *, session_id: str, turn_id: str) -> None:
        payload = {"authoritative": False, "event": "turn_finalized", "turn_id": turn_id}
        await self.store.publish(session_id, turn_id, name="interaction_trace.jsonl",
                                 content=(json.dumps(payload) + "\n").encode("utf-8"))
