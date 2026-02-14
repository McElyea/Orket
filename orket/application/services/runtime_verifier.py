from __future__ import annotations

import asyncio
import py_compile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class RuntimeVerificationResult:
    ok: bool
    checked_files: List[str]
    errors: List[str]


class RuntimeVerifier:
    """
    Deterministic runtime verification stage.

    Current baseline focuses on Python syntax/bytecode compilation checks
    for generated files in agent_output/.
    """

    def __init__(self, workspace_root: Path, organization: Any = None):
        self.workspace_root = workspace_root
        self.organization = organization

    async def verify(self) -> RuntimeVerificationResult:
        targets = await self._python_targets()
        if not targets:
            return RuntimeVerificationResult(ok=True, checked_files=[], errors=[])

        errors: List[str] = []
        checked_files: List[str] = []
        for target in targets:
            checked_files.append(str(target.relative_to(self.workspace_root)).replace("\\", "/"))
            try:
                await asyncio.to_thread(py_compile.compile, str(target), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(str(exc))

        return RuntimeVerificationResult(ok=not errors, checked_files=checked_files, errors=errors)

    async def _python_targets(self) -> List[Path]:
        root = self.workspace_root / "agent_output"
        exists = await asyncio.to_thread(root.exists)
        if not exists:
            return []
        files = await asyncio.to_thread(lambda: sorted([p for p in root.rglob("*.py") if p.is_file()]))
        return files

