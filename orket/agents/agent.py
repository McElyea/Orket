from __future__ import annotations

import hashlib
import inspect
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from orket.agents.model_family_registry import ModelFamilyRegistry
from orket.application.services.control_plane_authority_service import ControlPlaneAuthorityService
from orket.application.services.prompt_compiler import PromptCompiler
from orket.application.services.tool_parser import ToolParser
from orket.core.domain import ResidualUncertaintyClassification
from orket.core.domain.execution import ExecutionTurn, ToolCall, ToolCallErrorClass
from orket.exceptions import AgentConfigurationError, CardNotFound
from orket.logging import log_event
from orket.runtime import ConfigLoader
from orket.schema import DialectConfig, SkillConfig
from orket.utils import sanitize_name


class ModelProvider(Protocol):
    @property
    def model(self) -> str: ...

    async def complete(
        self,
        messages: list[dict[str, str]],
        runtime_context: dict[str, Any] | None = None,
    ) -> Any: ...


class NullControlPlaneAuthorityService:
    """No-op journal seam for callers that intentionally run without durable control-plane authority."""

    def append_effect_journal_entry(self, **_kwargs: Any) -> None:
        return None


class Agent:
    """
    Application Service: Orchestrates the execution of a single agent turn.
    Delegates to specialized services for prompt compilation and tool parsing.
    """

    def __init__(
        self,
        name: str,
        description: str,
        tools: dict[str, Callable[..., Any]],
        provider: ModelProvider,
        next_member: str | None = None,
        prompt_patch: str | None = None,
        config_root: Path | None = None,
        tool_gate: Any | None = None,
        strict_config: bool = True,
        journal: ControlPlaneAuthorityService | NullControlPlaneAuthorityService | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.tools = tools
        self.provider = provider
        self.next_member = next_member
        self._prompt_patch = prompt_patch
        self.config_root = config_root or Path().resolve()
        self.tool_gate = tool_gate  # Optional ToolGate for mechanical enforcement
        self.strict_config = bool(strict_config)
        self.journal = journal

        self.skill: SkillConfig | None = None
        self.dialect: DialectConfig | None = None
        self._load_configs()

    def _load_configs(self) -> None:
        loader = ConfigLoader(self.config_root, "core")
        try:
            self.skill = loader.load_asset("roles", sanitize_name(self.name), SkillConfig)
        except (FileNotFoundError, ValueError, CardNotFound) as e:
            if self.strict_config:
                raise AgentConfigurationError(
                    f"agent role asset load failed: agent={self.name} config_root={self.config_root}"
                ) from e
            log_event(
                "agent_role_asset_missing",
                {"agent": self.name, "error": str(e)},
                workspace=Path("workspace/default"),
                role=self.name,
            )

        model_name = self.provider.model.lower()
        model_family_match = ModelFamilyRegistry.from_config().resolve(model_name)
        family = model_family_match.family
        if not model_family_match.recognized:
            log_event(
                "model_family_unrecognized",
                {"agent": self.name, "model": self.provider.model, "family": family},
                workspace=Path("workspace/default"),
                role=self.name,
                level="warn",
            )

        try:
            self.dialect = loader.load_asset("dialects", family, DialectConfig)
        except (FileNotFoundError, ValueError, CardNotFound) as e:
            if self.strict_config:
                raise AgentConfigurationError(
                    "agent dialect asset load failed: "
                    f"agent={self.name} model={self.provider.model} family={family} config_root={self.config_root}"
                ) from e
            log_event(
                "agent_dialect_asset_missing",
                {"agent": self.name, "family": family, "error": str(e)},
                workspace=Path("workspace/default"),
                role=self.name,
            )

    def get_compiled_prompt(self) -> str:
        """Returns the fully compiled system instructions for this agent."""
        if self.skill and self.dialect:
            return PromptCompiler.compile(self.skill, self.dialect, self.next_member, self._prompt_patch)
        return self.description

    async def run(
        self,
        task: dict[str, Any],
        context: dict[str, Any],
        workspace: Path,
        transcript: list[dict[str, Any]] | None = None,
    ) -> ExecutionTurn:
        """Executes the turn and returns a structured ExecutionTurn object."""

        # 1. COMPILE INSTRUCTIONS
        system_prompt = (
            PromptCompiler.compile(self.skill, self.dialect, self.next_member, self._prompt_patch)
            if self.skill and self.dialect
            else self.description
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task['description']}"},
        ]

        if transcript:
            history = "Previous steps:\n" + "\n".join([f"[{t['role']}] {t['summary']}" for t in transcript])
            messages.append({"role": "user", "content": history})

        messages.append({"role": "user", "content": f"Context: {context}"})

        # 2. GENERATE RESPONSE
        result = await self.provider.complete(messages)
        text = result.content if hasattr(result, "content") else str(result)

        # Extract Thought
        thought: str | None = None
        thought_match = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
            text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL).strip()

        # 3. PARSE & EXECUTE TOOLS
        parser_diag: list[dict[str, Any]] = []

        def capture(stage: str, data: dict[str, Any]) -> None:
            parser_diag.append({"stage": stage, "data": data})

        parsed_calls = ToolParser.parse(text, diagnostics=capture)
        partial_recovery_events = [
            dict(item.get("data") or {})
            for item in parser_diag
            if item.get("stage") == "parse_partial_recovery"
            and dict(item.get("data") or {}).get("recovery_complete") is False
        ]
        partial_parse_error: str | None = None
        if partial_recovery_events:
            recovered_count = len(parsed_calls)
            skipped_tools = [
                dict(skipped)
                for event in partial_recovery_events
                for skipped in (event.get("skipped_tools") or [])
                if isinstance(skipped, dict)
            ]
            log_event(
                "tool_recovery_partial",
                {
                    "issue_id": context.get("issue_id", "unknown"),
                    "role": self.name,
                    "skipped_tools": skipped_tools,
                    "recovered_count": len(parsed_calls),
                    "result": "blocked",
                },
                workspace,
                role=self.name,
            )
            partial_parse_error = (
                "tool-call recovery was partial; Orket did not execute recovered or skipped tool calls"
            )
            parsed_calls = []
        turn = ExecutionTurn(
            role=self.name,
            issue_id=context.get("issue_id", "unknown"),
            thought=thought,
            content=text,
            tokens_used=getattr(result, "raw", {}).get("total_tokens", 0),
            raw=getattr(result, "raw", {}),
            partial_parse_failure=partial_parse_error is not None,
            error=partial_parse_error,
            error_class=ToolCallErrorClass.PARSE_PARTIAL if partial_parse_error else None,
        )
        if partial_parse_error:
            turn.raw["partial_parse_failure"] = {
                "error": partial_parse_error,
                "error_class": ToolCallErrorClass.PARSE_PARTIAL.value,
                "recovered_count": recovered_count,
                "skipped_tools": skipped_tools,
            }
            turn.note = f"role={self.name}, tools=0, partial_parse_failure=True"
            return turn

        previous_effect_entry = None
        for index, call in enumerate(parsed_calls):
            tool_name = call["tool"]
            args = call["args"]

            if tool_name not in self.tools:
                turn.tool_calls.append(
                    ToolCall(
                        tool=tool_name,
                        args=args,
                        error=f"Unknown tool '{tool_name}'",
                        error_class=ToolCallErrorClass.UNKNOWN_TOOL,
                    )
                )
                continue

            # --- TOOL GATE: Pre-execution validation ---
            if self.tool_gate:
                roles = context.get("roles", [self.name])
                gate_error = await self.tool_gate.validate(tool_name, args, context, roles)
                if gate_error:
                    turn.tool_calls.append(
                        ToolCall(
                            tool=tool_name,
                            args=args,
                            error=f"[GATE] {gate_error}",
                            error_class=ToolCallErrorClass.GATE_BLOCKED,
                        )
                    )
                    log_event(
                        "tool_blocked",
                        {"tool": tool_name, "args": args, "reason": gate_error},
                        workspace,
                        role=self.name,
                    )
                    continue

            # --- TOOL EXECUTION ---
            tool_fn = self.tools[tool_name]
            if self._journaling_enabled():
                _required_journal_context(context, "run_id")
            try:
                res = (
                    await tool_fn(args, context=context)
                    if inspect.iscoroutinefunction(tool_fn)
                    else tool_fn(args, context=context)
                )
            except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
                turn.tool_calls.append(
                    ToolCall(
                        tool=tool_name,
                        args=args,
                        error=str(e),
                        error_class=ToolCallErrorClass.EXECUTION_FAILED,
                    )
                )
                previous_effect_entry = self._append_effect_journal_entry(
                    context=context,
                    tool_name=tool_name,
                    args=args,
                    outcome=None,
                    error=str(e),
                    tool_index=index,
                    previous_entry=previous_effect_entry,
                )
                if previous_effect_entry is not None:
                    turn.raw.setdefault("effect_journal_entries", []).append(
                        previous_effect_entry.model_dump(mode="json")
                    )
                continue
            turn.tool_calls.append(ToolCall(tool=tool_name, args=args, result=res))
            previous_effect_entry = self._append_effect_journal_entry(
                context=context,
                tool_name=tool_name,
                args=args,
                outcome=res,
                error=None,
                tool_index=index,
                previous_entry=previous_effect_entry,
            )
            if previous_effect_entry is not None:
                turn.raw.setdefault("effect_journal_entries", []).append(
                    previous_effect_entry.model_dump(mode="json")
                )
            log_event("tool_call", {"tool": tool_name, "args": args, "result": res}, workspace, role=self.name)

        turn.note = f"role={self.name}, tools={len(turn.tool_calls)}"
        return turn

    def _append_effect_journal_entry(
        self,
        *,
        context: dict[str, Any],
        tool_name: str,
        args: dict[str, Any],
        outcome: Any | None,
        error: str | None,
        tool_index: int,
        previous_entry: Any | None,
    ) -> Any | None:
        journal = self.journal
        if journal is None or isinstance(journal, NullControlPlaneAuthorityService):
            return None
        tool_digest = _canonical_digest({"tool": tool_name, "args": args})
        result_ref = _canonical_ref({"result": outcome} if error is None else {"error": error})
        run_id = _required_journal_context(context, "run_id")
        attempt_id = str(context.get("attempt_id") or f"{run_id}:attempt:1")
        step_prefix = str(context.get("step_id") or f"{run_id}:step")
        step_id = f"{step_prefix}:{tool_index:04d}"
        uncertainty = (
            ResidualUncertaintyClassification.NONE
            if error is None
            else ResidualUncertaintyClassification.UNRESOLVED
        )
        return journal.append_effect_journal_entry(
            journal_entry_id=f"agent-tool-journal:{tool_digest}:{tool_index:04d}",
            effect_id=f"agent-tool-effect:{tool_digest}",
            run_id=run_id,
            attempt_id=attempt_id,
            step_id=step_id,
            authorization_basis_ref=str(context.get("authorization_basis_ref") or f"agent-tool-auth:{tool_digest}"),
            publication_timestamp=str(
                context.get("journal_publication_timestamp") or datetime.now(UTC).isoformat()
            ),
            intended_target_ref=str(context.get("intended_target_ref") or f"tool:{tool_name}:{tool_digest}"),
            observed_result_ref=result_ref,
            uncertainty_classification=uncertainty,
            integrity_verification_ref=str(context.get("integrity_verification_ref") or result_ref),
            previous_entry=previous_entry,
        )

    def _journaling_enabled(self) -> bool:
        return self.journal is not None and not isinstance(self.journal, NullControlPlaneAuthorityService)


def _required_journal_context(context: dict[str, Any], key: str) -> str:
    value = str(context.get(key) or "").strip()
    if not value:
        raise ValueError(f"agent effect journal requires context['{key}']")
    return value


def _canonical_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _canonical_ref(payload: Any) -> str:
    return f"sha256:{_canonical_digest(payload)}"
