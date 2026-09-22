"""Read-only registry observation. Invoke through an owned thread."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

side_effecting = False


@dataclass(frozen=True)
class PromptRegistryBytes:
    path: str
    content: bytes
    sha256: str


def read_prompt_registry(path: Path) -> PromptRegistryBytes:
    resolved = path.resolve()
    content = resolved.read_bytes()
    return PromptRegistryBytes(str(resolved), content, hashlib.sha256(content).hexdigest())
