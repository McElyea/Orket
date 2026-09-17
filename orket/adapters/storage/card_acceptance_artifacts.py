"""Capture declared artifact bytes using the existing no-follow host handles."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

MAX_ARTIFACT_BYTES = 1_048_576
MAX_SNAPSHOT_BYTES = 8_388_608


@dataclass(frozen=True)
class CapturedCardArtifact:
    path: str
    content: bytes

    @property
    def manifest_entry(self) -> dict[str, str | int]:
        return {"path": self.path, "sha256": hashlib.sha256(self.content).hexdigest(), "size_bytes": len(self.content)}


class CardAcceptanceArtifacts:
    side_effecting = True

    async def capture(self, root: Path, paths: tuple[str, ...]) -> tuple[CapturedCardArtifact, ...]:
        return await asyncio.to_thread(_capture, root, paths)

    async def materialize(self, root: Path, artifacts: tuple[CapturedCardArtifact, ...]) -> None:
        await asyncio.to_thread(_materialize, root, artifacts)


def artifact_manifest_digest(artifacts: tuple[CapturedCardArtifact, ...]) -> str:
    manifest = [artifact.manifest_entry for artifact in sorted(artifacts, key=lambda item: item.path)]
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _target_opener():
    if os.name == "nt":
        from orket.adapters.storage.bound_filesystem_windows import open_target
    elif os.name == "posix":
        from orket.adapters.storage.bound_filesystem_posix import open_target
    else:
        raise RuntimeError("E_CARD_ACCEPTANCE_HOST_UNSUPPORTED")
    return open_target


def _capture(root: Path, paths: tuple[str, ...]) -> tuple[CapturedCardArtifact, ...]:
    open_target = _target_opener()
    root = root.resolve()
    artifacts: list[CapturedCardArtifact] = []
    total = 0
    for path in sorted(paths):
        requested = root / path
        target = requested.resolve()
        if not target.is_relative_to(root) or target == root:
            raise ValueError("E_CARD_ACCEPTANCE_ARTIFACT_ESCAPE")
        with (open_target(root, target, requested, operation="read_file") as (descriptor, _delete),
              os.fdopen(os.dup(descriptor), "rb") as stream):
            content = stream.read(MAX_ARTIFACT_BYTES + 1)
        total += len(content)
        if len(content) > MAX_ARTIFACT_BYTES or total > MAX_SNAPSHOT_BYTES:
            raise ValueError("E_CARD_ACCEPTANCE_ARTIFACT_LIMIT")
        artifacts.append(CapturedCardArtifact(path=path, content=content))
    return tuple(artifacts)


def _materialize(root: Path, artifacts: tuple[CapturedCardArtifact, ...]) -> None:
    root = root.resolve()
    open_target = _target_opener()
    for artifact in artifacts:
        target = root / artifact.path
        if not target.resolve().is_relative_to(root):
            raise ValueError("E_CARD_ACCEPTANCE_ARTIFACT_ESCAPE")
        with open_target(root, target, target, operation="write_file") as (descriptor, _delete):
            os.ftruncate(descriptor, 0)
            with os.fdopen(os.dup(descriptor), "wb") as stream:
                stream.write(artifact.content)
