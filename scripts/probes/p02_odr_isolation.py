from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.kernel.v1.canon import raw_signature
from orket.kernel.v1.odr.live_runner import run_live_refinement
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from scripts.probes.probe_support import applied_probe_env, is_environment_blocker, now_utc_iso, write_report

DEFAULT_OUTPUT = "benchmarks/results/probes/p02_odr_isolation.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 probe P-02: ODR isolation against a real local model.")
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--ollama-host", default="")
    parser.add_argument("--task", default="Define requirements for a Python CLI tool that renames files based on metadata")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


async def _run_once(args: argparse.Namespace, run_index: int) -> dict[str, Any]:
    architect_provider = LocalModelProvider(
        model=str(args.model),
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
    )
    auditor_provider = LocalModelProvider(
        model=str(args.model),
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
    )
    try:
        result = await run_live_refinement(
            task=str(args.task),
            architect_client=architect_provider,
            auditor_client=auditor_provider,
            max_rounds=int(args.max_rounds),
        )
    finally:
        await architect_provider.close()
        await auditor_provider.close()

    return {
        "run_index": int(run_index),
        "model": str(args.model),
        **result,
        "history_v_count": len(result.get("history_v") or []),
        "raw_signature": raw_signature(
            {
                "history_v": list(result.get("history_v") or []),
                "stop_reason": result.get("stop_reason"),
            }
        ),
    }


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    stop_reasons: dict[str, int] = {}
    signatures: list[str] = []
    for row in results:
        key = str(row.get("stop_reason") or "NONE")
        stop_reasons[key] = stop_reasons.get(key, 0) + 1
        signatures.append(str(row.get("raw_signature") or ""))
    unique_signatures = len({item for item in signatures if item})
    return {
        "stop_reason_distribution": stop_reasons,
        "unique_raw_signatures": unique_signatures,
        "determinism": "STABLE" if results and unique_signatures == 1 else f"VARIABLE ({unique_signatures} unique)",
    }


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    with applied_probe_env(
        provider=str(args.provider),
        ollama_host=str(args.ollama_host or "").strip() or None,
        disable_sandbox=True,
    ):
        for run_index in range(1, int(args.runs) + 1):
            results.append(await _run_once(args, run_index))
    return {
        "schema_version": "phase1_probe.p02.v1",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-02",
        "probe_status": "observed",
        "proof_kind": "live",
        "observed_path": "primary",
        "observed_result": "success",
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "task": str(args.task),
        "runs_requested": int(args.runs),
        "max_rounds": int(args.max_rounds),
        "results": results,
        "summary": _summary(results),
    }


def _blocked_payload(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    blocked = is_environment_blocker(error)
    return {
        "schema_version": "phase1_probe.p02.v1",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-02",
        "probe_status": "blocked",
        "proof_kind": "live",
        "observed_path": "blocked" if blocked else "primary",
        "observed_result": "environment blocker" if blocked else "failure",
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "task": str(args.task),
        "error_type": type(error).__name__,
        "error": str(error),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_path = Path(str(args.output)).resolve()
    try:
        payload = asyncio.run(_run_probe(args))
    except Exception as exc:  # noqa: BLE001
        payload = _blocked_payload(args, exc)

    persisted = write_report(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "output_path": str(output_path)}, indent=2, ensure_ascii=True))
    else:
        summary = persisted.get("summary") if isinstance(persisted.get("summary"), dict) else {}
        print(
            " ".join(
                [
                    f"probe_status={persisted.get('probe_status')}",
                    f"observed_result={persisted.get('observed_result')}",
                    f"determinism={summary.get('determinism', '')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if str(persisted.get("probe_status") or "") == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
