"""Guided local project setup: orket setup or python -m orket.interfaces.setup_cli."""
import argparse
import asyncio
import os
import sys
from pathlib import Path

from orket.application.services.local_runtime_diagnostics import diagnose_local_runtime
from orket.application.services.setup_service import (
    ProviderSetup,
    SetupService,
    provider_choices,
    provider_setup_defaults,
)
from orket.application.services.user_settings_service import SettingsLocation
from orket.interfaces.doctor_cli import render_diagnostics
from orket.quickstart.governed_action_demo import run_governed_action_demo
from orket.settings import load_env


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orket setup", description=__doc__)
    parser.add_argument("--project", type=Path, help="Project directory; prompted when omitted.")
    for flag in ("name", "vision", "ethos", "workspace", "asset-root", "module-profile", "model-id", "base-url", "gguf-root"):
        parser.add_argument(f"--{flag}")
    parser.add_argument("--provider", choices=provider_choices())
    parser.add_argument("--non-interactive", action="store_true", help="Use flags/defaults without prompts.")
    parser.add_argument("--skip-check", action="store_true", help="Save project files; leave provider readiness unverified.")
    parser.add_argument("--run-example", action="store_true", help="Run the packaged offline approval example after setup.")
    parser.add_argument("--decision", choices=("approve", "deny"), help="Explicit decision for the offline example.")
    return parser


def _answer(value: str | None, label: str, default: str, *, unattended: bool) -> str:
    if value is not None:
        return value
    return default if unattended else input(f"{label} [{default}]: ").strip() or default


def _project_choices(args: argparse.Namespace) -> dict[str, str]:
    fields = (("name", "name", "Organization name", "Vibe Rail"),
              ("vision", "vision", "Vision", "Autonomous engineering excellence."),
              ("ethos", "ethos", "Ethos", "Local-first sovereignty."),
              ("workspace", "workspace", "Workspace path", "./workspace"),
              ("model", "asset_root", "Project asset path", "./model"),
              ("module_profile", "module_profile", "Module profile", "developer-local"))
    return {key: _answer(getattr(args, attribute), label, default, unattended=args.non_interactive)
            for key, attribute, label, default in fields}


def _provider_choices(args: argparse.Namespace, root: Path) -> ProviderSetup:
    captured = dict(os.environ)
    defaults = provider_setup_defaults(captured)
    provider = _answer(args.provider, "Provider", defaults["provider"],
                       unattended=args.non_interactive)
    defaults = provider_setup_defaults(captured, provider=provider)
    model = _answer(args.model_id, "Exact served model ID", defaults["model"], unattended=args.non_interactive)
    endpoint = _answer(args.base_url, "Provider endpoint", defaults["base_url"],
                       unattended=args.non_interactive)
    gguf = ""
    if provider == "llama_cpp":
        gguf = _answer(args.gguf_root, "GGUF directory (required)", "", unattended=args.non_interactive)
        if gguf:
            gguf = str((root / Path(gguf).expanduser()).resolve())
    return ProviderSetup(provider, model, endpoint, gguf)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.non_interactive and args.run_example and args.decision is None:
        parser.error("--run-example requires --decision in noninteractive mode")
    try:
        project = str(args.project) if args.project is not None else None
        root = Path(_answer(project, "Project directory", ".", unattended=args.non_interactive)).expanduser().resolve()
        print("Orket local setup\n")
        choices = _project_choices(args)
        provider = _provider_choices(args, root)
        location = SettingsLocation(root, os.environ.get("ORKET_DURABLE_ROOT", ".orket/durable"))
        result = asyncio.run(SetupService(root, location).initialize(choices, provider=provider))
        print("\nInitialization complete: project files saved; runtime readiness is checked separately.")
        print(f"Project: {root}\nConfig: {result['organization']}\nProvider settings: {result['environment']}")
        status = 0
        if args.skip_check:
            print("Provider and command readiness: not checked (--skip-check).")
        else:
            load_env(env_file=root / ".env")
            overrides = [key for key, value in provider.environment_values().items() if os.environ.get(key) != value]
            if overrides:
                print("Process environment overrides saved settings: " + ", ".join(overrides))
            report = asyncio.run(diagnose_local_runtime(root, environment=dict(os.environ)))
            render_diagnostics(report)
            status = 0 if report["ok"] else 1
        if args.run_example:
            print("\nOffline approval example: mock model; no provider inference.")
            decision = (lambda _prompt: args.decision) if args.decision else None
            asyncio.run(run_governed_action_demo(workspace=Path(result["workspace"]), input_func=decision))
        print('Next: run "orket doctor --project <directory> --inference" to check actual model inference.')
        print('Then run "orket demo local-agent --project <directory>" for the prepared provider-backed workflow.')
        return status
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except (OSError, ValueError, RuntimeError, EOFError) as exc:
        print(f"Initialization failed (earlier verified files may remain): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
