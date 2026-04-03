from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import aiofiles

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

    def __init__(
        self,
        workspace_root: Path,
        organization: Any = None,
        project_surface_profile: str | None = None,
        architecture_pattern: str | None = None,
        artifact_contract: Dict[str, Any] | None = None,
        issue_params: Dict[str, Any] | None = None,
    ):
        self.workspace_root = workspace_root
        self.organization = organization
        self.project_surface_profile = str(project_surface_profile or "").strip().lower()
        self.architecture_pattern = str(architecture_pattern or "").strip().lower()
        self.artifact_contract = dict(artifact_contract or {}) if isinstance(artifact_contract, dict) else {}
        self.issue_params = dict(issue_params or {}) if isinstance(issue_params, dict) else {}

    async def verify(self) -> RuntimeVerificationResult:
        targets = await self._python_targets()
        errors: List[str] = []
        checked_files: List[str] = []
        command_results: List[Dict[str, Any]] = []
        failure_breakdown: Dict[str, int] = {}
        for target in targets:
            checked_files.append(str(target.relative_to(self.workspace_root)).replace("\\", "/"))
            try:
                await self._check_python_syntax(target)
            except (SyntaxError, ValueError, OSError) as exc:
                failure_breakdown["python_compile"] = failure_breakdown.get("python_compile", 0) + 1
                errors.append(str(exc))

        command_plan = await self._resolve_runtime_command_plan()
        commands = command_plan.get("commands", [])
        policy_source = str(command_plan.get("source", "none"))
        timeout_sec = self._resolve_runtime_timeout_seconds()
        for command in commands:
            result = await self._run_command(command, timeout_sec, policy_source)
            command_results.append(result)
            if result.get("returncode", 1) != 0:
                failure_class = str(result.get("failure_class") or "command_failed")
                failure_breakdown[failure_class] = failure_breakdown.get(failure_class, 0) + 1
                errors.append(
                    f"runtime command failed [{failure_class}] ({result.get('command_display')}): "
                    f"{(result.get('stderr') or result.get('stdout') or '').strip()[:240]}"
                )

        await self._validate_stdout_contract(
            command_results=command_results,
            failure_breakdown=failure_breakdown,
            errors=errors,
        )

        deployment_missing = await self._validate_deployment_artifacts_if_required()
        if deployment_missing:
            failure_breakdown["deployment_missing"] = failure_breakdown.get("deployment_missing", 0) + 1
            errors.append("missing deployment artifacts: " + ", ".join(sorted(deployment_missing)))

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
            profile_stack = self._stack_profile_from_surface(
                self.project_surface_profile or str(process_rules.get("project_surface_profile", "unspecified"))
            )
            if profile_stack:
                stack_profile = profile_stack
            else:
                stack_profile = await self._infer_stack_profile()

        by_profile = process_rules.get("runtime_verifier_commands_by_profile")
        if isinstance(by_profile, dict):
            selected = by_profile.get(stack_profile)
            if isinstance(selected, list):
                return {
                    "commands": [item for item in selected if item],
                    "source": f"profile_policy:{stack_profile}",
                }
        default_commands = await self._default_commands_for_profile(stack_profile)
        if default_commands:
            return {
                "commands": default_commands,
                "source": f"profile_default:{stack_profile}",
            }
        return {
            "commands": [],
            "source": f"profile_default_none:{stack_profile}",
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

    async def _default_commands_for_profile(self, stack_profile: str) -> List[Any]:
        # Only Python-backed surfaces have a safe cross-platform builtin verifier command.
        agent_output_exists = await asyncio.to_thread((self.workspace_root / "agent_output").exists)
        commands: List[Any] = []
        if agent_output_exists and stack_profile in {"python", "polyglot"}:
            commands.append([sys.executable, "-m", "compileall", "-q", "agent_output"])
        entrypoint_command = self._default_entrypoint_command()
        if entrypoint_command is not None:
            commands.append(entrypoint_command)
        return commands

    async def _check_python_syntax(self, path: Path) -> None:
        async with aiofiles.open(path, mode="r", encoding="utf-8") as handle:
            source = await handle.read()
        await asyncio.to_thread(compile, source, str(path), "exec")

    def _resolve_runtime_timeout_seconds(self) -> int:
        process_rules = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            process_rules = self.organization.process_rules
        raw = process_rules.get("runtime_verifier_timeout_sec", 60)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 60

    def _default_entrypoint_command(self) -> List[str] | None:
        artifact_kind = str(self.artifact_contract.get("kind") or "").strip().lower()
        entrypoint_path = str(self.artifact_contract.get("entrypoint_path") or "").strip().replace("\\", "/")
        if artifact_kind != "app" or not entrypoint_path:
            return None
        if not entrypoint_path.lower().endswith(".py"):
            return None
        return [sys.executable, entrypoint_path]

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
        profile_stack = self._stack_profile_from_surface(
            self.project_surface_profile or str(process_rules.get("project_surface_profile", "unspecified"))
        )
        if profile_stack:
            return profile_stack
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

        architecture_pattern = (
            self.architecture_pattern or str(process_rules.get("architecture_forced_pattern", "")).strip().lower()
        )
        if architecture_pattern == "microservices":
            return [
                "agent_output/deployment/Dockerfile.api",
                "agent_output/deployment/Dockerfile.worker",
                "agent_output/deployment/docker-compose.yml",
            ]

        stack_profile = str(process_rules.get("runtime_verifier_stack_profile", "")).strip().lower()
        if stack_profile not in {"python", "node", "polyglot"}:
            stack_profile = (
                self._stack_profile_from_surface(
                    self.project_surface_profile or str(process_rules.get("project_surface_profile", "unspecified"))
                )
                or "python"
            )
        defaults = {
            "python": [
                "agent_output/deployment/Dockerfile",
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

    @staticmethod
    def _stack_profile_from_surface(project_surface_profile: str) -> str:
        profile = str(project_surface_profile or "").strip().lower()
        if profile in {"backend_only", "cli", "tui"}:
            return "python"
        if profile == "api_vue":
            return "polyglot"
        return ""

    async def _run_command(self, command: Any, timeout_sec: int, policy_source: str) -> Dict[str, Any]:
        if isinstance(command, list):
            cmd = [str(part) for part in command]
            display = " ".join(cmd)
        else:
            display = str(command)
            return {
                "command_display": display,
                "returncode": 126,
                "stdout": "",
                "stderr": "runtime verifier commands must be argv lists; shell strings are not allowed",
                "failure_class": "command_failed",
                "policy_source": policy_source,
            }

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.workspace_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
            except TimeoutError:
                process.kill()
                await process.communicate()
                return {
                    "command_display": display,
                    "returncode": 124,
                    "stdout": "",
                    "stderr": f"timeout after {timeout_sec}s",
                    "failure_class": "timeout",
                    "policy_source": policy_source,
                }
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return {
                "command_display": display,
                "returncode": int(process.returncode or 0),
                "stdout": stdout[:2000],
                "stderr": stderr[:2000],
                "failure_class": self._failure_class_from_returncode(int(process.returncode or 0)),
                "policy_source": policy_source,
            }
        except OSError as exc:
            return {
                "command_display": display,
                "returncode": 127,
                "stdout": "",
                "stderr": str(exc),
                "failure_class": "missing_runtime",
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

    def _resolve_stdout_contract(self) -> Dict[str, Any]:
        raw = self.issue_params.get("runtime_verifier")
        payload = dict(raw or {}) if isinstance(raw, dict) else {}
        expect_json_stdout = bool(payload.get("expect_json_stdout", False))
        raw_assertions = payload.get("json_assertions")
        json_assertions = [dict(item) for item in raw_assertions if isinstance(item, dict)] if isinstance(raw_assertions, list) else []
        return {
            "expect_json_stdout": expect_json_stdout,
            "json_assertions": json_assertions,
        }

    async def _validate_stdout_contract(
        self,
        *,
        command_results: List[Dict[str, Any]],
        failure_breakdown: Dict[str, int],
        errors: List[str],
    ) -> None:
        contract = self._resolve_stdout_contract()
        expect_json_stdout = bool(contract.get("expect_json_stdout"))
        json_assertions = list(contract.get("json_assertions") or [])
        if not expect_json_stdout and not json_assertions:
            return
        if not command_results:
            failure_breakdown["command_failed"] = failure_breakdown.get("command_failed", 0) + 1
            errors.append("runtime stdout contract requested but no runtime commands were executed")
            return

        last_result = command_results[-1]
        if int(last_result.get("returncode", 1)) != 0:
            return

        stdout = str(last_result.get("stdout") or "").strip()
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            failure_breakdown["command_failed"] = failure_breakdown.get("command_failed", 0) + 1
            errors.append(f"runtime stdout JSON parse failed: {exc.msg}")
            last_result["stdout_contract_ok"] = False
            last_result["stdout_contract_error"] = "json_parse_failed"
            return

        last_result["stdout_json"] = parsed
        assertion_failures = self._json_assertion_failures(parsed, json_assertions)
        if assertion_failures:
            failure_breakdown["command_failed"] = failure_breakdown.get("command_failed", 0) + 1
            errors.extend(assertion_failures)
            last_result["stdout_contract_ok"] = False
            last_result["stdout_assertion_failures"] = assertion_failures
            return

        last_result["stdout_contract_ok"] = True

    def _json_assertion_failures(self, payload: Any, assertions: List[Dict[str, Any]]) -> List[str]:
        failures: List[str] = []
        for assertion in assertions:
            path = str(assertion.get("path") or "").strip()
            op = str(assertion.get("op") or "").strip().lower()
            expected = assertion.get("value")
            if not path or not op:
                failures.append("runtime stdout assertion missing path or op")
                continue
            try:
                actual = self._resolve_json_path(payload, path)
            except KeyError:
                failures.append(f"runtime stdout assertion path missing: {path}")
                continue
            if not self._json_assertion_matches(actual=actual, op=op, expected=expected):
                failures.append(
                    f"runtime stdout assertion failed: path={path} op={op} expected={expected!r} actual={actual!r}"
                )
        return failures

    @staticmethod
    def _resolve_json_path(payload: Any, path: str) -> Any:
        current = payload
        for token in [segment for segment in str(path).split(".") if segment]:
            if isinstance(current, dict) and token in current:
                current = current[token]
                continue
            if isinstance(current, list):
                try:
                    index = int(token)
                except ValueError as exc:
                    raise KeyError(path) from exc
                if index < 0 or index >= len(current):
                    raise KeyError(path)
                current = current[index]
                continue
            raise KeyError(path)
        return current

    @staticmethod
    def _json_assertion_matches(*, actual: Any, op: str, expected: Any) -> bool:
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "contains":
            if isinstance(actual, str):
                return str(expected) in actual
            if isinstance(actual, list):
                return expected in actual
            return False
        if op == "len_gte":
            try:
                return len(actual) >= int(expected)
            except (TypeError, ValueError):
                return False
        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return False
        if op == "gt":
            return actual_num > expected_num
        if op == "gte":
            return actual_num >= expected_num
        if op == "lt":
            return actual_num < expected_num
        if op == "lte":
            return actual_num <= expected_num
        return False


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
