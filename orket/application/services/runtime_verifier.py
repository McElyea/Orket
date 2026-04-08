from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiofiles

from orket.core.domain.guard_contract import GuardContract, GuardViolation
from orket.application.services.runtime_verifier_evidence import annotate_runtime_verifier_evidence

_COMMAND_OUTPUT_LIMIT = 2000
_COMMAND_FAILURE_SUMMARY_LIMIT = 240
_KNOWN_JSON_ASSERTION_OPS = {"eq", "ne", "contains", "len_gte", "gt", "gte", "lt", "lte"}


@dataclass(frozen=True)
class RuntimeVerificationResult:
    ok: bool
    checked_files: list[str]
    errors: list[str]
    command_results: list[dict[str, Any]]
    failure_breakdown: dict[str, int]
    overall_evidence_class: str
    evidence_summary: dict[str, Any]
    guard_contract: GuardContract


class RuntimeVerifier:
    """
    Deterministic runtime verification stage.

    Baseline verification always checks Python syntax for generated files in
    agent_output/ and may execute additional configured runtime commands.
    """

    def __init__(
        self,
        workspace_root: Path,
        organization: Any = None,
        project_surface_profile: str | None = None,
        architecture_pattern: str | None = None,
        artifact_contract: dict[str, Any] | None = None,
        issue_params: dict[str, Any] | None = None,
    ):
        self.workspace_root = workspace_root
        self.organization = organization
        self.project_surface_profile = str(project_surface_profile or "").strip().lower()
        self.architecture_pattern = str(architecture_pattern or "").strip().lower()
        self.artifact_contract = dict(artifact_contract or {}) if isinstance(artifact_contract, dict) else {}
        self.issue_params = dict(issue_params or {}) if isinstance(issue_params, dict) else {}

    async def verify(self) -> RuntimeVerificationResult:
        targets = await self._python_targets()
        errors: list[str] = []
        checked_files: list[str] = []
        command_results: list[dict[str, Any]] = []
        failure_breakdown: dict[str, int] = {}
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
        stdout_contract = self._resolve_stdout_contract()
        for index, command in enumerate(commands, start=1):
            result = await self._run_command(command, timeout_sec, policy_source)
            result["command_id"] = f"command:{index:03d}"
            command_results.append(result)
            if result.get("returncode", 1) != 0:
                failure_class = str(result.get("failure_class") or "command_failed")
                failure_breakdown[failure_class] = failure_breakdown.get(failure_class, 0) + 1
                errors.append(
                    f"runtime command failed [{failure_class}] cwd={result.get('working_directory')}: "
                    f"{self._summarize_command_failure(result)}"
                )

        await self._validate_stdout_contract(
            command_results=command_results,
            failure_breakdown=failure_breakdown,
            errors=errors,
            contract=stdout_contract,
        )
        command_results, overall_evidence_class, evidence_summary = annotate_runtime_verifier_evidence(
            checked_files=checked_files,
            command_results=command_results,
            stdout_contract=stdout_contract,
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
            overall_evidence_class=overall_evidence_class,
            evidence_summary=evidence_summary,
            guard_contract=guard_contract,
        )

    async def _python_targets(self) -> list[Path]:
        root = self.workspace_root / "agent_output"
        exists = await asyncio.to_thread(root.exists)
        if not exists:
            return []
        files = await asyncio.to_thread(lambda: sorted([p for p in root.rglob("*.py") if p.is_file()]))
        return files

    async def _resolve_runtime_command_plan(self) -> dict[str, Any]:
        issue_commands = self._issue_runtime_verifier_commands()
        if issue_commands:
            return {"commands": issue_commands, "source": "issue_override"}

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

    def _issue_runtime_verifier_commands(self) -> list[Any]:
        runtime_verifier = self.issue_params.get("runtime_verifier")
        if not isinstance(runtime_verifier, dict):
            return []
        commands = runtime_verifier.get("commands")
        if not isinstance(commands, list):
            return []
        return [item for item in commands if item]

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

    async def _default_commands_for_profile(self, stack_profile: str) -> list[Any]:
        # Only Python-backed surfaces have a safe cross-platform builtin verifier command.
        agent_output_exists = await asyncio.to_thread((self.workspace_root / "agent_output").exists)
        commands: list[Any] = []
        if agent_output_exists and stack_profile in {"python", "polyglot"}:
            commands.append(["python", "-m", "compileall", "-q", "agent_output"])
        entrypoint_command = self._default_entrypoint_command()
        if entrypoint_command is not None:
            commands.append(entrypoint_command)
        return commands

    async def _check_python_syntax(self, path: Path) -> None:
        async with aiofiles.open(path, encoding="utf-8") as handle:
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

    def _default_entrypoint_command(self) -> list[str] | None:
        artifact_kind = str(self.artifact_contract.get("kind") or "").strip().lower()
        entrypoint_path = str(self.artifact_contract.get("entrypoint_path") or "").strip().replace("\\", "/")
        if artifact_kind != "app" or not entrypoint_path:
            return None
        if not entrypoint_path.lower().endswith(".py"):
            return None
        return ["python", entrypoint_path]

    async def _validate_deployment_artifacts_if_required(self) -> list[str]:
        process_rules = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            process_rules = self.organization.process_rules
        required = bool(process_rules.get("runtime_verifier_require_deployment_files", False))
        if not required:
            return []

        expected = self._resolve_expected_deployment_files(process_rules)
        if not isinstance(expected, list):
            return []
        missing: list[str] = []
        for rel_path in expected:
            if not str(rel_path).strip():
                continue
            exists = await asyncio.to_thread((self.workspace_root / str(rel_path)).is_file)
            if not exists:
                missing.append(str(rel_path))
        return missing

    async def _resolve_stack_profile(self, process_rules: dict[str, Any]) -> str:
        stack_profile = str(process_rules.get("runtime_verifier_stack_profile", "")).strip().lower()
        if stack_profile in {"python", "node", "polyglot"}:
            return stack_profile
        profile_stack = self._stack_profile_from_surface(
            self.project_surface_profile or str(process_rules.get("project_surface_profile", "unspecified"))
        )
        if profile_stack:
            return profile_stack
        return await self._infer_stack_profile()

    def _resolve_expected_deployment_files(self, process_rules: dict[str, Any]) -> list[str]:
        explicit = process_rules.get("runtime_verifier_required_deployment_files")
        if isinstance(explicit, list):
            return [str(item).strip() for item in explicit if str(item).strip()]

        planner_required = process_rules.get("deployment_planner_required_files")
        if isinstance(planner_required, dict):
            inferred = [str(path).strip() for path in planner_required if str(path).strip()]
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

    async def _run_command(self, command: Any, timeout_sec: int, policy_source: str) -> dict[str, Any]:
        parsed = await self._parse_runtime_command(command)
        if parsed.get("invalid"):
            display = str(parsed.get("command_text") or parsed.get("command_display") or command)
            return {
                "command_text": display,
                "command_display": display,
                "working_directory": str(parsed.get("working_directory") or "."),
                "returncode": 126,
                "exit_code": 126,
                "outcome": "fail",
                "stdout": "",
                "stderr": str(parsed.get("error") or "runtime verifier commands must be argv lists; shell strings are not allowed"),
                "failure_class": "command_failed",
                "policy_source": policy_source,
            }
        cmd = list(parsed["argv"])
        display = str(parsed["command_text"])
        working_directory = str(parsed["working_directory"])
        resolved_cwd = parsed["resolved_cwd"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(resolved_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
            except TimeoutError:
                process.kill()
                await process.communicate()
                return {
                    "command_text": display,
                    "command_display": display,
                    "working_directory": working_directory,
                    "returncode": 124,
                    "exit_code": 124,
                    "outcome": "fail",
                    "stdout": "",
                    "stderr": f"timeout after {timeout_sec}s",
                    "failure_class": "timeout",
                    "policy_source": policy_source,
                }
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            rc = process.returncode
            returncode = int(rc) if rc is not None else -1
            return {
                "command_text": display,
                "command_display": display,
                "working_directory": working_directory,
                "returncode": returncode,
                "exit_code": returncode,
                "outcome": "pass" if returncode == 0 else "fail",
                "stdout": self._clip_runtime_stream(stdout),
                "stderr": self._clip_runtime_stream(stderr, preserve_tail=True),
                "failure_class": self._failure_class_from_returncode(returncode),
                "policy_source": policy_source,
            }
        except OSError as exc:
            return {
                "command_text": display,
                "command_display": display,
                "working_directory": working_directory,
                "returncode": 127,
                "exit_code": 127,
                "outcome": "fail",
                "stdout": "",
                "stderr": str(exc),
                "failure_class": "missing_runtime",
                "policy_source": policy_source,
            }

    async def _parse_runtime_command(self, command: Any) -> dict[str, Any]:
        declared_cwd = "."
        raw_argv = command
        if isinstance(command, dict):
            raw_argv = command.get("argv")
            declared_cwd = str(command.get("cwd") or ".").strip() or "."
        if not isinstance(raw_argv, list):
            return {
                "invalid": True,
                "command_text": str(command),
                "working_directory": declared_cwd,
                "error": "runtime verifier commands must be argv lists or {argv, cwd} objects; shell strings are not allowed",
            }
        argv = [str(part).strip() for part in raw_argv if str(part).strip()]
        if not argv:
            return {
                "invalid": True,
                "command_text": "",
                "working_directory": declared_cwd,
                "error": "runtime verifier command argv cannot be empty",
            }

        command_text = self._display_command(argv)
        workspace_root = await asyncio.to_thread(self.workspace_root.resolve)
        resolved_cwd = await asyncio.to_thread(self._resolve_command_cwd, declared_cwd, workspace_root)
        if resolved_cwd is None:
            return {
                "invalid": True,
                "command_text": command_text,
                "working_directory": declared_cwd.replace("\\", "/"),
                "error": f"runtime verifier cwd escapes workspace: {declared_cwd}",
            }
        cwd_exists = await asyncio.to_thread(resolved_cwd.is_dir)
        working_directory = "." if resolved_cwd == workspace_root else str(resolved_cwd.relative_to(workspace_root)).replace("\\", "/")
        if not cwd_exists:
            return {
                "invalid": True,
                "command_text": command_text,
                "working_directory": working_directory,
                "error": f"runtime verifier cwd not found: {working_directory}",
            }

        executable_argv = list(argv)
        if executable_argv[0].lower() == "python":
            executable_argv[0] = sys.executable
        return {
            "invalid": False,
            "argv": executable_argv,
            "command_text": command_text,
            "working_directory": working_directory,
            "resolved_cwd": resolved_cwd,
        }

    @staticmethod
    def _display_command(argv: list[str]) -> str:
        display = list(argv)
        if display and Path(display[0]).name.lower().startswith("python"):
            display[0] = "python"
        return " ".join(display)

    @staticmethod
    def _clip_runtime_stream(text: str, *, preserve_tail: bool = False) -> str:
        normalized = str(text or "")
        if len(normalized) <= _COMMAND_OUTPUT_LIMIT:
            return normalized
        if not preserve_tail:
            return normalized[:_COMMAND_OUTPUT_LIMIT]

        head_limit = 400
        tail_limit = _COMMAND_OUTPUT_LIMIT - head_limit - 32
        truncated = len(normalized) - head_limit - tail_limit
        return (
            normalized[:head_limit]
            + f"\n...[truncated {truncated} chars]...\n"
            + normalized[-tail_limit:]
        )

    @staticmethod
    def _summarize_command_failure(result: dict[str, Any]) -> str:
        details = str(result.get("stderr") or result.get("stdout") or "").strip()
        if not details:
            return "command exited non-zero with no captured output"

        lines = [line.strip() for line in details.splitlines() if line.strip()]
        summary = " | ".join(lines[-3:]) if lines else details
        if len(summary) <= _COMMAND_FAILURE_SUMMARY_LIMIT:
            return summary
        return "..." + summary[-(_COMMAND_FAILURE_SUMMARY_LIMIT - 3) :]

    @staticmethod
    def _resolve_command_cwd(raw_cwd: str, workspace_root: Path) -> Path | None:
        workspace_root = workspace_root.resolve()
        token = str(raw_cwd or ".").strip() or "."
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = workspace_root / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(workspace_root):
            return None
        return resolved

    @staticmethod
    def _failure_class_from_returncode(returncode: int) -> str:
        if returncode == 0:
            return "none"
        if returncode == 137:
            return "oom_killed"
        if returncode == 124:
            return "timeout"
        if returncode in {126, 127}:
            return "missing_runtime"
        return "command_failed"

    def _resolve_stdout_contract(self) -> dict[str, Any]:
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
        command_results: list[dict[str, Any]],
        failure_breakdown: dict[str, int],
        errors: list[str],
        contract: dict[str, Any] | None = None,
    ) -> None:
        contract = dict(contract or self._resolve_stdout_contract())
        expect_json_stdout = bool(contract.get("expect_json_stdout"))
        json_assertions = list(contract.get("json_assertions") or [])
        if not expect_json_stdout and not json_assertions:
            return
        if not command_results:
            failure_breakdown["stdout_contract_missing"] = failure_breakdown.get("stdout_contract_missing", 0) + 1
            errors.append("runtime stdout contract requested but no runtime commands were executed")
            return

        last_result = command_results[-1]
        if int(last_result.get("returncode", 1)) != 0:
            return

        stdout = str(last_result.get("stdout") or "").strip()
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            failure_breakdown["stdout_json_parse_failed"] = failure_breakdown.get("stdout_json_parse_failed", 0) + 1
            errors.append(f"runtime stdout JSON parse failed: {exc.msg}")
            last_result["outcome"] = "fail"
            last_result["failure_class"] = "stdout_json_parse_failed"
            last_result["stdout_contract_ok"] = False
            last_result["stdout_contract_error"] = "json_parse_failed"
            return

        last_result["stdout_json"] = parsed
        assertion_failures = self._json_assertion_failures(parsed, json_assertions)
        if assertion_failures:
            failure_breakdown["stdout_assertion_failed"] = failure_breakdown.get("stdout_assertion_failed", 0) + 1
            errors.extend(assertion_failures)
            last_result["outcome"] = "fail"
            last_result["failure_class"] = "stdout_assertion_failed"
            last_result["stdout_contract_ok"] = False
            last_result["stdout_assertion_failures"] = assertion_failures
            return

        last_result["stdout_contract_ok"] = True

    def _json_assertion_failures(self, payload: Any, assertions: list[dict[str, Any]]) -> list[str]:
        failures: list[str] = []
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
            try:
                assertion_matched = self._json_assertion_matches(actual=actual, op=op, expected=expected)
            except ValueError as exc:
                failures.append(f"runtime stdout assertion invalid: {exc}")
                continue
            if not assertion_matched:
                failures.append(
                    f"runtime stdout assertion failed: path={path} op={op} expected={expected!r} actual={actual!r}"
                )
        return failures

    @staticmethod
    def _resolve_json_path(payload: Any, path: str) -> Any:
        current = payload
        for token in [segment for segment in re.split(r"[.\[\]]", str(path)) if segment]:
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
        if op not in _KNOWN_JSON_ASSERTION_OPS:
            raise ValueError(f"unknown assertion op: {op!r}. Known ops: {sorted(_KNOWN_JSON_ASSERTION_OPS)}")
        if op == "eq":
            return bool(actual == expected)
        if op == "ne":
            return bool(actual != expected)
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


def build_runtime_guard_contract(*, ok: bool, errors: list[str]) -> GuardContract:
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
                rule_id=f"RUNTIME_VERIFIER.FAIL.{index}",
                code="RUNTIME_VERIFIER_FAILED",
                message=str(error)[:480] or "Runtime verification checks failed.",
                location="output",
                severity="strict",
                evidence=(str(error)[:240] if str(error) else None),
                evidence_truncated=len(str(error)) > 240,
            )
            for index, error in enumerate(errors)
        ],
        severity="strict",
        fix_hint="Fix runtime verification failures and rerun.",
        terminal_failure=False,
        terminal_reason=None,
    )
