"""Owned immutable interaction artifacts, with native admission and readback."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.file_admission import require_regular_or_absent
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.core.contracts.interaction_stream import validate_interaction_id


@dataclass(frozen=True)
class InteractionArtifactStore:
    side_effecting = True
    project_root: Path

    def __post_init__(self) -> None:
        if not self.project_root.is_absolute():
            raise ValueError("E_INTERACTION_ROOT_ABSOLUTE_REQUIRED")

    async def publish(self, session_id: str, turn_id: str, *, name: str, content: bytes) -> Path:
        validate_interaction_id(session_id)
        validate_interaction_id(turn_id)
        if name not in {"authority_commit.json", "interaction_trace.jsonl"}:
            raise ValueError("E_INTERACTION_ARTIFACT_NAME")
        captured = bytes(content)
        return await run_owned_thread(
            lambda: self._publish_sync(session_id, turn_id, name, captured), label="interaction-artifact",
        )

    def _publish_sync(self, session_id: str, turn_id: str, name: str, content: bytes) -> Path:
        root = self.project_root.resolve()
        directory = root / "workspace" / "interactions" / session_id / turn_id
        if not directory.resolve().is_relative_to(root):
            raise ValueError("E_INTERACTION_ARTIFACT_ESCAPE")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        require_regular_or_absent(target, error_code="E_INTERACTION_ARTIFACT_NOT_REGULAR")
        locks = NativeFileLocks(target, suffix=".owners", error_prefix="E_INTERACTION", empty_key_error="E_INTERACTION_KEY")
        with locks.hold_sync("publish"):
            require_regular_or_absent(target, error_code="E_INTERACTION_ARTIFACT_NOT_REGULAR")
            if target.exists():
                if target.read_bytes() != content:
                    raise ValueError("E_INTERACTION_ARTIFACT_CONFLICT")
                return target
            descriptor, temporary = tempfile.mkstemp(prefix=name + ".", suffix=".tmp", dir=directory)
            temporary = Path(temporary)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    if handle.write(content) != len(content):
                        raise OSError("E_INTERACTION_ARTIFACT_SHORT_WRITE")
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(target)
                if target.read_bytes() != content:
                    raise OSError("E_INTERACTION_ARTIFACT_UNVERIFIED")
            finally:
                temporary.unlink(missing_ok=True)
        return target
