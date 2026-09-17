"""Separate interpreter whose normal asyncio shutdown cancels an owned command."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.logging import subscribe_to_events


async def main(root, caller):
    worker = Path(__file__).with_name("verification_lifetime_worker.py")
    command = [sys.executable, str(worker), str(root), "2", "detached", "ignore-term"]
    if caller == "verification":
        verifier = RuntimeVerifier(root, issue_params={"runtime_verifier": {"commands": [command]}})
        invocation = verifier.verify()
    else:
        assert caller == "outward-command"
        service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY, workspace_root=root)
        invocation = service.invoke("run_command", {"command": command})
    await asyncio.to_thread((root / "fixture-bootstrap-ready").touch)
    asyncio.create_task(invocation)
    for _ in range(500):
        if await asyncio.to_thread((root / "shutdown-now").exists):
            return  # asyncio.run cancels all live tasks, including adapter collectors.
        await asyncio.sleep(0.02)
    raise RuntimeError("Acceptance driver did not request shutdown")


if __name__ == "__main__":
    subscribe_to_events(lambda event: print(json.dumps(event), flush=True))
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2]))
