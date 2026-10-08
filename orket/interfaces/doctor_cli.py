"""Public project diagnostics with explicit observation limits."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from orket.application.services.local_runtime_diagnostics import diagnose_local_runtime
from orket.application.services.setup_service import provider_choices
from orket.settings import load_env


def render_diagnostics(report: dict) -> None:
    print(f"Project: {report['project']}")
    print(f"Provider: {report['provider']} | model: {report['model']} | endpoint: {report['base_url']}")
    observed = report["provider_observation"]
    print("Model catalog admission: " + ("passed" if observed["catalog_admitted"] else "failed"))
    if observed.get("error"):
        print(observed["error"])
    print(f"Inference: {observed.get('inference', 'not_established')} | Metal: unverified")
    native = report["command_observation"]
    print(f"Native command check: {'passed' if native['ok'] else 'failed'} ({native['backend']})")
    if not native["ok"]:
        print("Runtime command execution is not ready; inspect the native ownership blocker before running workflows.")
    hardware = report["hardware"]
    print(f"Memory model: {hardware.get('memory_model', 'unknown')} | GPU: {hardware.get('gpu_observation', 'unobserved')}")
    print(report["scope"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orket doctor", description=__doc__)
    parser.add_argument("--project", type=Path, default=Path())
    parser.add_argument("--provider", choices=provider_choices(), default="")
    parser.add_argument("--model-id", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--inference", action="store_true", help="Run a bounded arithmetic inference check.")
    parser.add_argument("--timeout-seconds", type=float, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.project.expanduser().resolve(strict=True)
        load_env(env_file=root / ".env")
        report = asyncio.run(diagnose_local_runtime(root, environment=dict(os.environ), provider_name=args.provider,
            model_id=args.model_id, base_url=args.base_url, inference=args.inference, timeout_seconds=args.timeout_seconds))
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            render_diagnostics(report)
        return 0 if report["ok"] else 1
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Diagnostics failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
