from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from orket.core.domain.guard_contract import GuardContract, GuardViolation

@dataclass(frozen=True)
class RuntimeVerificationResult:
    ok: bool
    checked_files: List[str]
    errors: List[str]
    command_results: List[Dict[str, Any]]
    failure_breakdown: Dict[str, int]
    guard_contract: GuardContract


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
        failure_breakdown: Dict[str, int] = {}
        for target in targets:
            checked_files.append(str(target.relative_to(self.workspace_root)).replace("\\", "/"))
            try:
                await asyncio.to_thread(self._check_python_syntax, target)
            except (SyntaxError, ValueError, OSError) as exc:
                failure_breakdown["python_compile"] = failure_breakdown.get("python_compile", 0) + 1
                errors.append(str(exc))

        command_plan = await self._resolve_runtime_command_plan()
        commands = command_plan.get("commands", [])
        policy_source = str(command_plan.get("source", "none"))
        timeout_sec = self._resolve_runtime_timeout_seconds()
        for command in commands:
            result = await asyncio.to_thread(self._run_command, command, timeout_sec, policy_source)
            command_results.append(result)
            if result.get("returncode", 1) != 0:
                failure_class = str(result.get("failure_class") or "command_failed")
                failure_breakdown[failure_class] = failure_breakdown.get(failure_class, 0) + 1
                errors.append(
                    f"runtime command failed [{failure_class}] ({result.get('command_display')}): "
                    f"{(result.get('stderr') or result.get('stdout') or '').strip()[:240]}"
                )

        deployment_missing = await self._validate_deployment_artifacts_if_required()
        if deployment_missing:
            failure_breakdown["deployment_missing"] = failure_breakdown.get("deployment_missing", 0) + 1
            errors.append(
                "missing deployment artifacts: " + ", ".join(sorted(deployment_missing))
            )

        guard_contract = build_runtime_guard_contract(ok=not errors, errors=errors)
        return RuntimeVerificationResult(
            ok=not errors,
            checked_files=checked_files,
            errors=errors,
            command_results=command_results,
            failure_breakdown=failure_breakdown,
            guard_contract=guard_contract,
        )

    async def _python_targets(self) -> List[Path]:
        root = self.workspace_root / "agent_output"
        exists = await asyncio.to_thread(root.exists)
        if not exists:
            return []
        files = await asyncio.to_thread(lambda: sorted([p for p in root.rglob("*.py") if p.is_file()]))
        return files

    async def _resolve_runtime_command_plan(self) -> Dict[str, Any]:
        process_rules = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            process_rules = self.organization.process_rules
        raw = process_rules.get("runtime_verifier_commands") if process_rules else None
        if isinstance(raw, list):
            return {"commands": [item for item in raw if item], "source": "policy_override"}

        stack_profile = str(process_rules.get("runtime_verifier_stack_profile", "")).strip().lower()
        if stack_profile not in {"python", "node", "polyglot"}:
            stack_profile = await self._infer_stack_profile()

        by_profile = process_rules.get("runtime_verifier_commands_by_profile")
        if isinstance(by_profile, dict):
            selected = by_profile.get(stack_profile)
            if isinstance(selected, list):
                return {
                    "commands": [item for item in selected if item],
                    "source": f"profile_policy:{stack_profile}",
                }
        return {
            "commands": self._default_commands_for_profile(stack_profile),
            "source": f"profile_default:{stack_profile}",
        }

    async def _infer_stack_profile(self) -> str:
        deps_root = self.workspace_root / "agent_output" / "dependencies"
        has_pyproject = await asyncio.to_thread((deps_root / "pyproject.toml").is_file)
        has_requirements = await asyncio.to_thread((deps_root / "requirements.txt").is_file)
        has_package_json = await asyncio.to_thread((deps_root / "package.json").is_file)
        if (has_pyproject or has_requirements) and has_package_json:
            return "polyglot"
        if has_package_json:
            return "node"
        return "python"

    @staticmethod
    def _default_commands_for_profile(stack_profile: str) -> List[Any]:
        if stack_profile in {"python", "polyglot"}:
            return []
        return []

    @staticmethod
    def _check_python_syntax(path: Path) -> None:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")

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

        expected = self._resolve_expected_deployment_files(process_rules)
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

    async def _resolve_stack_profile(self, process_rules: Dict[str, Any]) -> str:
        stack_profile = str(process_rules.get("runtime_verifier_stack_profile", "")).strip().lower()
        if stack_profile in {"python", "node", "polyglot"}:
            return stack_profile
        return await self._infer_stack_profile()

    def _resolve_expected_deployment_files(self, process_rules: Dict[str, Any]) -> List[str]:
        explicit = process_rules.get("runtime_verifier_required_deployment_files")
        if isinstance(explicit, list):
            return [str(item).strip() for item in explicit if str(item).strip()]

        planner_required = process_rules.get("deployment_planner_required_files")
        if isinstance(planner_required, dict):
            inferred = [str(path).strip() for path in planner_required.keys() if str(path).strip()]
            if inferred:
                return inferred

        stack_profile = str(process_rules.get("runtime_verifier_stack_profile", "python")).strip().lower()
        defaults = {
            "python": [
                "agent_output/deployment/Dockerfile",
                "agent_output/deployment/docker-compose.yml",
            ],
            "node": [
                "agent_output/deployment/Dockerfile",
                "agent_output/deployment/docker-compose.yml",
            ],
            "polyglot": [
                "agent_output/deployment/Dockerfile",
                "agent_output/deployment/docker-compose.yml",
            ],
        }
        return list(defaults.get(stack_profile, defaults["python"]))

    def _run_command(self, command: Any, timeout_sec: int, policy_source: str) -> Dict[str, Any]:
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
                "failure_class": self._failure_class_from_returncode(int(completed.returncode)),
                "policy_source": policy_source,
            }
        except subprocess.TimeoutExpired:
            return {
                "command_display": display,
                "returncode": 124,
                "stdout": "",
                "stderr": f"timeout after {timeout_sec}s",
                "failure_class": "timeout",
                "policy_source": policy_source,
            }

    @staticmethod
    def _failure_class_from_returncode(returncode: int) -> str:
        if returncode == 0:
            return "none"
        if returncode == 124:
            return "timeout"
        if returncode in {126, 127}:
            return "missing_runtime"
        return "command_failed"


def build_runtime_guard_contract(*, ok: bool, errors: List[str]) -> GuardContract:
    if ok:
        return GuardContract(
            result="pass",
            violations=[],
            severity="soft",
            fix_hint=None,
            terminal_failure=False,
            terminal_reason=None,
        )

    return GuardContract(
        result="fail",
        violations=[
            GuardViolation(
                rule_id="RUNTIME_VERIFIER.FAIL",
                code="RUNTIME_VERIFIER_FAILED",
                message="Runtime verification checks failed.",
                location="output",
                severity="strict",
                evidence=(errors[0][:240] if errors else None),
            )
        ],
        severity="strict",
        fix_hint="Fix runtime verification failures and rerun.",
        terminal_failure=False,
        terminal_reason=None,
    )
