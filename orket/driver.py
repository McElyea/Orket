import json
from pathlib import Path
from typing import Dict, Any, List
import re
import ast
import shlex
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, IssueConfig, SkillConfig, DialectConfig
from orket.logging import log_event
from orket.exceptions import CardNotFound

class OrketDriver:
    """
    The Driver is the high-level intent parser and resource manager.
    It manages Rocks, Epics, Issues, and Team Selection.
    """
    def __init__(self, model: str = None):
        self.fs = AsyncFileTools(Path("."))
        # 1. Load Organization context
        from orket.schema import OrganizationConfig
        org_path = Path("model/organization.json")
        self.org = None
        if org_path.exists():
            try:
                self.org = OrganizationConfig.model_validate_json(self.fs.read_file_sync(str(org_path)))
            except (ValueError, FileNotFoundError):
                pass

        # 2. Select Model
        from orket.orchestration.models import ModelSelector
        selector = ModelSelector(organization=self.org)
        selected_model = selector.select(role="operations_lead", override=model)
        
        self.provider = LocalModelProvider(model=selected_model, temperature=0.1)
        self.model_root = Path("model")
        self.skill: SkillConfig | None = None
        self.dialect: DialectConfig | None = None
        self._load_engine_configs()

    def _load_engine_configs(self):
        from orket.orket import ConfigLoader
        loader = ConfigLoader(Path("model"), "core")
        
        # 1. Load specialized Driver skill if exists, otherwise fallback
        try:
            self.skill = loader.load_asset("skills", "operations_lead", SkillConfig)
        except (FileNotFoundError, ValueError, CardNotFound):
            pass

        # 2. Load Dialect
        model_name = self.provider.model.lower()
        if "deepseek" in model_name: family = "deepseek-r1"
        elif "llama" in model_name: family = "llama3"
        elif "phi" in model_name: family = "phi"
        elif "qwen" in model_name: family = "qwen"
        else: family = "generic"
            
        try:
            self.dialect = loader.load_asset("dialects", family, DialectConfig)
        except (FileNotFoundError, ValueError, CardNotFound):
            pass

    async def _get_inventory(self) -> Dict[str, Any]:
        """Scans all departments for teams and skills."""
        inventory = {"departments": {}}
        for dept_dir in self.model_root.iterdir():
            if dept_dir.is_dir():
                dept_name = dept_dir.name
                inventory["departments"][dept_name] = {
                    "teams": [f.stem for f in (dept_dir / "teams").glob("*.json")] if (dept_dir / "teams").exists() else [],
                    "skills": [f.stem for f in (dept_dir / "skills").glob("*.json")] if (dept_dir / "skills").exists() else []
                }
        return inventory

    async def process_request(self, message: str) -> str:
        cli_response = await self._try_cli_command(message)
        if cli_response is not None:
            return cli_response

        if self._should_handle_as_conversation(message):
            return self._conversation_reply(message)

        # 1. Gather current context + Inventory
        loader = ConfigLoader(Path("model"), "core")
        inventory = await self._get_inventory()
        
        context = {
            "inventory": inventory,
            "active_rocks": loader.list_assets("rocks"),
            "active_epics": loader.list_assets("epics"),
            "request": message
        }

        # 2. Build compiled prompt
        if self.skill and self.dialect:
            system_prompt = f"IDENTITY: {self.skill.name}\nINTENT: {self.skill.intent}\n\n"
            system_prompt += "RESPONSIBILITIES:\n" + "\n".join([f"- {r}" for r in self.skill.responsibilities]) + "\n\n"
            system_prompt += f"SYNTAX DIALECT ({self.dialect.model_family}):\n"
            system_prompt += "YOU MUST RESPOND WITH VALID JSON matching the Orket Schema.\n"
            system_prompt += "\nCONSTRAINTS:\n" + "\n".join([f"- {c}" for c in self.dialect.constraints])
            system_prompt += f"\nGUARDRAIL: {self.dialect.hallucination_guard}\n"
        else:
            # Fallback hardcoded prompt
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

        response = await self.provider.complete([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context: {context}\nRequest: {message}"}
        ])

        try:
            text = response.content
            start = text.find('{')
            end = text.rfind('}')
            if start == -1 or end == -1:
                return f"Driver failed to find JSON in response: {text[:100]}..."
                
            plan = json.loads(text[start:end+1])
            return await self.execute_plan(plan)
        except json.JSONDecodeError as e:
            return f"Driver failed to parse JSON: {str(e)}"
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
            # Fallback for unexpected logical errors, but still better than a bare except
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
        new_asset = plan.get("new_asset", {})
        reasoning = plan.get("reasoning", "No reasoning provided.")
        response_text = str(plan.get("response", "") or "").strip()
        
        if action == "assign_team":
            team = plan.get("suggested_team")
            dept = plan.get("suggested_department")
            log_event("team_assignment", {"team": team, "department": dept, "reason": reasoning}, Path("workspace/default"), role="DRIVER")
            return f"Resource Selection: Switching to Team '{team}' in '{dept}'.\nReason: {reasoning}"

        if action == "turn_directive":
            # This is where we produce a Note for the target seat
            target = plan.get("target_seat")
            directive = plan.get("directive")
            # The OrchestrationEngine will need to handle this note delivery
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

    async def _execute_structural_change(self, plan: Dict[str, Any]) -> str:
        action = plan.get("action")
        new_asset = plan.get("new_asset", {})
        suggested_dept = plan.get("suggested_department", "core")
        dept_root = self.model_root / suggested_dept
        workspace_path = Path("workspace/default")
        
        if not dept_root.exists(): dept_root = self.model_root / "core"
        
        if action == "create_issue":
            parent_epic = plan.get("target_parent")
            path = dept_root / "epics" / f"{parent_epic}.json"
            if not path.exists(): path = self.model_root / "core" / "epics" / f"{parent_epic}.json"
            
            if path.exists():
                epic_data = json.loads(self.fs.read_file_sync(str(path)))
                if "issues" not in epic_data: epic_data["issues"] = []
                issue_entry = {
                    "summary": new_asset.get("summary", "New Task"),
                    "seat": new_asset.get("seat", "senior_developer"),
                    "priority": new_asset.get("priority", "Medium"),
                    "note": new_asset.get("note", "")
                }
                epic_data["issues"].append(issue_entry)
                self.fs.write_file_sync(str(path), epic_data)
                log_event("create_issue", {"epic": parent_epic, "summary": issue_entry["summary"]}, workspace_path, role="DRIVER")
                return f"Added issue '{issue_entry['summary']}' to Epic '{parent_epic}' in {path.parent.parent.name}."
            return f"Error: Target epic {parent_epic} not found in core or {suggested_dept}."

        elif action == "create_epic":
            epic_name = new_asset.get("name", "new_epic")
            epic_path = dept_root / "epics" / f"{epic_name}.json"
            epic_path.parent.mkdir(parents=True, exist_ok=True)
            self.fs.write_file_sync(str(epic_path), new_asset)
            
            parent_rock = plan.get("target_parent")
            rock_path = dept_root / "rocks" / f"{parent_rock}.json"
            if not rock_path.exists(): rock_path = self.model_root / "core" / "rocks" / f"{parent_rock}.json"

            if not parent_rock or not rock_path.exists():
                parent_rock = f"Rock-Nomination-{epic_name}"
                nom_path = dept_root / "rocks" / f"{parent_rock}.json"
                nom_path.parent.mkdir(parents=True, exist_ok=True)
                rock_data = {
                    "name": parent_rock,
                    "description": f"Strategic parent for {new_asset.get('description', 'new initiative')}",
                    "owner_department": suggested_dept,
                    "epics": [{"epic": epic_name, "department": suggested_dept}]
                }
                self.fs.write_file_sync(str(nom_path), rock_data)
                log_event("create_epic", {"name": epic_name, "rock": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
                log_event("create_rock", {"name": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
                return f"Created Epic '{epic_name}' and nominated new parent Rock '{parent_rock}' in {suggested_dept}."
            else:
                rock_data = json.loads(self.fs.read_file_sync(str(rock_path)))
                if "epics" not in rock_data: rock_data["epics"] = []
                rock_data["epics"].append({"epic": epic_name, "department": suggested_dept})
                self.fs.write_file_sync(str(rock_path), rock_data)
                log_event("create_epic", {"name": epic_name, "rock": parent_rock, "dept": suggested_dept}, workspace_path, role="DRIVER")
                return f"Created Epic '{epic_name}' and linked to existing Rock '{parent_rock}' in {rock_path.parent.parent.name}."

        elif action == "create_rock":
            rock_name = new_asset.get("name", "new_rock")
            path = dept_root / "rocks" / f"{rock_name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.fs.write_file_sync(str(path), new_asset)
            log_event("create_rock", {"name": rock_name, "dept": suggested_dept}, workspace_path, role="DRIVER")
            return f"Nominated new Rock: '{rock_name}' in {suggested_dept}."

        elif action == "adopt_issue":
            issue_id = plan.get("issue_id")
            target_epic = plan.get("target_epic")
            # Logic: Load epic, find issue in orphanage, append, save. 
            # Simplified: Models can just read/write the JSONs to fix orphans now.
            return f"Structural Reconciler: Moving issue {issue_id} to Epic {target_epic}."

        return "No structural action taken."

    async def _try_cli_command(self, message: str) -> str | None:
        text = str(message or "").strip()
        if not text:
            return None

        normalized = text.lower()
        if normalized in {"help", "/help", "what can you do", "capabilities", "/capabilities"}:
            return self._cli_help_text()
        if "what can you do" in normalized or "capabilities" in normalized:
            return self._cli_help_text()
        if "in this environment" in normalized and any(
            token in normalized for token in ("what can", "available", "do here", "use here")
        ):
            return self._cli_help_text()

        command_text = text
        if text.startswith("/"):
            command_text = text[1:].strip()

        known_cli_verbs = {"list", "show", "create", "add-card", "add_card", "list-cards", "list_cards"}
        first_word = command_text.split(" ", 1)[0].strip().lower()
        is_cli_form = text.startswith("/") or first_word in known_cli_verbs
        if not is_cli_form:
            return None

        try:
            tokens = shlex.split(command_text)
        except ValueError:
            return "Invalid command syntax. Use /help for examples."
        if not tokens:
            return None

        verb = tokens[0].lower()
        args = tokens[1:]

        if verb == "list":
            return self._cli_handle_list(args)
        if verb == "show":
            return self._cli_handle_show(args)
        if verb == "create":
            return self._cli_handle_create(args)
        if verb in {"add-card", "add_card"}:
            return self._cli_handle_add_card(args)
        if verb in {"list-cards", "list_cards"}:
            return self._cli_handle_list_cards(args)

        if normalized.startswith("list "):
            return self._cli_handle_list(shlex.split(text)[1:])
        if normalized.startswith("show "):
            return self._cli_handle_show(shlex.split(text)[1:])
        if normalized.startswith("create "):
            return self._cli_handle_create(shlex.split(text)[1:])
        if normalized.startswith("add card "):
            return self._cli_handle_add_card(shlex.split(text)[2:])

        return None

    def _cli_help_text(self) -> str:
        return "\n".join(
            [
                "Operator CLI is available.",
                "Commands:",
                "- /list departments",
                "- /list <teams|environments|epics|rocks|roles|dialects|skills> [department]",
                "- /show <team|environment|epic|rock> <name> [department]",
                "- /create <team|environment|epic|rock> <name> [department]",
                "- /list-cards <epic> [department]",
                "- /add-card <epic> <seat> <priority> <summary...> [--department <department>]",
                "- /capabilities",
            ]
        )

    def _cli_handle_list(self, args: List[str]) -> str:
        if not args:
            return "Usage: /list <resource> [department]"
        resource = args[0].strip().lower()
        if resource == "departments":
            departments = sorted([p.name for p in self.model_root.iterdir() if p.is_dir()])
            return f"Departments ({len(departments)}): " + ", ".join(departments)
        if resource == "cards":
            if len(args) < 2:
                return "Usage: /list cards <epic> [department]"
            epic_name = self._slug_name(args[1])
            department = args[2] if len(args) > 2 else "core"
            return self._list_cards_for_epic(epic_name, department)
        department = args[1] if len(args) > 1 else "core"
        resource_dir = self._resource_dir(resource, department)
        if resource_dir is None:
            return f"Unknown list resource '{resource}'. Use /help."
        if not resource_dir.exists():
            return f"No '{resource}' directory found in department '{department}'."
        names = sorted([f.stem for f in resource_dir.glob("*.json")])
        return f"{resource.title()} in {department} ({len(names)}): " + ", ".join(names)

    def _cli_handle_show(self, args: List[str]) -> str:
        if len(args) < 2:
            return "Usage: /show <team|environment|epic|rock> <name> [department]"
        resource = args[0].strip().lower()
        name = self._slug_name(args[1])
        department = args[2] if len(args) > 2 else None
        path = self._find_asset_path(resource, name, department)
        if path is None or not path.exists():
            return f"{resource} '{name}' not found."
        data = json.loads(self.fs.read_file_sync(str(path)))
        return json.dumps(data, indent=2)

    def _cli_handle_create(self, args: List[str]) -> str:
        if len(args) < 2:
            return "Usage: /create <team|environment|epic|rock> <name> [department]"
        resource = args[0].strip().lower()
        name = self._slug_name(args[1])
        department = args[2] if len(args) > 2 else "core"
        resource_dir = self._resource_dir(f"{resource}s" if not resource.endswith("s") else resource, department)
        if resource_dir is None:
            resource_dir = self._resource_dir(resource, department)
        if resource_dir is None:
            return f"Unknown create resource '{resource}'. Use /help."
        resource_dir.mkdir(parents=True, exist_ok=True)
        target = resource_dir / f"{name}.json"
        if target.exists():
            return f"{resource} '{name}' already exists in {department}."

        if resource in {"team", "teams"}:
            payload = self._team_template(name)
        elif resource in {"environment", "environments"}:
            payload = self._environment_template(name)
        elif resource in {"epic", "epics"}:
            payload = self._epic_template(name)
        elif resource in {"rock", "rocks"}:
            payload = self._rock_template(name, department)
        else:
            return f"Create for '{resource}' is not supported."

        self.fs.write_file_sync(str(target), payload)
        return f"Created {resource.rstrip('s')} '{name}' at {target.as_posix()}."

    def _cli_handle_list_cards(self, args: List[str]) -> str:
        if not args:
            return "Usage: /list-cards <epic> [department]"
        epic_name = self._slug_name(args[0])
        department = args[1] if len(args) > 1 else "core"
        return self._list_cards_for_epic(epic_name, department)

    def _list_cards_for_epic(self, epic_name: str, department: str) -> str:
        path = self._find_asset_path("epic", epic_name, department)
        if path is None or not path.exists():
            return f"Epic '{epic_name}' not found in {department}."
        epic_data = json.loads(self.fs.read_file_sync(str(path)))
        cards = list(epic_data.get("cards") or epic_data.get("issues") or [])
        if not cards:
            return f"Epic '{epic_name}' has no cards."
        lines = [f"Cards in {epic_name} ({len(cards)}):"]
        for idx, card in enumerate(cards, start=1):
            summary = str(card.get("summary") or card.get("name") or "Untitled")
            seat = str(card.get("seat") or "unspecified")
            priority = str(card.get("priority") or "n/a")
            lines.append(f"{idx}. [{seat}] p={priority} {summary}")
        return "\n".join(lines)

    def _cli_handle_add_card(self, args: List[str]) -> str:
        if len(args) < 4:
            return "Usage: /add-card <epic> <seat> <priority> <summary...> [--department <department>]"
        department = "core"
        filtered: list[str] = []
        i = 0
        while i < len(args):
            token = args[i]
            if token == "--department" and i + 1 < len(args):
                department = args[i + 1]
                i += 2
                continue
            filtered.append(token)
            i += 1
        if len(filtered) < 4:
            return "Usage: /add-card <epic> <seat> <priority> <summary...> [--department <department>]"
        epic_name = self._slug_name(filtered[0])
        seat = filtered[1]
        try:
            priority = float(filtered[2])
        except ValueError:
            return f"Invalid priority '{filtered[2]}'. Use a numeric value."
        summary = " ".join(filtered[3:]).strip()
        if not summary:
            return "Card summary is required."

        path = self._find_asset_path("epic", epic_name, department)
        if path is None or not path.exists():
            return f"Epic '{epic_name}' not found in {department}."
        epic_data = json.loads(self.fs.read_file_sync(str(path)))
        key = "cards" if "cards" in epic_data else "issues"
        if key not in epic_data:
            key = "cards"
            epic_data[key] = []
        epic_data[key].append({"summary": summary, "seat": seat, "priority": priority})
        self.fs.write_file_sync(str(path), epic_data)
        return f"Added card to epic '{epic_name}' in {department}: [{seat}] p={priority} {summary}"

    def _resource_dir(self, resource: str, department: str) -> Path | None:
        normalized = resource.strip().lower()
        aliases = {
            "team": "teams",
            "teams": "teams",
            "environment": "environments",
            "environments": "environments",
            "epic": "epics",
            "epics": "epics",
            "rock": "rocks",
            "rocks": "rocks",
            "role": "roles",
            "roles": "roles",
            "dialect": "dialects",
            "dialects": "dialects",
            "skill": "skills",
            "skills": "skills",
            "contract": "contracts",
            "contracts": "contracts",
            "artifact": "artifacts",
            "artifacts": "artifacts",
        }
        folder = aliases.get(normalized)
        if not folder:
            return None
        return self.model_root / department / folder

    def _find_asset_path(self, resource: str, name: str, department: str | None = None) -> Path | None:
        search_departments = [department] if department else sorted([p.name for p in self.model_root.iterdir() if p.is_dir()])
        for dept in search_departments:
            resource_dir = self._resource_dir(resource, dept)
            if resource_dir is None:
                continue
            candidate = resource_dir / f"{name}.json"
            if candidate.exists():
                return candidate
        return None

    def _slug_name(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_") or "unnamed"

    def _team_template(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "description": f"Team '{name}' generated by Operator CLI.",
            "roles": {
                "coder": {
                    "name": "coder",
                    "description": "Software Engineer role focusing on implementation.",
                    "tools": ["read_file", "write_file", "list_directory", "add_issue_comment", "get_issue_context", "update_issue_status"],
                },
                "code_reviewer": {
                    "name": "code_reviewer",
                    "description": "Code reviewer role for governance and quality review.",
                    "tools": ["read_file", "list_directory", "add_issue_comment", "get_issue_context", "update_issue_status"],
                },
            },
            "seats": {
                "coder": {"name": "Coder", "roles": ["coder"]},
                "code_reviewer": {"name": "Code Reviewer", "roles": ["code_reviewer"]},
                "integrity_guard": {"name": "Integrity Guard", "roles": ["integrity_guard"]},
            },
        }

    def _environment_template(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "description": f"Environment '{name}' generated by Operator CLI.",
            "model": "qwen3-coder:latest",
            "temperature": 0.2,
            "seed": 42,
            "params": {},
        }

    def _epic_template(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "description": f"Epic '{name}' generated by Operator CLI.",
            "team": "standard",
            "environment": "standard",
            "cards": [],
        }

    def _rock_template(self, name: str, department: str) -> Dict[str, Any]:
        rock_id = f"{self._slug_name(name).upper()}-ROCK"
        return {
            "id": rock_id,
            "name": name,
            "description": f"Rock '{name}' generated by Operator CLI.",
            "status": "active",
            "owner_department": department,
            "epics": [],
        }

    def _should_handle_as_conversation(self, message: str) -> bool:
        text = str(message or "").strip().lower()
        if not text:
            return True
        if len(text) <= 3:
            return True

        conversation_patterns = (
            r"^(hi|hey|hello|yo|sup|how are you)\b",
            r"\bthank(s| you)\b",
            r"\bcan you (chat|talk|converse)\b",
            r"\byou are not set up to converse\b",
            r"\blet('?s| us) chat\b",
        )
        for pattern in conversation_patterns:
            if re.search(pattern, text):
                return True

        structural_markers = (
            "create epic",
            "create issue",
            "create rock",
            "new epic",
            "new issue",
            "new rock",
            "adopt issue",
            "move issue",
            "assign team",
            "run active",
            "halt session",
            "archive card",
            "runtime policy",
            "settings",
        )
        return not any(marker in text for marker in structural_markers)

    def _conversation_reply(self, message: str) -> str:
        text = str(message or "").strip()
        if not text:
            return "I am here. You can chat with me or ask me to make a specific board change."

        lowered = text.lower()
        if "what can you do" in lowered or "capabilities" in lowered or "in this environment" in lowered:
            return self._cli_help_text()
        if (
            "tell me about this application" in lowered
            or "about this app" in lowered
            or "about this application" in lowered
            or "what is this application" in lowered
            or "what is this app" in lowered
        ):
            return (
                "This is Orket, an orchestration application for managing rocks, epics, cards, teams, and "
                "runtime policy. I can converse and I can operate the board through CLI-style commands like "
                "/list, /show, /create, /list-cards, and /add-card."
            )
        if re.search(r"\bcan you\b.*\b(converse|talk|chat)\b", lowered):
            return (
                "Yes. I can converse normally and also run Orket operations when you ask explicitly."
            )
        if lowered in {"what?", "what"}:
            return "I can explain capabilities, answer simple questions, and run explicit Orket CLI commands."
        if "didn't think so" in lowered:
            return "Fair pushback. Ask me anything and I will answer directly; use /help for command capabilities."
        if lowered in {"hi", "hey", "hello"}:
            return "Hi. I am here and can chat normally. If you want structural changes, ask explicitly."
        if lowered in {"cool", "nice", "great", "awesome"}:
            return "Nice. Want to keep chatting, or switch to a board action?"
        if "not set up to converse" in lowered:
            return "I can converse. I will only make structural changes when you ask for them explicitly."
        if "anything else" in lowered or "say anything else" in lowered:
            return "Yes. Ask about capabilities with /help, inspect assets with /list, or ask a direct question."
        math_answer = self._try_answer_math(text)
        if math_answer is not None:
            return math_answer
        return "Understood. What would you like to talk about?"

    def _try_answer_math(self, message: str) -> str | None:
        lowered = str(message or "").strip().lower()
        prefixes = ("what is ", "what's ", "calculate ", "compute ")
        expr = lowered
        for prefix in prefixes:
            if expr.startswith(prefix):
                expr = expr[len(prefix):]
                break
        expr = expr.strip().rstrip("?").strip()
        if not expr:
            return None

        if not re.fullmatch(r"[0-9\.\+\-\*\/\(\)\s]+", expr):
            return None

        try:
            node = ast.parse(expr, mode="eval")
        except SyntaxError:
            return None
        try:
            value = self._eval_arithmetic(node.body)
        except (ValueError, ZeroDivisionError):
            return None

        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)

    def _eval_arithmetic(self, node: ast.AST) -> float:
        if isinstance(node, ast.BinOp):
            left = self._eval_arithmetic(node.left)
            right = self._eval_arithmetic(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            raise ValueError("Unsupported arithmetic operator")
        if isinstance(node, ast.UnaryOp):
            value = self._eval_arithmetic(node.operand)
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.USub):
                return -value
            raise ValueError("Unsupported unary operator")
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("Unsupported expression")

