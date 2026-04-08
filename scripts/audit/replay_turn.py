#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.orchestration.engine import OrchestrationEngine
from scripts.audit.audit_support import normalize_text, now_utc_iso, sha256_text, text_diff_location, write_report
from scripts.probes.probe_support import is_environment_blocker, json_safe

DEFAULT_OUTPUT = "benchmarks/results/audit/replay_turn.json"


def _load_replay_source(
    *,
    workspace: Path,
    session_id: str,
    issue_id: str,
    turn_index: int,
    role: str | None,
) -> dict[str, Any]:
    engine = OrchestrationEngine(Path(workspace).resolve())
    return engine.replay_turn(
        session_id=str(session_id),
        issue_id=str(issue_id),
        turn_index=int(turn_index),
        role=role,
    )


async def _default_replay_call(
    *,
    messages: list[dict[str, str]],
    model: str,
    runtime_context: dict[str, Any],
) -> dict[str, Any]:
    provider = LocalModelProvider(model=model, temperature=0.0, timeout=300)
    try:
        response = await provider.complete(messages, runtime_context=runtime_context)
    finally:
        await provider.close()
    return {
        "content": str(response.content or ""),
        "raw": json_safe(dict(response.raw or {})),
    }


async def replay_turn_report(
    *,
    workspace: Path,
    session_id: str,
    issue_id: str,
    turn_index: int,
    role: str | None = None,
    model_override: str | None = None,
    replay_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    replay_source = await asyncio.to_thread(
        _load_replay_source,
        workspace=Path(workspace).resolve(),
        session_id=str(session_id),
        issue_id=str(issue_id),
        turn_index=int(turn_index),
        role=role,
    )
    messages = replay_source.get("messages")
    checkpoint = replay_source.get("checkpoint")
    original_response = normalize_text(str(replay_source.get("model_response") or ""))
    if not isinstance(messages, list) or not isinstance(checkpoint, dict):
        raise ValueError("persisted_turn_artifacts_invalid")
    model = str(model_override or checkpoint.get("model") or "").strip()
    if not model:
        raise ValueError("replay_model_missing")
    runtime_context = {
        "session_id": str(session_id),
        "issue_id": str(issue_id),
        "turn_index": int(turn_index),
        "role": str(checkpoint.get("role") or role or ""),
    }
    runner = replay_call or _default_replay_call
    try:
        replayed = await runner(messages=messages, model=model, runtime_context=runtime_context)
    except Exception as exc:  # noqa: BLE001
        blocked = is_environment_blocker(exc)
        return {
            "schema_version": "audit.replay_turn.v1",
            "recorded_at_utc": now_utc_iso(),
            "proof_kind": "live" if blocked else "structural",
            "observed_path": "blocked" if blocked else "primary",
            "observed_result": "environment blocker" if blocked else "failure",
            "workspace": str(Path(workspace).resolve()),
            "session_id": str(session_id),
            "issue_id": str(issue_id),
            "turn_index": int(turn_index),
            "role": str(role or checkpoint.get("role") or ""),
            "model": model,
            "stability_status": "blocked",
            "structural_verdict": {
                "status": "blocked",
                "match": False,
                "original_sha256": sha256_text(original_response),
                "replayed_sha256": None,
            },
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    replayed_response = normalize_text(str(replayed.get("content") or ""))
    match = replayed_response == original_response
    status = "stable" if match else "diverged"
    diff = text_diff_location(original_response, replayed_response)
    return {
        "schema_version": "audit.replay_turn.v1",
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live",
        "observed_path": "primary",
        "observed_result": "success" if match else "failure",
        "workspace": str(Path(workspace).resolve()),
        "session_id": str(session_id),
        "issue_id": str(issue_id),
        "turn_index": int(turn_index),
        "role": str(role or checkpoint.get("role") or ""),
        "model": model,
        "stability_status": status,
        "structural_verdict": {
            "status": status,
            "match": match,
            "first_diff": diff,
            "original_sha256": sha256_text(original_response),
            "replayed_sha256": sha256_text(replayed_response),
        },
        "replay_turn": {
            "turn_dir": str(replay_source.get("turn_dir") or ""),
            "checkpoint_model": str(checkpoint.get("model") or ""),
            "messages_count": len(messages),
            "original_response_chars": len(original_response),
            "replayed_response_chars": len(replayed_response),
        },
        "provider_raw": replayed.get("raw") if isinstance(replayed.get("raw"), dict) else {},
    }


def build_report(
    *,
    workspace: Path,
    session_id: str,
    issue_id: str,
    turn_index: int,
    role: str | None = None,
    model_override: str | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        replay_turn_report(
            workspace=workspace,
            session_id=session_id,
            issue_id=issue_id,
            turn_index=turn_index,
            role=role,
            model_override=model_override,
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay one preserved turn and compare against model_response.txt.")
    parser.add_argument("--workspace", required=True, help="Workspace root for the run.")
    parser.add_argument("--session-id", required=True, help="Run/session id.")
    parser.add_argument("--issue-id", required=True, help="Issue id containing the turn.")
    parser.add_argument("--turn-index", required=True, type=int, help="1-based turn index.")
    parser.add_argument("--role", default=None, help="Optional role suffix filter.")
    parser.add_argument("--model", default=None, help="Optional model override.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Stable rerunnable JSON output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted JSON payload.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output_path = Path(str(args.output)).resolve()
    payload = build_report(
        workspace=Path(str(args.workspace)).resolve(),
        session_id=str(args.session_id),
        issue_id=str(args.issue_id),
        turn_index=int(args.turn_index),
        role=str(args.role).strip() or None if args.role is not None else None,
        model_override=str(args.model).strip() or None if args.model is not None else None,
    )
    persisted = write_report(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "output_path": str(output_path)}, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"stability_status={persisted.get('stability_status')}",
                    f"match={((persisted.get('structural_verdict') or {}).get('match') if isinstance(persisted.get('structural_verdict'), dict) else '')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if str(persisted.get("stability_status") or "") == "stable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
