"""Filesystem implementation for application-authorized structural board updates."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.core.domain.reconciler import ReconciliationWrite, StructuralAsset

side_effecting = True


class StructuralBoardStore:
    side_effecting = True

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    async def snapshot(self) -> tuple[StructuralAsset, ...]:
        return await run_owned_thread(self._snapshot_sync, label="structural-board-snapshot")

    async def apply(self, update: ReconciliationWrite) -> None:
        await run_owned_thread(lambda: self._apply_sync(update), label="structural-board-write")

    def _snapshot_sync(self) -> tuple[StructuralAsset, ...]:
        """Only invoked in the owned worker; traversal and reads never occupy the event loop."""
        root = self.root.resolve(strict=True)
        assets = []
        for department in sorted(root.iterdir()):
            if not department.is_dir():
                continue
            if not department.resolve(strict=True).is_relative_to(root):
                raise ValueError(f"Structural department is outside the model root: {department}")
            for kind in ("rocks", "epics", "issues"):
                directory = department / kind
                if not directory.exists():
                    continue
                if not directory.resolve(strict=True).is_relative_to(root):
                    raise ValueError(f"Structural directory is outside the model root: {directory}")
                for path in sorted(directory.glob("*.json")):
                    if not path.resolve(strict=True).is_relative_to(root):
                        raise ValueError(f"Structural asset is outside the model root: {path}")
                    assets.append(StructuralAsset(department.name, kind, path.stem, path.read_text(encoding="utf-8")))
        return tuple(assets)

    def _apply_sync(self, update: ReconciliationWrite) -> None:
        """An owned worker compares the snapshot, replaces one target and verifies its bytes."""
        root = self.root.resolve(strict=True)
        path = (root / update.relative_path).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError("Structural update is outside the model root")
        if path.read_text(encoding="utf-8") != update.expected_content:
            raise ValueError(f"Structural target changed after snapshot: {update.relative_path}")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(update.content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
            if path.read_text(encoding="utf-8") != update.content:
                raise OSError(f"Structural update did not verify: {update.relative_path}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
