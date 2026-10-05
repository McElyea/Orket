"""CLI-only bridge from the challenge's admitted checks to retained CLI acceptance.

The caller passes the authored runtime verifier contract as one JSON argument.
This uses Orket's existing verifier and its native process ownership, rather than
interpreting exit codes or JSON assertions with a second implementation.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from orket.application.services.runtime_verifier import RuntimeVerifier


async def main(workspace: Path) -> None:
    contract = json.loads(sys.argv[1])
    if not isinstance(contract, dict) or not contract.get("commands"):
        raise ValueError("Challenge acceptance requires explicit commands")
    verifier = RuntimeVerifier(
        workspace,
        organization=SimpleNamespace(process_rules={"runtime_verifier_timeout_sec": 15}),
        issue_params={"runtime_verifier": contract},
    )
    result = await verifier.verify()
    print(json.dumps({"challenge_verification": {
        "errors": result.errors, "command_results": result.command_results,
        "overall_evidence_class": result.overall_evidence_class,
    }}), file=sys.stderr)
    payload = {"ok": result.ok, "commands": len(result.command_results)}
    if not result.ok:
        payload["errors"] = result.errors
    print(json.dumps(payload))


if __name__ == "__main__":
    asyncio.run(main(Path(__file__).resolve().parent.parent))
