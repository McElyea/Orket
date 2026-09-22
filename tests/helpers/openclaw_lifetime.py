"""Fixture composition only; the adapter executes actual native JSONL traffic."""
import json
import sys
from pathlib import Path

import psutil

from orket.adapters.execution.openclaw_jsonl_adapter import OpenClawJsonlSubprocessAdapter
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from tests.integration.test_verification_process_lifetime import WORKER, observe_processes

FIXTURE = Path(__file__).parents[1] / "integration/openclaw_lifetime_worker.py"


def adapter_for(root, mode, flags):
    return OpenClawJsonlSubprocessAdapter(
        command=[sys.executable, str(FIXTURE), str(root), mode, str(WORKER), *flags],
        runner=CommandProcessSupervisor(root, cancellation_event="openclaw_fixture_interrupted"),
        cwd=root, io_timeout_seconds=5,
    )


def observe_fixture(root):
    processes = observe_processes(root)
    try:
        marker = json.loads((root / "adapter-ready.json").read_text(encoding="utf-8"))
        processes.append(psutil.Process(marker["pid"]))
    except (FileNotFoundError, psutil.NoSuchProcess):
        pass  # A missing/dead fixture leader cannot establish readiness.
    return processes
