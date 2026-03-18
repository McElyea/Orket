"""
scripts/training/extract_training_data.py

Extracts fine-tuning training examples from Orket workspace run observability data.

Each example is one (messages → completion) pair from a single model turn,
taken only from runs and turns that passed quality gates.

Output
------
  --out-jsonl   : JSONL file, one example per line, in chat-completion format.
                  Compatible with Unsloth, Axolotl, LLaMA-Factory, and any
                  OpenAI fine-tuning endpoint.
  --out-manifest: JSON manifest written via write_payload_with_diff_ledger,
                  recording what was extracted and why examples were rejected.

Quality gates (applied in order, each is independently skippable via flags)
---------------------------------------------------------------------------
  1. Run must have session_status == "complete" in run_summary.json.
     (Skip with --allow-incomplete-runs)
  2. Every issue in the run must have reached status "done".
     (Skip with --allow-partial-runs)
  3. Turn must have at least one parsed tool call in parsed_tool_calls.json.
     (Skip with --allow-no-tool-calls)
  4. Turn must NOT be an integrity_guard turn where the guard rejected.
     (Skip with --allow-guard-rejections)
  5. Turn model_response must not be empty or whitespace-only.

Recency filter
--------------
  --since-date YYYY-MM-DD  : Only include turns from runs modified on or
                             after this date (based on run_summary.json mtime).
  --newest-n N             : After all filters, keep only the N most recent
                             examples (ordered by run mtime, then turn index).

Usage examples
--------------
  # Basic: all complete runs, all seats
  python scripts/training/extract_training_data.py \
      --workspace workspace \
      --out-jsonl data/training/orket_turns.jsonl \
      --out-manifest benchmarks/results/training/extract_manifest.json

  # Only qwen2.5-coder turns, last 30 days, coder + architect seats only
  python scripts/training/extract_training_data.py \
      --workspace workspace \
      --model-filter "qwen2.5-coder:7b" \
      --seats coder architect \
      --since-date 2026-02-01 \
      --out-jsonl data/training/orket_turns_recent.jsonl \
      --out-manifest benchmarks/results/training/extract_manifest_recent.json

  # Dry run: see stats without writing JSONL
  python scripts/training/extract_training_data.py \
      --workspace workspace \
      --dry-run \
      --out-manifest benchmarks/results/training/extract_manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from common.rerun_diff_ledger import write_payload_with_diff_ledger  # type: ignore[no-redef]
    except ModuleNotFoundError:
        # Fallback: plain JSON write so the script is usable without the full project installed.
        def write_payload_with_diff_ledger(out_path: Path, payload: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TurnExample:
    """One extracted training example."""
    run_id: str
    issue_id: str
    turn_dir_name: str
    seat: str
    model: str
    run_mtime: float  # for recency ordering
    turn_index: int   # extracted from turn_dir_name prefix e.g. "003_architect" -> 3
    messages: list[dict[str, Any]]
    completion: str


@dataclass
class RejectionRecord:
    run_id: str
    issue_id: str
    turn_dir_name: str
    reason: str


@dataclass
class ExtractionStats:
    runs_scanned: int = 0
    runs_accepted: int = 0
    runs_rejected_no_summary: int = 0
    runs_rejected_incomplete: int = 0
    runs_rejected_partial: int = 0
    runs_rejected_date_filter: int = 0
    turns_scanned: int = 0
    turns_accepted: int = 0
    turns_rejected_seat_filter: int = 0
    turns_rejected_model_filter: int = 0
    turns_rejected_no_tool_calls: int = 0
    turns_rejected_guard_rejection: int = 0
    turns_rejected_empty_response: int = 0
    turns_rejected_missing_files: int = 0
    rejections: list[RejectionRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None


def _load_text(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Turn-level helpers
# ---------------------------------------------------------------------------

def _parse_turn_index(turn_dir_name: str) -> int:
    """Extract numeric prefix from e.g. '003_architect' -> 3."""
    prefix = turn_dir_name.split("_")[0]
    try:
        return int(prefix)
    except ValueError:
        return 0


def _parse_seat(turn_dir_name: str) -> str:
    """Extract seat name from e.g. '003_architect' -> 'architect'."""
    parts = turn_dir_name.split("_", 1)
    return parts[1] if len(parts) > 1 else turn_dir_name


def _extract_model_from_raw(raw_path: Path) -> str:
    """Pull the model name from model_response_raw.json if present."""
    raw = _load_json(raw_path)
    if not isinstance(raw, dict):
        return ""
    # Try ollama structure first, then openai-compat structure
    for key in ("model", "ollama.model"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    ollama_payload = raw.get("ollama")
    if isinstance(ollama_payload, dict):
        val = ollama_payload.get("model")
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _has_valid_tool_calls(parsed_path: Path) -> bool:
    """Return True if parsed_tool_calls.json contains at least one call."""
    data = _load_json(parsed_path)
    if isinstance(data, list):
        return len(data) > 0
    if isinstance(data, dict):
        calls = data.get("tool_calls") or data.get("calls") or []
        return len(calls) > 0
    return False


def _is_guard_rejection(turn_dir_name: str, checkpoint_path: Path) -> bool:
    """
    Return True if this is an integrity_guard turn that rejected the card.
    A guard rejection is: seat == integrity_guard AND checkpoint shows
    the card was set to 'blocked' or the guard explicitly rejected.
    """
    seat = _parse_seat(turn_dir_name)
    if seat != "integrity_guard":
        return False
    checkpoint = _load_json(checkpoint_path)
    if not isinstance(checkpoint, dict):
        return False
    final_status = str(checkpoint.get("final_card_status") or checkpoint.get("card_status") or "")
    outcome = str(checkpoint.get("outcome") or checkpoint.get("result") or "")
    return final_status == "blocked" or outcome in ("reject", "rejected", "blocked")


# ---------------------------------------------------------------------------
# Run-level helpers
# ---------------------------------------------------------------------------

def _load_run_summary(workspace_run_dir: Path) -> dict[str, Any] | None:
    """
    Try multiple known summary locations.
    Primary:   workspace/<run_id>/runs/<run_id>/run_summary.json
    Fallback:  workspace/<run_id>/run_summary.json
    """
    run_id = workspace_run_dir.name
    candidates = [
        workspace_run_dir / "runs" / run_id / "run_summary.json",
        workspace_run_dir / "run_summary.json",
    ]
    for path in candidates:
        data = _load_json(path)
        if isinstance(data, dict):
            return data
    return None


def _run_is_complete(summary: dict[str, Any]) -> bool:
    status = str(summary.get("session_status") or summary.get("status") or "").lower()
    return status in ("complete", "done", "success")


def _run_all_issues_done(summary: dict[str, Any]) -> bool:
    """Return True if every issue in the summary reached status 'done'."""
    issues = summary.get("issues") or []
    if not issues:
        # No issue list in summary — fall back to True (can't verify, don't penalise)
        return True
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        status = str(issue.get("status") or "").lower()
        if status not in ("done", "complete"):
            return False
    return True


def _run_mtime(workspace_run_dir: Path) -> float:
    """Best-effort mtime for recency ordering. Falls back to 0."""
    run_id = workspace_run_dir.name
    candidates = [
        workspace_run_dir / "runs" / run_id / "run_summary.json",
        workspace_run_dir / "run_summary.json",
    ]
    for path in candidates:
        if path.exists():
            return path.stat().st_mtime
    try:
        return workspace_run_dir.stat().st_mtime
    except OSError:
        return 0.0


# ---------------------------------------------------------------------------
# Core extractor
# ---------------------------------------------------------------------------

def extract_from_workspace(
    workspace_root: Path,
    *,
    allow_incomplete_runs: bool = False,
    allow_partial_runs: bool = False,
    allow_no_tool_calls: bool = False,
    allow_guard_rejections: bool = False,
    since_date: date | None = None,
    model_filter: str | None = None,
    seats: set[str] | None = None,
) -> tuple[list[TurnExample], ExtractionStats]:
    stats = ExtractionStats()
    examples: list[TurnExample] = []

    # Each direct subdirectory of workspace is a run
    try:
        run_dirs = sorted(
            [d for d in workspace_root.iterdir() if d.is_dir()],
            key=lambda d: d.name,
        )
    except OSError:
        return examples, stats

    for run_dir in run_dirs:
        stats.runs_scanned += 1
        run_id = run_dir.name

        # --- Run-level gate 1: run_summary.json must exist ---
        summary = _load_run_summary(run_dir)
        if summary is None:
            stats.runs_rejected_no_summary += 1
            continue

        # --- Run-level gate 2: recency filter ---
        mtime = _run_mtime(run_dir)
        if since_date is not None:
            run_date = datetime.fromtimestamp(mtime, tz=timezone.utc).date()
            if run_date < since_date:
                stats.runs_rejected_date_filter += 1
                continue

        # --- Run-level gate 3: completeness ---
        if not allow_incomplete_runs and not _run_is_complete(summary):
            stats.runs_rejected_incomplete += 1
            continue

        # --- Run-level gate 4: all issues done ---
        if not allow_partial_runs and not _run_all_issues_done(summary):
            stats.runs_rejected_partial += 1
            continue

        stats.runs_accepted += 1

        # Observability root: workspace/<run_id>/observability/<run_id>/
        obs_root = run_dir / "observability" / run_id
        if not obs_root.exists():
            # Some runs flatten to workspace/<run_id>/observability/
            obs_root = run_dir / "observability"
        if not obs_root.exists():
            continue

        # Each subdirectory of obs_root is an issue directory
        try:
            issue_dirs = sorted([d for d in obs_root.iterdir() if d.is_dir()])
        except OSError:
            continue

        for issue_dir in issue_dirs:
            issue_id = issue_dir.name

            # Each subdirectory of the issue dir is a turn directory
            try:
                turn_dirs = sorted([d for d in issue_dir.iterdir() if d.is_dir()])
            except OSError:
                continue

            for turn_dir in turn_dirs:
                stats.turns_scanned += 1
                turn_name = turn_dir.name
                seat = _parse_seat(turn_name)

                # --- Turn gate 1: seat filter ---
                if seats is not None and seat not in seats:
                    stats.turns_rejected_seat_filter += 1
                    stats.rejections.append(RejectionRecord(run_id, issue_id, turn_name, f"seat_filter:{seat}"))
                    continue

                # --- Turn gate 2: required files ---
                messages_path = turn_dir / "messages.json"
                response_path = turn_dir / "model_response.txt"
                checkpoint_path = turn_dir / "checkpoint.json"
                parsed_path = turn_dir / "parsed_tool_calls.json"
                raw_path = turn_dir / "model_response_raw.json"

                if not messages_path.exists() or not response_path.exists():
                    stats.turns_rejected_missing_files += 1
                    stats.rejections.append(RejectionRecord(run_id, issue_id, turn_name, "missing_messages_or_response"))
                    continue

                # --- Turn gate 3: model filter ---
                model = _extract_model_from_raw(raw_path)
                if model_filter is not None and model_filter.lower() not in model.lower():
                    stats.turns_rejected_model_filter += 1
                    stats.rejections.append(RejectionRecord(run_id, issue_id, turn_name, f"model_filter:{model}"))
                    continue

                # --- Turn gate 4: tool calls present ---
                if not allow_no_tool_calls and parsed_path.exists():
                    if not _has_valid_tool_calls(parsed_path):
                        stats.turns_rejected_no_tool_calls += 1
                        stats.rejections.append(RejectionRecord(run_id, issue_id, turn_name, "no_tool_calls"))
                        continue

                # --- Turn gate 5: guard rejection ---
                if not allow_guard_rejections and checkpoint_path.exists():
                    if _is_guard_rejection(turn_name, checkpoint_path):
                        stats.turns_rejected_guard_rejection += 1
                        stats.rejections.append(RejectionRecord(run_id, issue_id, turn_name, "guard_rejection"))
                        continue

                # --- Turn gate 6: non-empty response ---
                completion = _load_text(response_path) or ""
                if not completion.strip():
                    stats.turns_rejected_empty_response += 1
                    stats.rejections.append(RejectionRecord(run_id, issue_id, turn_name, "empty_response"))
                    continue

                # --- Load messages ---
                messages_raw = _load_json(messages_path)
                if not isinstance(messages_raw, list) or len(messages_raw) == 0:
                    stats.turns_rejected_missing_files += 1
                    stats.rejections.append(RejectionRecord(run_id, issue_id, turn_name, "empty_messages"))
                    continue

                stats.turns_accepted += 1
                examples.append(TurnExample(
                    run_id=run_id,
                    issue_id=issue_id,
                    turn_dir_name=turn_name,
                    seat=seat,
                    model=model,
                    run_mtime=mtime,
                    turn_index=_parse_turn_index(turn_name),
                    messages=messages_raw,
                    completion=completion.strip(),
                ))

    return examples, stats


# ---------------------------------------------------------------------------
# Output serialisers
# ---------------------------------------------------------------------------

def _to_chat_format(example: TurnExample) -> dict[str, Any]:
    """
    Emit in the OpenAI fine-tuning / Unsloth / Axolotl chat format:

        {
          "messages": [
            {"role": "system", "content": "..."},
            {"role": "user",   "content": "..."},
            {"role": "assistant", "content": "<target completion>"}
          ],
          "_meta": { ... source provenance ... }
        }

    The messages list from Orket already contains the full conversation
    context up to (but not including) the model's response.  We append
    the completion as the final assistant message.
    """
    # Normalise any Orket-specific message formats
    normalised: list[dict[str, str]] = []
    for msg in example.messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").strip()
        content = str(msg.get("content") or "").strip()
        if not role or not content:
            continue
        # Map any non-standard roles to the OpenAI set
        if role not in ("system", "user", "assistant"):
            role = "user"
        normalised.append({"role": role, "content": content})

    # Append the target completion
    normalised.append({"role": "assistant", "content": example.completion})

    return {
        "messages": normalised,
        "_meta": {
            "run_id": example.run_id,
            "issue_id": example.issue_id,
            "turn": example.turn_dir_name,
            "seat": example.seat,
            "model": example.model,
        },
    }


def write_jsonl(examples: list[TurnExample], out_path: Path) -> int:
    """Write training examples to JSONL. Returns count written."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            record = _to_chat_format(ex)
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    return written


def build_manifest(
    examples: list[TurnExample],
    stats: ExtractionStats,
    args: argparse.Namespace,
) -> dict[str, Any]:
    seat_counts: dict[str, int] = {}
    model_counts: dict[str, int] = {}
    for ex in examples:
        seat_counts[ex.seat] = seat_counts.get(ex.seat, 0) + 1
        key = ex.model or "unknown"
        model_counts[key] = model_counts.get(key, 0) + 1

    rejection_summary: dict[str, int] = {}
    for r in stats.rejections:
        bucket = r.reason.split(":")[0]
        rejection_summary[bucket] = rejection_summary.get(bucket, 0) + 1

    return {
        "schema": "orket_training_extract.v1",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "config": {
            "workspace": str(args.workspace),
            "since_date": str(args.since_date) if args.since_date else None,
            "newest_n": args.newest_n,
            "model_filter": args.model_filter,
            "seats": sorted(args.seats) if args.seats else None,
            "allow_incomplete_runs": args.allow_incomplete_runs,
            "allow_partial_runs": args.allow_partial_runs,
            "allow_no_tool_calls": args.allow_no_tool_calls,
            "allow_guard_rejections": args.allow_guard_rejections,
        },
        "summary": {
            "runs_scanned": stats.runs_scanned,
            "runs_accepted": stats.runs_accepted,
            "turns_scanned": stats.turns_scanned,
            "turns_accepted": stats.turns_accepted,
            "examples_written": len(examples),
            "seat_distribution": seat_counts,
            "model_distribution": model_counts,
        },
        "rejection_summary": {
            "runs": {
                "no_summary": stats.runs_rejected_no_summary,
                "incomplete": stats.runs_rejected_incomplete,
                "partial": stats.runs_rejected_partial,
                "date_filter": stats.runs_rejected_date_filter,
            },
            "turns": {
                "seat_filter": stats.turns_rejected_seat_filter,
                "model_filter": stats.turns_rejected_model_filter,
                "no_tool_calls": stats.turns_rejected_no_tool_calls,
                "guard_rejection": stats.turns_rejected_guard_rejection,
                "empty_response": stats.turns_rejected_empty_response,
                "missing_files": stats.turns_rejected_missing_files,
            },
            "by_reason": rejection_summary,
        },
        # Full rejection log is only included in verbose mode to keep the
        # manifest readable.  Individual records carry run_id + turn for tracing.
        "rejection_log": (
            [{"run_id": r.run_id, "issue_id": r.issue_id, "turn": r.turn_dir_name, "reason": r.reason}
             for r in stats.rejections]
            if getattr(args, "verbose_rejections", False) else []
        ),
    }


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract fine-tuning training data from Orket workspace observability.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # I/O
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("workspace"),
        help="Root workspace directory containing run subdirectories. (default: workspace)",
    )
    parser.add_argument(
        "--out-jsonl",
        type=Path,
        default=Path("data/training/orket_turns.jsonl"),
        help="Output JSONL path for training examples. (default: data/training/orket_turns.jsonl)",
    )
    parser.add_argument(
        "--out-manifest",
        type=Path,
        default=Path("benchmarks/results/training/extract_manifest.json"),
        help="Output JSON manifest path. (default: benchmarks/results/training/extract_manifest.json)",
    )

    # Quality gate overrides
    parser.add_argument(
        "--allow-incomplete-runs",
        action="store_true",
        help="Include turns from runs where session_status != complete.",
    )
    parser.add_argument(
        "--allow-partial-runs",
        action="store_true",
        help="Include turns from runs where not all issues reached 'done'.",
    )
    parser.add_argument(
        "--allow-no-tool-calls",
        action="store_true",
        help="Include turns that produced no parsed tool calls.",
    )
    parser.add_argument(
        "--allow-guard-rejections",
        action="store_true",
        help="Include integrity_guard turns that rejected the card.",
    )

    # Filters
    parser.add_argument(
        "--since-date",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="Only include runs with a summary mtime on or after this date.",
    )
    parser.add_argument(
        "--newest-n",
        type=int,
        default=None,
        metavar="N",
        help="After all other filters, keep only the N most recent examples.",
    )
    parser.add_argument(
        "--model-filter",
        type=str,
        default=None,
        metavar="SUBSTRING",
        help="Only include turns produced by a model whose name contains SUBSTRING "
             "(case-insensitive). E.g. 'qwen2.5-coder:7b'.",
    )
    parser.add_argument(
        "--seats",
        nargs="+",
        default=None,
        metavar="SEAT",
        help="Only include turns from these seats. "
             "E.g. --seats coder architect requirements_analyst",
    )

    # Output control
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all extraction and filtering but do not write the JSONL output. "
             "Manifest is still written.",
    )
    parser.add_argument(
        "--verbose-rejections",
        action="store_true",
        help="Include the full per-turn rejection log in the manifest.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    workspace = args.workspace.resolve()
    if not workspace.exists():
        print(f"[ERROR] Workspace directory not found: {workspace}", file=sys.stderr)
        return 1

    seats_filter: set[str] | None = set(args.seats) if args.seats else None

    if not args.quiet:
        print(f"Scanning workspace: {workspace}")
        if args.since_date:
            print(f"  Recency filter: on or after {args.since_date}")
        if seats_filter:
            print(f"  Seat filter: {sorted(seats_filter)}")
        if args.model_filter:
            print(f"  Model filter: {args.model_filter!r}")

    examples, stats = extract_from_workspace(
        workspace,
        allow_incomplete_runs=args.allow_incomplete_runs,
        allow_partial_runs=args.allow_partial_runs,
        allow_no_tool_calls=args.allow_no_tool_calls,
        allow_guard_rejections=args.allow_guard_rejections,
        since_date=args.since_date,
        model_filter=args.model_filter,
        seats=seats_filter,
    )

    # Apply recency sort then newest-N cap
    examples.sort(key=lambda e: (e.run_mtime, e.turn_index))
    if args.newest_n is not None and args.newest_n > 0:
        examples = examples[-args.newest_n:]

    if not args.quiet:
        print(
            f"Runs scanned: {stats.runs_scanned}  accepted: {stats.runs_accepted}  "
            f"rejected: {stats.runs_scanned - stats.runs_accepted}"
        )
        print(
            f"Turns scanned: {stats.turns_scanned}  accepted: {stats.turns_accepted}  "
            f"rejected: {stats.turns_scanned - stats.turns_accepted}"
        )
        print(f"Examples after recency cap: {len(examples)}")

    # Write JSONL
    if not args.dry_run:
        written = write_jsonl(examples, args.out_jsonl)
        if not args.quiet:
            print(f"Wrote {written} examples → {args.out_jsonl}")
    else:
        if not args.quiet:
            print(f"[dry-run] Would write {len(examples)} examples → {args.out_jsonl}")

    # Write manifest
    manifest = build_manifest(examples, stats, args)
    persisted = write_payload_with_diff_ledger(Path(args.out_manifest), manifest)
    if not args.quiet:
        print(f"Manifest → {args.out_manifest}")
        # Print a short summary inline
        s = persisted.get("summary", {})
        print(json.dumps(s, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())