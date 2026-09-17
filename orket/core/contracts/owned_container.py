"""Container lifetime is distinct from the lifetime of its Docker CLI clients."""
from __future__ import annotations

from dataclasses import dataclass

from orket.core.contracts.owned_command import OwnedCommandResult


@dataclass(frozen=True)
class OwnedContainerResult:
    name: str
    owner_id: str
    container_id: str | None
    returncode: int | None
    reason: str
    cleanup_confirmed: bool
    attached: OwnedCommandResult | None
    commands: tuple[dict, ...]
    diagnostics: tuple[str, ...]

    @property
    def stdout(self) -> bytes:
        return self.attached.stdout if self.attached else b""

    @property
    def stderr(self) -> bytes:
        return self.attached.stderr if self.attached else b""

    @property
    def capture_complete(self) -> bool:
        return self.attached is not None and self.attached.capture_complete

    def lifetime(self) -> dict:
        return {"schema_version": "owned_container.v1", "name": self.name, "owner_id": self.owner_id,
                "container_id": self.container_id, "exit_code": self.returncode, "reason": self.reason,
                "cleanup_confirmed": self.cleanup_confirmed, "capture_complete": self.capture_complete,
                "commands": list(self.commands), "diagnostics": list(self.diagnostics)}
