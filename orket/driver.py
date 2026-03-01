from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.reforger_tools import ReforgerTools
from orket.exceptions import CardNotFound
from orket.logging import log_event
from orket.orket import ConfigLoader
from orket.schema import DialectConfig, SkillConfig

from orket.driver_support_cli import DriverCliMixin
from orket.driver_support_conversation import DriverConversationMixin
from orket.driver_support_resources import DriverResourceMixin


class OrketDriver(DriverCliMixin, DriverConversationMixin, DriverResourceMixin):
    """
    The Driver is the high-level intent parser and resource manager.
    It manages Rocks, Epics, Issues, and Team Selection.
    """

    def __init__(self, model: str = None):
        self.fs = AsyncFileTools(Path("."))
        self.reforger_tools = ReforgerTools(Path("workspace/default"), [Path(".")])

        from orket.schema import OrganizationConfig

        org_path = Path("model/organization.json")
        self.org = None
        if org_path.exists():
            try:
                self.org = OrganizationConfig.model_validate_json(self.fs.read_file_sync(str(org_path)))
            except (ValueError, FileNotFoundError):
                pass

        from orket.orchestration.models import ModelSelector

        selector = ModelSelector(organization=self.org)
        selected_model = selector.select(role="operations_lead", override=model)

        self.provider = LocalModelProvider(model=selected_model, temperature=0.1)
        self.model_root = Path("model")
        self.skill: SkillConfig | None = None
        self.dialect: DialectConfig | None = None
        self._load_engine_configs()

    def _load_engine_configs(self):
        loader = ConfigLoader(Path("model"), "core")

        try:
            self.skill = loader.load_asset("skills", "operations_lead", SkillConfig)
        except (FileNotFoundError, ValueError, CardNotFound):
            pass

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

        try:
            self.dialect = loader.load_asset("dialects", family, DialectConfig)
        except (FileNotFoundError, ValueError, CardNotFound):
            pass

    async def _get_inventory(self) -> Dict[str, Any]:
        inventory = {"departments": {}}
        for dept_dir in self.model_root.iterdir():
            if dept_dir.is_dir():
                dept_name = dept_dir.name
                inventory["departments"][dept_name] = {
                    "teams": [f.stem for f in (dept_dir / "teams").glob("*.json")] if (dept_dir / "teams").exists() else [],
                    "skills": [f.stem for f in (dept_dir / "skills").glob("*.json")] if (dept_dir / "skills").exists() else [],
                }
        return inventory

    async def process_request(self, message: str) -> str:
        request_text = str(message or "").strip()
        self._log_operator_metric("operator_request_total", route="received")

        cli_response = await self._try_cli_command(message)
        if cli_response is not None:
            self._log_operator_metric("operator_request_total", route="cli")
            return cli_response

        if self._should_handle_as_conversation(message):
            self._log_operator_metric("operator_request_total", route="conversation")
            rule_reply = self._conversation_reply(message)
            if rule_reply is not None:
                return rule_reply
            model_reply = await self._conversation_model_reply(request_text)
            if model_reply:
                return model_reply
            return "I can chat normally and help with Orket operations when you ask explicitly."

        loader = ConfigLoader(Path("model"), "core")
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
            system_prompt = """You are the Orket Operator.

Operate in a precise, high-context, non-repetitive reasoning mode.
Your job is to interpret the user's request and decide the correct action
within the Orket Schema. You are not a conversational assistant; you are
a project-board controller.

CORE RULES:
- Always return VALID JSON matching the Orket Schema.
- Never invent assets, departments, or relationships that do not exist.
- Never propose structural changes unless the user request clearly requires it.
- Never repeat instructions back to the user.
- Never explain JSON; just produce it.

THINKING STYLE:
- Be concise, explicit, and deterministic.
- Use first-principles reasoning.
- Prefer minimal changes over broad restructuring.
- If uncertain, choose the safest, least-destructive action.

MODES:
1. Conversational input (greeting, clarification, meta-discussion)
   → respond with:
   {
     "action": "converse",
     "response": "<natural response>",
     "reasoning": "<brief explanation>"
   }

2. Structural request (create, update, move, delete, direct)
   → choose the correct Orket action and produce only the JSON.

3. Ambiguous request
   → ask a single clarifying question using action: "converse".

CONTEXT PROVIDED:
- inventory: current assets
- active_rocks: available rocks
- active_epics: available epics
- request: the user message

Your output must always be a single JSON object with:
- action
- reasoning
- and any required fields for that action.

Do not include commentary outside the JSON.
"""

        response = await self.provider.complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context: {context}\nRequest: {message}"},
            ]
        )

        try:
            text = response.content
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1:
                self._log_operator_metric("operator_request_total", route="model_no_json")
                return f"Driver failed to find JSON in response: {text[:100]}..."

            plan = json.loads(text[start : end + 1])
            action = str(plan.get("action") or "").strip().lower()
            if action in {"create_issue", "create_epic", "create_rock", "adopt_issue"} and not self._has_explicit_structural_intent(request_text):
                self._log_operator_metric("operator_structural_action_blocked", action=action)
                log_event(
                    "operator_structural_action_blocked",
                    {"action": action, "request": request_text},
                    Path("workspace/default"),
                    role="DRIVER",
                )
                return (
                    "I can do that, but please ask explicitly for a board change. "
                    "For example: '/create epic <name> <department>' or 'create epic <name>'."
                )
            self._log_operator_metric("operator_request_total", route="model")
            return await self.execute_plan(plan)
        except json.JSONDecodeError as e:
            self._log_operator_metric("operator_request_total", route="model_json_error")
            return f"Driver failed to parse JSON: {str(e)}"
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
            import traceback

            log_event(
                "driver_process_failed",
                {"error": str(e), "traceback": traceback.format_exc()},
                Path("workspace/default"),
                role="DRIVER",
            )
            return f"Driver failed to process request due to internal error: {str(e)}"

    async def execute_plan(self, plan: Dict[str, Any]) -> str:
        action = plan.get("action")
        reasoning = plan.get("reasoning", "No reasoning provided.")
        response_text = str(plan.get("response", "") or "").strip()

        if action == "assign_team":
            team = plan.get("suggested_team")
            dept = plan.get("suggested_department")
            log_event("team_assignment", {"team": team, "department": dept, "reason": reasoning}, Path("workspace/default"), role="DRIVER")
            return f"Resource Selection: Switching to Team '{team}' in '{dept}'.\nReason: {reasoning}"

        if action == "turn_directive":
            target = plan.get("target_seat")
            directive = plan.get("directive")
            return f"Tactical Directive issued to {target}: {directive}"

        if action in {"converse", "chat", "respond", "conversation"}:
            if response_text:
                return response_text
            return reasoning

        if action in {"create_issue", "create_epic", "create_rock", "adopt_issue"}:
            res = await self._execute_structural_change(plan)
            return f"{res}\n\nStrategic Insight: {reasoning}"

        if response_text:
            return response_text
        return "I can chat normally or help with board actions. Tell me what you want to do."
