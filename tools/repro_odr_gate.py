from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.kernel.v1.canon import canonical_bytes, first_diff_path, raw_signature  # noqa: E402
from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round  # noqa: E402


def _load_fixture(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _permute_fixture(fixture: Dict[str, Any], seed: int, perm_index: int) -> Dict[str, Any]:
    payload = json.loads(json.dumps(fixture))
    rng = random.Random(seed + (perm_index * 7919))
    graph = payload.get("graph", {})
    for key in ("nodes", "edges", "relationships", "links", "refs"):
        values = graph.get(key)
        if isinstance(values, list):
            rng.shuffle(values)
    return payload


def _run_fixture_rounds(payload: Dict[str, Any], round_limit: int) -> Dict[str, Any]:
    cfg = ReactorConfig()
    state = ReactorState()
    rounds = payload.get("rounds", [])
    for index, round_payload in enumerate(rounds):
        if round_limit > 0 and index >= round_limit:
            break
        state = run_round(
            state,
            str(round_payload.get("architect_raw", "")),
            str(round_payload.get("auditor_raw", "")),
            cfg,
        )
        if state.stop_reason is not None:
            break
    return {
        "fixture_id": payload.get("id"),
        "graph": payload.get("graph", {}),
        "history_v": list(state.history_v),
        "history_rounds": list(state.history_rounds),
        "stop_reason": state.stop_reason,
    }


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _print_failure(
    *,
    seed: int,
    perm_index: int,
    round_index: int,
    diff_path: str,
    stop_reason: str,
    reason: str,
) -> int:
    print(f"seed={seed}")
    print(f"perm_index={perm_index}")
    print(f"round={round_index}")
    print(f"first_diff_path={diff_path}")
    print(f"stop_reason={stop_reason}")
    print(f"failure_reason={reason}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproduce one ODR determinism gate case.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--perm-index", type=int, required=True)
    parser.add_argument("--rounds", type=int, default=0)
    parser.add_argument("--mode", choices=("pr", "nightly"), default="pr")
    parser.add_argument("--print-canon-hash", action="store_true")
    parser.add_argument("--print-raw-signature", action="store_true")
    parser.add_argument("--expected-hash", type=str, default="")
    parser.add_argument("--expected-raw-signature", type=str, default="")
    parser.add_argument("--expected-stop-reason", type=str, default="")
    args = parser.parse_args()

    fixture = _load_fixture(args.fixture)
    permuted = _permute_fixture(fixture, args.seed, args.perm_index)
    output = _run_fixture_rounds(permuted, args.rounds)
    canon = canonical_bytes(output)
    canon_hash = _hash_bytes(canon)
    raw_sig = raw_signature(output)

    stop_reason = str(output.get("stop_reason") or "NONE")
    if args.expected_stop_reason and stop_reason != args.expected_stop_reason:
        return _print_failure(
            seed=args.seed,
            perm_index=args.perm_index,
            round_index=max(1, len(output.get("history_rounds", []))),
            diff_path="$",
            stop_reason=stop_reason,
            reason="STOP_REASON_MISMATCH",
        )

    if args.expected_hash and canon_hash != args.expected_hash:
        expected_payload = {"expected_hash": args.expected_hash}
        expected_bytes = canonical_bytes(expected_payload)
        diff_path = first_diff_path(canon, expected_bytes)
        return _print_failure(
            seed=args.seed,
            perm_index=args.perm_index,
            round_index=max(1, len(output.get("history_rounds", []))),
            diff_path=diff_path,
            stop_reason=stop_reason,
            reason="CANON_MISMATCH",
        )

    if args.expected_raw_signature and raw_sig != args.expected_raw_signature:
        return _print_failure(
            seed=args.seed,
            perm_index=args.perm_index,
            round_index=max(1, len(output.get("history_rounds", []))),
            diff_path="$",
            stop_reason=stop_reason,
            reason="RAW_SIGNATURE_MISMATCH",
        )

    if args.print_canon_hash:
        print(f"canon_hash={canon_hash}")
    if args.print_raw_signature:
        print(f"raw_signature={raw_sig}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
