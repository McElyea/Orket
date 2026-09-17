"""Host-local ownership identity; this is not a remote-effect or containment claim."""
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol


class LocalFileLockError(ValueError):
    """A cooperating caller cannot acquire the selected native file identity."""


@dataclass(frozen=True)
class LocalFileLockRef:
    root_path: str
    lock_path: str
    device: int
    inode: int


class LocalFileLocks(Protocol):
    def hold(self, key: str) -> AbstractAsyncContextManager[LocalFileLockRef]: ...
