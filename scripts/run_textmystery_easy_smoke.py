from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.extensions.manager import ExtensionManager
from scripts.register_textmystery_bridge_extension import main as register_bridge_main


def _resolve_textmystery_src(args_root: str | None) -> Path:
    if args_root:
        return Path(args_root).resolve() / "src"
    env_root = str(os.getenv("TEXTMYSTERY_ROOT", "")).strip()
    if env_root:
        return Path(env_root).resolve() / "src"
    return Path(r"C:\Source\Orket-Extensions\TextMystery\src")


def _default_parity_payload() -> dict[str, Any]:
    return {
        "run_header": {
            "seed": 12345,
            "scene_id": "SCENE_001",
            "npc_ids": ["NICK_VALE", "NADIA_BLOOM", "VICTOR_SLATE", "GABE_ROURKE"],
            "difficulty": "normal",
            "content_version": "dev",
            "generator_version": "worldgen_v1",
        },
        "transcript_inputs": [
            {"turn": 1, "npc_id": "NICK_VALE", "raw_question": "Where were you at 11:03?"},
            {"turn": 2, "npc_id": "GABE_ROURKE", "raw_question": "Who had access to the panel?"},
            {"turn": 3, "accuse": {"npc_id": "VICTOR_SLATE"}},
        ],
    }


def _default_leak_payload() -> dict[str, Any]:
    return {
        "allowed_entities": [
            "NICK_VALE",
            "NADIA_BLOOM",
            "VICTOR_SLATE",
            "GABE_ROURKE",
            "PANEL",
            "CASE",
            "CAMERA",
            "11:03",
        ],
        "allowed_fact_values": ["11:03", "PANEL"],
        "text": "That's not something I'm discussing.",
    }


async def _run_bridge(textmystery_root: str) -> dict[str, Any]:
    manager = ExtensionManager(project_root=PROJECT_ROOT)
    parity_result = await manager.run_workload(
        workload_id="textmystery_bridge_v1",
        input_config={
            "operation": "parity-check",
            "textmystery_root": textmystery_root,
            "payload": _default_parity_payload(),
        },
        workspace=PROJECT_ROOT,
        department="core",
    )
    leak_result = await manager.run_workload(
        workload_id="textmystery_bridge_v1",
        input_config={
            "operation": "leak-check",
            "textmystery_root": textmystery_root,
            "payload": _default_leak_payload(),
        },
        workspace=PROJECT_ROOT,
        department="core",
    )
    return {"parity": parity_result.summary, "leak": leak_result.summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="One-command TextMystery bridge smoke run (direct SDK/local contract).")
    parser.add_argument("--textmystery-root", default=None, help="Path to TextMystery project root.")
    args = parser.parse_args()

    register_bridge_main()

    textmystery_src = _resolve_textmystery_src(args.textmystery_root)
    if not textmystery_src.exists():
        print(f"[FAIL] TextMystery src path not found: {textmystery_src}")
        print("Set --textmystery-root or TEXTMYSTERY_ROOT.")
        return 1

    textmystery_root = str(textmystery_src.parent)
    summaries = asyncio.run(_run_bridge(textmystery_root))

    parity_output = summaries.get("parity", {}).get("output", {})
    leak_output = summaries.get("leak", {}).get("output", {})
    parity_contract = parity_output.get("contract_response", {}) if isinstance(parity_output, dict) else {}
    leak_contract = leak_output.get("contract_response", {}) if isinstance(leak_output, dict) else {}
    ok_parity = isinstance(parity_contract, dict) and "world_digest" in parity_contract
    ok_leak = isinstance(leak_contract, dict) and bool(leak_contract.get("ok")) is True

    print("=== TextMystery Easy Smoke ===")
    print(f"textmystery_root={textmystery_root}")
    print(f"parity_ok={ok_parity}")
    print(f"leak_ok={ok_leak}")
    print("parity_summary=" + json.dumps(summaries.get("parity", {}), indent=2, sort_keys=True))
    print("leak_summary=" + json.dumps(summaries.get("leak", {}), indent=2, sort_keys=True))
    if ok_parity and ok_leak:
        print("RESULT=PASS")
        return 0
    print("RESULT=FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
