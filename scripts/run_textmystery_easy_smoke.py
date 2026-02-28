from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer
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


def _start_local_contract_server(textmystery_src: Path, host: str, port: int) -> tuple[ThreadingHTTPServer, threading.Thread]:
    if str(textmystery_src) not in sys.path:
        sys.path.insert(0, str(textmystery_src))
    from textmystery.cli.live_server import _Handler  # type: ignore

    server = ThreadingHTTPServer((host, port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


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


async def _run_bridge(endpoint_base_url: str) -> dict[str, Any]:
    manager = ExtensionManager(project_root=PROJECT_ROOT)
    parity_result = await manager.run_workload(
        workload_id="textmystery_bridge_v1",
        input_config={
            "operation": "parity-check",
            "endpoint_base_url": endpoint_base_url,
            "payload": _default_parity_payload(),
        },
        workspace=PROJECT_ROOT,
        department="core",
    )
    leak_result = await manager.run_workload(
        workload_id="textmystery_bridge_v1",
        input_config={
            "operation": "leak-check",
            "endpoint_base_url": endpoint_base_url,
            "payload": _default_leak_payload(),
        },
        workspace=PROJECT_ROOT,
        department="core",
    )
    return {"parity": parity_result.summary, "leak": leak_result.summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="One-command TextMystery bridge smoke run.")
    parser.add_argument("--textmystery-root", default=None, help="Path to TextMystery project root.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    register_bridge_main()

    textmystery_src = _resolve_textmystery_src(args.textmystery_root)
    if not textmystery_src.exists():
        print(f"[FAIL] TextMystery src path not found: {textmystery_src}")
        print("Set --textmystery-root or TEXTMYSTERY_ROOT.")
        return 1

    server, thread = _start_local_contract_server(textmystery_src, args.host, args.port)
    endpoint = f"http://{args.host}:{args.port}"
    try:
        summaries = asyncio.run(_run_bridge(endpoint))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)

    parity_contract = summaries.get("parity", {}).get("contract_response", {})
    leak_contract = summaries.get("leak", {}).get("contract_response", {})
    ok_parity = isinstance(parity_contract, dict) and "world_digest" in parity_contract
    ok_leak = isinstance(leak_contract, dict) and bool(leak_contract.get("ok")) is True

    print("=== TextMystery Easy Smoke ===")
    print(f"endpoint={endpoint}")
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
