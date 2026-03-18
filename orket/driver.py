from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.reforger_tools import ReforgerTools
from orket.exceptions import CardNotFound
from orket.logging import log_event
from orket.orket import ConfigLoader
from orket.project_paths import default_model_root, default_project_root, default_workspace_root
from orket.schema import DialectConfig, SkillConfig

from orket.driver_support_cli import DriverCliMixin
from orket.driver_support_conversation import DriverConversationMixin
from orket.driver_support_resources import DriverResourceMixin


def _default_project_root() -> Path:
    return default_project_root()


def _default_model_root() -> Path:
    return default_model_root()


def _default_workspace_root() -> Path:
    return default_workspace_root()


class OrketDriver(DriverCliMixin, DriverConversationMixin, DriverResourceMixin):
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
        reforger_tools: ReforgerTools | None = None,
        strict_config: bool | None = None,
        json_parse_mode: str | None = None,
        project_root: Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve() if project_root is not None else _default_project_root()
        self.model_root = default_model_root(self.project_root)
        self.workspace_root = default_workspace_root(self.project_root)
        self.fs = fs or AsyncFileTools(self.project_root)
        self.reforger_tools = reforger_tools or ReforgerTools(self.workspace_root, [self.project_root])

        from orket.schema import OrganizationConfig

        org_path = self.model_root / "organization.json"
        self.org = None
        if org_path.exists():
            try:
                self.org = OrganizationConfig.model_validate_json(self.fs.read_file_sync(str(org_path)))
            except (ValueError, FileNotFoundError):
                pass

        from orket.orchestration.models import ModelSelector

        selector = ModelSelector(organization=self.org)
        selected_model = selector.select(role="operations_lead", override=model)

        self.provider = provider or LocalModelProvider(model=selected_model, temperature=0.1)
        self.skill: SkillConfig | None = None
        self.dialect: DialectConfig | None = None
        strict_from_env = str(os.getenv("ORKET_DRIVER_STRICT_CONFIG", "")).strip().lower()
        self.strict_config_mode = (
            strict_config if strict_config is not None else strict_from_env in {"1", "true", "yes", "on"}
        )
        parse_mode_from_env = str(os.getenv("ORKET_DRIVER_JSON_PARSE_MODE", "")).strip().lower()
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

    def _operator_workspace_root(self) -> Path:
        return Path(getattr(self, "workspace_root", _default_workspace_root()))

    def _operator_model_root(self) -> Path:
        return Path(getattr(self, "model_root", _default_model_root()))

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
        loader = ConfigLoader(self._operator_model_root(), "core")
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

        model_name = self.provider.model.lower()
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

    async def _get_inventory(self) -> dict[str, Any]:
        inventory = {"departments": {}}
        for dept_dir in self.model_root.iterdir():
            if dept_dir.is_dir():
                dept_name = dept_dir.name
                inventory["departments"][dept_name] = {
                    "teams": [f.stem for f in (dept_dir / "teams").glob("*.json")]
                    if (dept_dir / "teams").exists()
                    else [],
                    "skills": [f.stem for f in (dept_dir / "skills").glob("*.json")]
                    if (dept_dir / "skills").exists()
                    else [],
                }
        return inventory

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

    def _build_fallback_system_prompt(self) -> str:
        registry = self._canonical_action_registry()
        grouped_actions = []
        for group in ("suggestion", "directive", "conversation", "structural"):
            actions = ", ".join(registry[group])
            grouped_actions.append(f"- {group}: {actions}")
        return (
            "You are the Orket Operator.\n\n"
            "Operate in a precise, high-context, non-repetitive reasoning mode.\n"
            "Your job is to interpret the user's request and decide the correct action\n"
            "within the Orket Schema. You are a constrained action router, not a general\n"
            "project-board controller.\n\n"
            "CORE RULES:\n"
            "- Always return VALID JSON matching the Orket Schema.\n"
            "- Never invent assets, departments, or relationships that do not exist.\n"
            "- Never propose structural changes unless the user request clearly requires it.\n"
            "- Never repeat instructions back to the user.\n"
            "- Never explain JSON; just produce it.\n\n"
            "SUPPORTED ACTIONS:\n" + "\n".join(grouped_actions) + "\n\n"
            "If the request needs an unsupported action, return action='converse' with a short clarification.\n\n"
            "THINKING STYLE:\n"
            "- Be concise, explicit, and deterministic.\n"
            "- Use first-principles reasoning.\n"
            "- Prefer minimal changes over broad restructuring.\n"
            "- If uncertain, choose the safest, least-destructive action.\n\n"
            "MODES:\n"
            "1. Conversational input (greeting, clarification, meta-discussion)\n"
            "   -> respond with:\n"
            "   {\n"
            '     "action": "converse",\n'
            '     "response": "<natural response>",\n'
            '     "reasoning": "<brief explanation>"\n'
            "   }\n\n"
            "2. Structural request matching supported structural actions\n"
            "   -> choose the correct Orket action and produce only the JSON.\n\n"
            "3. Ambiguous request\n"
            '   -> ask a single clarifying question using action: "converse".\n\n'
            "CONTEXT PROVIDED:\n"
            "- inventory: current assets\n"
            "- active_rocks: available rocks\n"
            "- active_epics: available epics\n"
            "- request: the user message\n\n"
            "Your output must always be a single JSON object with:\n"
            "- action\n"
            "- reasoning\n"
            "- and any required fields for that action.\n\n"
            "Do not include commentary outside the JSON.\n"
        )

    def _parse_model_plan(self, raw_text: str) -> dict[str, Any]:
        workspace_root = self._operator_workspace_root()
        parse_mode = str(getattr(self, "json_parse_mode", "compatibility")).strip().lower()
        self._compatibility_parse_fallback_used = False
        if parse_mode == "strict":
            log_event(
                "driver_json_parse_mode_strict",
                {"mode": "strict"},
                workspace_root,
                role="DRIVER",
            )
            stripped = str(raw_text or "").strip()
            try:
                return json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError("Strict JSON mode requires pure JSON envelope output.") from exc
            except TypeError as exc:
                raise ValueError("Strict JSON mode requires pure JSON envelope output.") from exc

        log_event(
            "driver_json_parse_mode_compatibility",
            {"mode": "compatibility"},
            workspace_root,
            role="DRIVER",
        )
        text = str(raw_text or "")
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return json.loads(stripped)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Compatibility mode could not find JSON envelope in model output.")
        self._compatibility_parse_fallback_used = True
        return json.loads(text[start : end + 1])

    async def process_request(self, message: str) -> str:
        request_text = str(message or "").strip()
        workspace_root = self._operator_workspace_root()
        self._log_operator_metric("operator_request_total", route="received")

        cli_response = await self._try_cli_command(message)
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

        loader = ConfigLoader(self._operator_model_root(), "core")
        inventory = await self._get_inventory()
        context = {
            "inventory": inventory,
            "active_rocks": loader.list_assets("rocks"),
            "active_epics": loader.list_assets("epics"),
            "request": message,
        }

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
        except (json.JSONDecodeError, ValueError) as e:
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
        reasoning = plan.get("reasoning", "No reasoning provided.")
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
