from __future__ import annotations

import asyncio
import py_compile
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class RuntimeVerificationResult:
    ok: bool
    checked_files: List[str]
    errors: List[str]
    command_results: List[Dict[str, Any]]


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
        errors: List[str] = []
        checked_files: List[str] = []
        command_results: List[Dict[str, Any]] = []
        for target in targets:
            checked_files.append(str(target.relative_to(self.workspace_root)).replace("\\", "/"))
            try:
                await asyncio.to_thread(py_compile.compile, str(target), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(str(exc))

        commands = self._resolve_runtime_commands()
        timeout_sec = self._resolve_runtime_timeout_seconds()
        for command in commands:
            result = await asyncio.to_thread(self._run_command, command, timeout_sec)
            command_results.append(result)
            if result.get("returncode", 1) != 0:
                errors.append(
                    f"runtime command failed ({result.get('command_display')}): "
                    f"{(result.get('stderr') or result.get('stdout') or '').strip()[:240]}"
                )

        deployment_missing = await self._validate_deployment_artifacts_if_required()
        if deployment_missing:
            errors.append(
                "missing deployment artifacts: " + ", ".join(sorted(deployment_missing))
            )

        return RuntimeVerificationResult(
            ok=not errors,
            checked_files=checked_files,
            errors=errors,
            command_results=command_results,
        )

    async def _python_targets(self) -> List[Path]:
        root = self.workspace_root / "agent_output"
        exists = await asyncio.to_thread(root.exists)
        if not exists:
            return []
        files = await asyncio.to_thread(lambda: sorted([p for p in root.rglob("*.py") if p.is_file()]))
        return files

    def _resolve_runtime_commands(self) -> List[Any]:
        process_rules = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            process_rules = self.organization.process_rules
        raw = process_rules.get("runtime_verifier_commands") if process_rules else None
        if isinstance(raw, list):
            return [item for item in raw if item]
        return []

    def _resolve_runtime_timeout_seconds(self) -> int:
        process_rules = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            process_rules = self.organization.process_rules
        raw = process_rules.get("runtime_verifier_timeout_sec", 60)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 60

    async def _validate_deployment_artifacts_if_required(self) -> List[str]:
        process_rules = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            process_rules = self.organization.process_rules
        required = bool(process_rules.get("runtime_verifier_require_deployment_files", False))
        if not required:
            return []

        expected = process_rules.get(
            "runtime_verifier_required_deployment_files",
            [
                "agent_output/deployment/Dockerfile",
                "agent_output/deployment/docker-compose.yml",
            ],
        )
        if not isinstance(expected, list):
            return []
        missing: List[str] = []
        for rel_path in expected:
            if not str(rel_path).strip():
                continue
            exists = await asyncio.to_thread((self.workspace_root / str(rel_path)).is_file)
            if not exists:
                missing.append(str(rel_path))
        return missing

    def _run_command(self, command: Any, timeout_sec: int) -> Dict[str, Any]:
        if isinstance(command, list):
            cmd = [str(part) for part in command]
            display = " ".join(cmd)
            shell = False
        else:
            cmd = str(command)
            display = str(command)
            shell = True

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                shell=shell,
                check=False,
            )
            return {
                "command_display": display,
                "returncode": int(completed.returncode),
                "stdout": (completed.stdout or "")[:2000],
                "stderr": (completed.stderr or "")[:2000],
            }
        except subprocess.TimeoutExpired:
            return {
                "command_display": display,
                "returncode": 124,
                "stdout": "",
                "stderr": f"timeout after {timeout_sec}s",
            }
