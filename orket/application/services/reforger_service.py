"""Application compiler admission with captured inputs and retained worker lifetime."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.application.services.reforger_command import ReforgerCommand


@dataclass(frozen=True)
class ReforgerService:
    workspace_root: Path
    references: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        root, references = Path(self.workspace_root), tuple(Path(p) for p in self.references)
        if not all(p.is_absolute() for p in (root, *references)):
            raise ValueError("REFORGER_ROOTS_MUST_BE_ABSOLUTE")
        object.__setattr__(self, "workspace_root", root)
        object.__setattr__(self, "references", references)

    async def inspect(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._execute("inspect", args)

    async def run(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._execute("run", args)

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        captured, root, references = deepcopy(args), self.workspace_root, self.references

        def operation():
            worker = ReforgerCommand(root.resolve(), [p.resolve() for p in references])
            locks = NativeFileLocks(root, suffix=".reforger-locks", error_prefix="REFORGER",
                                    empty_key_error="REFORGER_LOCK_KEY")
            with locks.hold_sync("workspace"):
                return worker.inspect(captured) if command == "inspect" else worker.run(captured)

        return await run_owned_thread(operation, label="reforger-" + command)
