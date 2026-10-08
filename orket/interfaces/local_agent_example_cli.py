"""Public rendering of the prepared local provider workflow."""
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from orket.application.services.local_agent_example_service import run_local_agent_example
from orket.settings import load_env


def handle_local_agent_example(args) -> int:
    try:
        root = Path(args.project).expanduser().resolve(strict=True)
        target = (root / args.output).resolve()
        load_env(env_file=root / ".env")
        result = asyncio.run(run_local_agent_example(root, target=target, now=datetime.now(UTC),
                                                     environment=dict(os.environ)))
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        result = {"ok": False, "error": str(exc), "observed_path": "primary", "observed_result": "failure"}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print("Ticket report verified by Orket. Metal use remains unverified.")
        print(f"Evidence: {result['example']['report']}")
        print(f"Inspect: orket agent inspect {result['run']['run_id']} --db \"{result['db_path']}\"")
        print(f"Replay: orket agent replay {result['run']['run_id']} --db \"{result['db_path']}\"")
    else:
        print(f"Example failed: {result.get('error') or result.get('normalized_reason')}")
        print("Earlier files and run state may remain; retain them when diagnosing the failure.")
    return 0 if result["ok"] else 1
