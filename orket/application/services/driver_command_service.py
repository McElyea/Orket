"""Captured operator commands with owned resource/compiler effects."""
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.driver_resource_store import DriverResourceStore
from orket.application.services.driver_reforger_command import DriverReforgerCommand
from orket.application.services.driver_resource_commands import DriverResourceCommands
from orket.application.services.reforger_service import ReforgerService
from orket.runtime.config.config_loader import ConfigLoader


async def collect_driver_inventory(project_root: Path, model_root: Path, environment: Mapping[str, str]) -> dict:
    project, model, captured_environment = Path(project_root), Path(model_root), dict(environment)
    if not project.is_absolute() or not model.is_absolute():
        raise ValueError("DRIVER_INVENTORY_ROOTS_MUST_BE_ABSOLUTE")

    def collect() -> dict:
        loader = ConfigLoader(project, "core", environment=captured_environment)
        return {"inventory": DriverResourceStore(model).inventory(),
                "active_rocks": loader.list_assets("rocks"), "active_epics": loader.list_assets("epics")}

    return await run_owned_thread(collect, label="driver-inventory")


@dataclass(frozen=True)
class DriverCommandService:
    model_root: Path
    reforger: ReforgerService | None
    capability_lines: tuple[str, ...]

    async def execute(self, message: str) -> str | None:
        text = str(message or "").strip()
        normalized = text.lower()
        if not text:
            return None
        is_help = normalized in {"help", "/help", "capabilities", "/capabilities"} or any(
            phrase in normalized for phrase in ("what can you do", "capabilities", "in this environment"))
        command_text = text[1:].strip() if text.startswith("/") else text
        verbs = {"list", "show", "create", "add-card", "add_card", "list-cards", "list_cards", "reforge"}
        if not is_help and not (text.startswith("/") or command_text.split(" ", 1)[0].lower() in verbs):
            return None
        try:
            tokens = shlex.split(command_text)
        except ValueError:
            return "Invalid command syntax. Use /help for examples."
        if not tokens:
            return None
        verb, args = tokens[0].lower(), tokens[1:]
        root = Path(self.model_root)
        lines, reforger = tuple(self.capability_lines), self.reforger
        try:
            if (is_help or verb in verbs - {"reforge"}) and not root.is_absolute():
                raise ValueError("DRIVER_MODEL_ROOT_MUST_BE_ABSOLUTE")
            if is_help:
                return await run_owned_thread(lambda: _capabilities(root, lines), label="driver-capabilities")
            if verb == "reforge":
                if reforger is None:
                    raise ValueError("DRIVER_REFORGER_UNAVAILABLE")
                return await DriverReforgerCommand(reforger).execute(args)
            if verb not in verbs:
                return None
            return await run_owned_thread(
                lambda: DriverResourceCommands(DriverResourceStore(root)).execute(verb, args), label="driver-command")
        except (OSError, ValueError) as exc:
            return f"Error: {exc}"


def _capabilities(root: Path, lines: tuple[str, ...]) -> str:
    departments = DriverResourceStore(root).departments()
    summary = [cli_help_text(), *lines]
    if departments:
        summary.append(f"Detected departments: {', '.join(departments)}")
    return "\n".join(summary)


def cli_help_text() -> str:
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
            (
                "- /reforge run --route <id> --in <dir> --out <dir> "
                "[--mode truth_only] [--scenario-pack <id|path>] "
                "[--seed N] [--max-iters K] [--force]"
            ),
            "- /capabilities",
        ]
    )
