from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.extensions import ExtensionManager


def _load_payload(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("payload JSON must be an object")
    return data


async def _run(args: argparse.Namespace) -> int:
    manager = ExtensionManager(project_root=Path.cwd())
    result = await manager.run_workload(
        workload_id="textmystery_bridge_v1",
        input_config={
            "operation": args.operation,
            "textmystery_root": args.textmystery_root,
            "payload": _load_payload(Path(args.payload_file) if args.payload_file else None),
        },
        workspace=Path(args.workspace).resolve(),
        department=args.department,
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TextMystery bridge extension workload.")
    parser.add_argument("--operation", choices=["parity-check", "leak-check"], default="parity-check")
    parser.add_argument("--textmystery-root", default="C:/Source/Orket-Extensions/TextMystery")
    parser.add_argument("--payload-file", default=None, help="Path to JSON object payload passed to bridge endpoint.")
    parser.add_argument("--workspace", default="workspace/default")
    parser.add_argument("--department", default="core")
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
