from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Dict, List


class DriverCliMixin:
    async def _try_cli_command(self, message: str) -> str | None:
        text = str(message or "").strip()
        if not text:
            return None

        normalized = text.lower()
        if normalized in {"help", "/help", "what can you do", "capabilities", "/capabilities"}:
            return self._capabilities_summary()
        if "what can you do" in normalized or "capabilities" in normalized:
            return self._capabilities_summary()
        if "in this environment" in normalized and any(
            token in normalized for token in ("what can", "available", "do here", "use here")
        ):
            return self._capabilities_summary()

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
        if verb == "reforge":
            return await self._cli_handle_reforge(args)
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

    async def _cli_handle_reforge(self, args: List[str]) -> str:
        if not args:
            return "Usage: /reforge <inspect|run> [options]"
        sub = str(args[0]).strip().lower()
        flags = self._parse_reforge_flags(args[1:])
        if sub == "inspect":
            input_dir = flags.get("in") or flags.get("input") or "."
            payload = {
                "route_id": flags.get("route"),
                "input_dir": input_dir,
                "mode": flags.get("mode"),
                "scenario_pack": flags.get("scenario-pack") or flags.get("scenario_pack"),
            }
            result = self.reforger_tools.inspect(payload)
            if not result.get("ok"):
                return (
                    "Reforger inspect failed.\n"
                    + f"route_id={result.get('route_id')}\n"
                    + f"errors={result.get('errors')}\n"
                    + f"artifact_root={result.get('artifact_root')}"
                )
            return (
                "Reforger inspect ok.\n"
                + f"route_id={result.get('route_id')}\n"
                + f"runnable={result.get('runnable')}\n"
                + f"suite_ready={result.get('suite_ready')}\n"
                + f"missing_inputs={result.get('missing_inputs')}\n"
                + f"suite_requirements={result.get('suite_requirements')}\n"
                + f"artifact_root={result.get('artifact_root')}"
            )
        if sub == "run":
            route_id = flags.get("route")
            input_dir = flags.get("in") or flags.get("input")
            output_dir = flags.get("out") or flags.get("output")
            if not route_id or not input_dir or not output_dir:
                return (
                    "Usage: /reforge run --route <id> --in <dir> --out <dir> "
                    "[--mode truth_only] [--scenario-pack <id|path>] [--seed N] [--max-iters K]"
                )
            inspect_payload = {
                "route_id": route_id,
                "input_dir": input_dir,
                "mode": flags.get("mode"),
                "scenario_pack": flags.get("scenario-pack") or flags.get("scenario_pack"),
            }
            inspect_result = self.reforger_tools.inspect(inspect_payload)
            suite_ready = bool(inspect_result.get("suite_ready"))
            force = self._flag_enabled(flags, "force")
            if not suite_ready and not force:
                return (
                    "Reforger run blocked: suite_ready=false.\n"
                    + f"missing_inputs={inspect_result.get('missing_inputs')}\n"
                    + f"errors={inspect_result.get('errors')}\n"
                    + f"suite_requirements={inspect_result.get('suite_requirements')}\n"
                    + "Re-run with --force to compile anyway."
                )
            seed_raw = flags.get("seed")
            max_iters_raw = flags.get("max-iters") or flags.get("max_iters")
            run_payload = {
                "route_id": route_id,
                "input_dir": input_dir,
                "output_dir": output_dir,
                "mode": flags.get("mode"),
                "scenario_pack": flags.get("scenario-pack") or flags.get("scenario_pack"),
                "seed": int(seed_raw) if seed_raw and str(seed_raw).isdigit() else 0,
                "max_iters": int(max_iters_raw) if max_iters_raw and str(max_iters_raw).isdigit() else 8,
                "forced": force,
                "force_reason": "suite_ready_false" if force and not suite_ready else "",
            }
            result = self.reforger_tools.run(run_payload)
            if not result.get("ok"):
                return (
                    "Reforger run failed.\n"
                    + f"route_id={result.get('route_id')}\n"
                    + f"errors={result.get('errors')}\n"
                    + f"artifact_root={result.get('artifact_root')}"
                )
            return (
                f"Reforger run ok={result.get('ok')}\n"
                + f"forced={result.get('forced')}\n"
                + f"force_reason={result.get('force_reason')}\n"
                + f"suite_ready={result.get('suite_ready')}\n"
                + f"output_paths={result.get('output_paths')}\n"
                + f"artifact_root={result.get('artifact_root')}"
            )
        return "Usage: /reforge <inspect|run> [options]"

    def _parse_reforge_flags(self, tokens: List[str]) -> Dict[str, str]:
        flags: Dict[str, str] = {}
        i = 0
        while i < len(tokens):
            token = str(tokens[i]).strip()
            if token.startswith("--"):
                key = token[2:]
                value: str = "true"
                if i + 1 < len(tokens) and not str(tokens[i + 1]).startswith("--"):
                    value = str(tokens[i + 1])
                    i += 1
                flags[key] = value
                i += 1
                continue
            i += 1
        return flags

    def _flag_enabled(self, flags: Dict[str, str], name: str) -> bool:
        value = str(flags.get(name, "")).strip().lower()
        return value in {"1", "true", "yes", "on"}

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
                "- /reforge inspect [--route <id>] [--in <dir>] [--mode truth_only] [--scenario-pack <id|path>]",
                "- /reforge run --route <id> --in <dir> --out <dir> [--mode truth_only] [--scenario-pack <id|path>] [--seed N] [--max-iters K] [--force]",
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
