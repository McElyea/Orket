from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context, run_owned_io
from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.driver_command_service import DriverCommandService, collect_driver_inventory
from orket.application.services.local_model_factory import create_local_model_provider
from orket.application.services.model_selection_service import prepare_bootstrap_model_selection
from orket.application.services.reforger_service import ReforgerService
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_result_lifetime import create_runtime_owner
from orket.driver_support_conversation import DriverConversationMixin
from orket.driver_support_resources import DriverResourceMixin
from orket.exceptions import CardNotFound
from orket.logging import log_event
from orket.project_paths import default_model_root, default_project_root, default_workspace_root
from orket.runtime import ConfigLoader
from orket.schema import DialectConfig, SkillConfig


def _default_project_root() -> Path:
    return default_project_root()


def _default_workspace_root() -> Path:
    return default_workspace_root()


class OrketDriver(DriverResourceMixin, DriverConversationMixin):
    """
    The Driver is the high-level intent parser and resource manager.
    It manages Rocks, Epics, Issues, and Team Selection.
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        provider: LocalModelProvider | None = None,
        fs: AsyncFileTools | None = None,
        reforger_tools: ReforgerService | None = None,
        strict_config: bool | None = None,
        json_parse_mode: str | None = None,
        project_root: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        require_sync_context(code="E_DRIVER_CONSTRUCTION_REQUIRES_WORKER")
        captured_environment = dict(os.environ if environment is None else environment)
        self._environment = MappingProxyType(captured_environment)
        self.project_root = Path(project_root).resolve() if project_root is not None else _default_project_root()
        self.model_root = default_model_root(self.project_root)
        self.workspace_root = default_workspace_root(self.project_root)
        self.fs = fs or AsyncFileTools(self.project_root)
        self.reforger_tools = reforger_tools or ReforgerService(self.workspace_root, [self.project_root])

        from orket.schema import OrganizationConfig

        org_path = self.model_root / "organization.json"
        self.org = None
        if org_path.exists():
            with contextlib.suppress(ValueError, FileNotFoundError):
                self.org = OrganizationConfig.model_validate_json(self.fs.read_file_sync(str(org_path)))

        if provider is None:
            selection = prepare_bootstrap_model_selection(environment=captured_environment, organization=self.org)
            selected_model = selection.select("operations_lead", override=model).final_model
        self.provider = provider
        self._configured_model_name = selected_model if provider is None else provider.model
        self.skill: SkillConfig | None = None
        self.dialect: DialectConfig | None = None
        strict_from_env = str(captured_environment.get("ORKET_DRIVER_STRICT_CONFIG", "")).strip().lower()
        self.strict_config_mode = (
            strict_config if strict_config is not None else strict_from_env in {"1", "true", "yes", "on"}
        )
        parse_mode_from_env = str(captured_environment.get("ORKET_DRIVER_JSON_PARSE_MODE", "")).strip().lower()
        self.json_parse_mode = "compatibility"
        self.prompting_mode = "fallback"
        self.config_degraded = False
        self.config_dependency_classification: dict[str, str] = {}
        self.config_load_failures: list[dict[str, str]] = []
        self._load_engine_configs()
        self.json_parse_mode = self._resolve_json_parse_mode(
            explicit_mode=json_parse_mode,
            env_mode=parse_mode_from_env,
        )
        if self.provider is None:
            self.provider = create_local_model_provider(model=self._configured_model_name, temperature=0.1,
                                               environment=captured_environment)

    @classmethod
    async def create(
        cls, model: str | None = None, *, provider: LocalModelProvider | None = None,
        fs: AsyncFileTools | None = None, reforger_tools: ReforgerService | None = None,
        strict_config: bool | None = None, json_parse_mode: str | None = None,
        project_root: Path | None = None, environment: Mapping[str, str] | None = None,
    ) -> OrketDriver:
        relative_root = Path() if project_root is None else Path(project_root)
        inputs = await RuntimeConstructionInputs.capture_async(environment=environment)
        root = inputs.invocation_root / relative_root

        def construct():
            inputs.bind_settings()
            return cls(model, provider=provider, fs=fs, reforger_tools=reforger_tools,
                       strict_config=strict_config, json_parse_mode=json_parse_mode,
                       project_root=root, environment=inputs.environment)

        return await create_runtime_owner(construct, label="driver-construction")

    async def close(self) -> None:
        await run_owned_io(self.provider.close, label="driver-provider-close", preserve_failure=True)

    def _operator_workspace_root(self) -> Path:
        return Path(getattr(self, "workspace_root", _default_workspace_root()))

    def _operator_model_root(self) -> Path:
        return Path(getattr(self, "model_root", default_model_root()))

    def _compatibility_parse_warning(self) -> str:
        if not bool(getattr(self, "_compatibility_parse_fallback_used", False)):
            return ""
        return "[DEGRADED] Compatibility mode extracted JSON from non-envelope model output.\n"

    def _resolve_json_parse_mode(self, *, explicit_mode: str | None, env_mode: str) -> str:
        selected_parse_mode = str(explicit_mode or env_mode or "").strip().lower()
        if selected_parse_mode in {"strict", "compatibility"}:
            return selected_parse_mode
        return "strict" if self.prompting_mode == "governed" else "compatibility"

    def _load_engine_configs(self) -> None:
        workspace_root = self._operator_workspace_root()
        self.config_dependency_classification.clear()
        self.config_load_failures.clear()
        self.config_degraded = False
        loader = ConfigLoader(self.project_root, "core", environment=self._environment)
        skill_dependency = "skill.operations_lead"
        self.config_dependency_classification[skill_dependency] = "degradable"

        try:
            self.skill = loader.load_asset("skills", "operations_lead", SkillConfig)
        except (FileNotFoundError, ValueError, CardNotFound) as exc:
            self.skill = None
            self.config_degraded = True
            failure = {
                "dependency": skill_dependency,
                "classification": "degradable",
                "error": str(exc),
            }
            self.config_load_failures.append(failure)
            log_event("driver_config_dependency_failed", failure, workspace_root, role="DRIVER")

        model_name = (self.provider.model if self.provider is not None else self._configured_model_name).lower()
        if "deepseek" in model_name:
            family = "deepseek-r1"
        elif "llama" in model_name:
            family = "llama3"
        elif "phi" in model_name:
            family = "phi"
        elif "qwen" in model_name:
            family = "qwen"
        else:
            family = "generic"

        dialect_dependency = f"dialect.{family}"
        self.config_dependency_classification[dialect_dependency] = "degradable"
        try:
            self.dialect = loader.load_asset("dialects", family, DialectConfig)
        except (FileNotFoundError, ValueError, CardNotFound) as exc:
            self.dialect = None
            self.config_degraded = True
            failure = {
                "dependency": dialect_dependency,
                "classification": "degradable",
                "error": str(exc),
            }
            self.config_load_failures.append(failure)
            log_event("driver_config_dependency_failed", failure, workspace_root, role="DRIVER")

        self.prompting_mode = "governed" if self.skill and self.dialect else "fallback"
        log_event(
            "driver_prompting_mode",
            {
                "mode": self.prompting_mode,
                "degraded": self.config_degraded,
                "strict_mode": bool(self.strict_config_mode),
                "load_failures": self.config_load_failures,
            },
            workspace_root,
            role="DRIVER",
        )
        if bool(self.strict_config_mode) and self.prompting_mode != "governed":
            raise RuntimeError(
                "Driver strict config mode requires governed prompting assets. "
                f"load_failures={self.config_load_failures}"
            )

    def _canonical_action_registry(self) -> dict[str, tuple[str, ...]]:
        return {
            "suggestion": ("assign_team",),
            "directive": ("turn_directive",),
            "conversation": ("converse", "chat", "respond", "conversation"),
            "structural": ("create_issue", "create_epic", "create_rock"),
        }

    def _supported_plan_actions(self) -> set[str]:
        actions: set[str] = set()
        for group_actions in self._canonical_action_registry().values():
            actions.update(group_actions)
        return actions

    def _supported_action_summary_lines(self) -> list[str]:
        registry = self._canonical_action_registry()
        structural = ", ".join(registry["structural"])
        conversation = ", ".join(registry["conversation"])
        return [
            "Supported model-directed actions:",
            "- assign_team (suggestion only; no runtime team switch)",
            "- turn_directive",
            f"- conversation replies: {conversation}",
            f"- structural changes: {structural}",
        ]

    def _supported_action_error_text(self, attempted_action: str) -> str:
        summary = "\n".join(self._supported_action_summary_lines())
        return f"Unsupported action '{attempted_action}'.\n{summary}"

    async def process_request(self, message: str) -> str:
        request_text = str(message or "").strip()
        workspace_root = self._operator_workspace_root()
        self._log_operator_metric("operator_request_total", route="received")

        cli_response = await DriverCommandService(
            self.model_root, getattr(self, "reforger_tools", None), self._capability_lines()).execute(message)
        if cli_response is not None:
            self._log_operator_metric("operator_request_total", route="cli")
            return cli_response

        if self._should_route_to_conversation(message):
            self._log_operator_metric("operator_request_total", route="conversation")
            rule_reply = self._conversation_reply(message)
            if rule_reply is not None:
                return rule_reply
            model_reply = await self._conversation_model_reply(request_text)
            if model_reply:
                return model_reply
            return "I can chat normally and help with Orket operations when you ask explicitly."

        context = await collect_driver_inventory(self.project_root, self.model_root, self._environment)
        context["request"] = message

        if self.skill and self.dialect:
            system_prompt = f"IDENTITY: {self.skill.name}\nINTENT: {self.skill.intent}\n\n"
            system_prompt += "RESPONSIBILITIES:\n" + "\n".join([f"- {r}" for r in self.skill.responsibilities]) + "\n\n"
            system_prompt += f"SYNTAX DIALECT ({self.dialect.model_family}):\n"
            system_prompt += "YOU MUST RESPOND WITH VALID JSON matching the Orket Schema.\n"
            system_prompt += "\nCONSTRAINTS:\n" + "\n".join([f"- {c}" for c in self.dialect.constraints])
            system_prompt += f"\nGUARDRAIL: {self.dialect.hallucination_guard}\n"
        else:
            system_prompt = self._build_fallback_system_prompt()

        response = await self.provider.complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context: {context}\nRequest: {message}"},
            ]
        )

        try:
            plan = self._parse_model_plan(str(response.content or ""))
            compatibility_warning = self._compatibility_parse_warning()
            if compatibility_warning:
                log_event(
                    "driver_json_parse_compatibility_fallback_used",
                    {"mode": "compatibility"},
                    workspace_root,
                    role="DRIVER",
                )
            action = str(plan.get("action") or "").strip().lower()
            if action in {"create_issue", "create_epic", "create_rock"} and not self._has_explicit_structural_intent(
                request_text
            ):
                self._log_operator_metric("operator_structural_action_blocked", action=action)
                log_event(
                    "operator_structural_action_blocked",
                    {"action": action, "request": request_text},
                    workspace_root,
                    role="DRIVER",
                )
                return (
                    compatibility_warning + "I can do that, but please ask explicitly for a board change. "
                    "For example: '/create epic <name> <department>' or 'create epic <name>'."
                )
            self._log_operator_metric("operator_request_total", route="model")
            return compatibility_warning + await self.execute_plan(plan)
        except json.JSONDecodeError as e:
            self._log_operator_metric("operator_request_total", route="model_json_error")
            return f"Driver failed to parse JSON: {str(e)}"
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
            import traceback

            log_event(
                "driver_process_failed",
                {"error": str(e), "traceback": traceback.format_exc()},
                workspace_root,
                role="DRIVER",
            )
            return f"Driver failed to process request due to internal error: {str(e)}"

    async def execute_plan(self, plan: dict[str, Any]) -> str:
        action = plan.get("action")
        reasoning = str(plan.get("reasoning", "No reasoning provided."))
        response_text = str(plan.get("response", "") or "").strip()
        normalized_action = str(action or "").strip().lower()
        workspace_root = self._operator_workspace_root()

        if normalized_action and normalized_action not in self._supported_plan_actions():
            return self._supported_action_error_text(normalized_action)

        if normalized_action == "assign_team":
            team = plan.get("suggested_team")
            dept = plan.get("suggested_department")
            log_event(
                "team_assignment_suggested",
                {
                    "team": team,
                    "department": dept,
                    "reason": reasoning,
                    "mode": "suggestion_only",
                },
                workspace_root,
                role="DRIVER",
            )
            team_label = str(team or "unknown_team")
            dept_label = str(dept or "unknown_department")
            return (
                f"Resource Selection Suggestion: Consider Team '{team_label}' in '{dept_label}'. "
                "No runtime team switch was applied.\n"
                f"Reason: {reasoning}"
            )

        if normalized_action == "turn_directive":
            target = plan.get("target_seat")
            directive = plan.get("directive")
            return f"Tactical Directive issued to {target}: {directive}"

        if normalized_action in {"converse", "chat", "respond", "conversation"}:
            if response_text:
                return response_text
            return reasoning

        if normalized_action in {"create_issue", "create_epic", "create_rock"}:
            res = await self._execute_structural_change(plan)
            if str(res).strip().lower().startswith("error:"):
                return res
            return f"{res}\n\nStrategic Insight: {reasoning}"

        if response_text:
            return response_text
        return "I can chat normally or help with board actions. Tell me what you want to do."
