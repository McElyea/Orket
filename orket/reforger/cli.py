from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

from orket.reforger.eval.base import EvalResult
from orket.reforger.eval.runner import StubEvalHarness
from orket.reforger.modes import load_mode
from orket.reforger.optimizer.mutate import MutateOptimizer
from orket.reforger.optimizer.noop import NoopOptimizer
from orket.reforger.packs import resolve_pack, write_resolved_pack
from orket.reforger.report.diff import write_best_vs_baseline_diff
from orket.reforger.report.summary import write_summary
from orket.reforger.runbundle import (
    copy_tree,
    deterministic_run_stamp,
    digest_tree,
    prepare_run_dirs,
    write_manifest,
)


def _tool_version() -> str:
    try:
        return metadata.version("orket")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def _workspace_root() -> Path:
    return Path.cwd() / "reforge"


def _resolve_baseline_path(*, baseline: str, model_id: str, mode_id: str, workspace_root: Path) -> Path:
    if baseline.strip():
        candidate = Path(baseline)
        if candidate.exists():
            return candidate.resolve()
        return (workspace_root / "packs" / baseline).resolve()

    best_index = workspace_root / "packs" / "best_index.json"
    if best_index.is_file():
        payload = json.loads(best_index.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            key = f"{model_id}:{mode_id}"
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                candidate = Path(value)
                if candidate.exists():
                    return candidate.resolve()
                combined = (workspace_root / "packs" / value).resolve()
                if combined.exists():
                    return combined
    return (workspace_root / "packs" / "model" / model_id / mode_id).resolve()


def _write_scoreboard(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["candidate_id", "score", "hard_fail_count", "soft_fail_count"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})


def _resolve_optimizer(name: str) -> object:
    normalized = name.strip().lower()
    if normalized == "noop":
        return NoopOptimizer()
    return MutateOptimizer()


def _run_reforge(args: argparse.Namespace) -> int:
    workspace_root = _workspace_root()
    mode_path = workspace_root / "modes" / f"{args.mode}.yaml"
    mode = load_mode(mode_path)
    baseline_path = _resolve_baseline_path(
        baseline=str(args.baseline or ""),
        model_id=args.model,
        mode_id=args.mode,
        workspace_root=workspace_root,
    )
    resolved_baseline = resolve_pack(baseline_path, packs_root=workspace_root / "packs")
    baseline_digest = digest_tree(baseline_path)
    run_stamp = deterministic_run_stamp(
        mode_id=args.mode,
        model_id=args.model,
        seed=int(args.seed),
        budget=int(args.budget),
        baseline_digest=baseline_digest,
    )
    run_root = Path(args.out).resolve() if str(args.out or "").strip() else workspace_root / "runs" / run_stamp
    dirs = prepare_run_dirs(run_root)

    (dirs["mode"]).write_text(mode.path.read_text(encoding="utf-8"), encoding="utf-8")
    baseline_resolved_path = write_resolved_pack(resolved_baseline, dirs["baseline_resolved"])
    baseline_eval_dir = dirs["eval"] / "baseline"

    optimizer = _resolve_optimizer(str(args.optimizer))
    candidates = optimizer.generate(
        baseline_pack=baseline_resolved_path,
        mode={
            "mode_id": mode.mode_id,
            "hard_rules": list(mode.hard_rules),
            "soft_rules": list(mode.soft_rules),
        },
        seed=int(args.seed),
        budget=int(args.budget),
        out_dir=dirs["candidates"],
    )

    harness = StubEvalHarness()
    suite_path = (workspace_root / mode.suite_ref).resolve()
    baseline_result = harness.run(
        model_id=args.model,
        mode_id=args.mode,
        pack_path=baseline_resolved_path,
        suite_path=suite_path,
        out_dir=baseline_eval_dir,
    )

    results: dict[str, EvalResult] = {}
    scoreboard: list[dict[str, Any]] = []
    for candidate_path in sorted(candidates, key=lambda path: path.name):
        candidate_id = candidate_path.name.split("_", 1)[0]
        eval_dir = dirs["eval"] / f"candidate_{candidate_id}"
        result = harness.run(
            model_id=args.model,
            mode_id=args.mode,
            pack_path=candidate_path,
            suite_path=suite_path,
            out_dir=eval_dir,
        )
        results[candidate_id] = result
        scoreboard.append(
            {
                "candidate_id": candidate_id,
                "score": float(result.score),
                "hard_fail_count": int(result.hard_fail_count),
                "soft_fail_count": int(result.soft_fail_count),
            }
        )

    scoreboard.sort(
        key=lambda row: (
            -float(row["score"]),
            int(row["hard_fail_count"]),
            int(row["soft_fail_count"]),
            str(row["candidate_id"]),
        )
    )
    _write_scoreboard(dirs["eval"] / "scoreboard.csv", scoreboard)
    best_candidate_id = str(scoreboard[0]["candidate_id"]) if scoreboard else "0001"
    best_result = results[best_candidate_id]

    delta_counts = write_best_vs_baseline_diff(
        baseline=baseline_result,
        best=best_result,
        all_results=results,
        out_path=dirs["diff"] / "best_vs_baseline.md",
    )

    timestamp = f"deterministic-{run_stamp}"
    write_summary(
        out_path=dirs["summary"],
        timestamp=timestamp,
        seed=int(args.seed),
        model_id=args.model,
        mode_id=args.mode,
        budget=int(args.budget),
        best_candidate_id=best_candidate_id,
        scoreboard=scoreboard,
        baseline=baseline_result,
        best=best_result,
        all_results=results,
        delta_counts=delta_counts,
    )

    manifest_payload = {
        "tool_version": _tool_version(),
        "seed": int(args.seed),
        "budget": int(args.budget),
        "model_id": args.model,
        "model_interface_version": str(args.model_interface_version),
        "mode_id": args.mode,
        "timestamps": {"generated_at_utc": timestamp},
        "digests": {
            "mode": digest_tree(dirs["inputs"]),
            "baseline_pack": digest_tree(dirs["baseline_resolved"]),
            "suite": digest_tree(suite_path) if suite_path.exists() else "",
            "run_bundle": digest_tree(dirs["root"]),
        },
    }
    write_manifest(dirs["manifest"], manifest_payload)
    print(dirs["summary"].read_text(encoding="utf-8"))

    hard_violations = int(best_result.hard_fail_count)
    if str(args.save_best).lower() == "true":
        best_target = workspace_root / "packs" / "model" / args.model / args.mode / "best"
        best_target.parent.mkdir(parents=True, exist_ok=True)
        if best_target.exists():
            shutil.rmtree(best_target)
        copy_tree(dirs["candidates"] / f"{best_candidate_id}_pack_resolved", best_target)
        index_file = workspace_root / "packs" / "best_index.json"
        index_payload: dict[str, str] = {}
        if index_file.is_file():
            try:
                parsed = json.loads(index_file.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    index_payload = {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                index_payload = {}
        index_payload[f"{args.model}:{args.mode}"] = str(best_target)
        index_file.write_text(json.dumps(index_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0 if hard_violations == 0 else 1


def _init_reforge(args: argparse.Namespace) -> int:
    workspace_root = _workspace_root()
    mode_path = workspace_root / "modes" / f"{args.mode}.yaml"
    mode_text = mode_path.read_text(encoding="utf-8")
    source = Path(args.from_pack)
    if source.exists():
        parent_ref = str(source.resolve())
    else:
        parent_ref = str(args.from_pack)

    target = workspace_root / "packs" / "model" / args.model / args.mode
    target.mkdir(parents=True, exist_ok=True)
    pack_payload = {"id": f"{args.model}_{args.mode}", "version": "0.1.0", "extends": parent_ref}
    (target / "pack.json").write_text(json.dumps(pack_payload, indent=2) + "\n", encoding="utf-8")
    if not (target / "system.txt").exists():
        (target / "system.txt").write_text("Follow constraints strictly.\n", encoding="utf-8")
    if not (target / "constraints.yaml").exists():
        (target / "constraints.yaml").write_text(mode_text, encoding="utf-8")
    print(f"Initialized pack: {target}")
    return 0


def _open_last_reforge() -> int:
    runs_root = _workspace_root() / "runs"
    if not runs_root.is_dir():
        print("No runs directory found.")
        return 0
    candidates = sorted([item for item in runs_root.iterdir() if item.is_dir()], key=lambda path: path.name)
    if not candidates:
        print("No runs available.")
        return 0
    last = candidates[-1]
    report = last / "diff" / "best_vs_baseline.md"
    if not report.exists():
        print(f"Last run has no diff report: {last}")
        return 0
    try:
        if os.name == "nt":
            os.startfile(str(report))  # type: ignore[attr-defined]
        elif os.name == "posix":
            subprocess.run(["xdg-open", str(report)], check=False)
        else:
            print(f"Open not supported on this platform. Report: {report}")
            return 0
    except OSError:
        print(f"Could not open report automatically. Report: {report}")
    return 0


def add_reforge_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    reforge = subparsers.add_parser("reforge", help="Run Reforger Layer 0 workflows.")
    reforge_sub = reforge.add_subparsers(dest="reforge_command", required=True)

    run = reforge_sub.add_parser("run", help="Generate and evaluate candidate packs.")
    run.add_argument("--mode", required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--seed", required=True, type=int)
    run.add_argument("--budget", required=True, type=int)
    run.add_argument("--baseline", default="")
    run.add_argument("--out", default="")
    run.add_argument("--optimizer", default="mutate")
    run.add_argument("--model-interface-version", default="unknown")
    run.add_argument("--save-best", default="true")

    init = reforge_sub.add_parser("init", help="Initialize model/mode pack from a base pack.")
    init.add_argument("--mode", required=True)
    init.add_argument("--model", required=True)
    init.add_argument("--from", dest="from_pack", required=True)

    open_cmd = reforge_sub.add_parser("open", help="Open run reports.")
    open_cmd.add_argument("which", choices=["last"])


def handle_reforge(args: argparse.Namespace) -> int:
    if args.reforge_command == "run":
        return _run_reforge(args)
    if args.reforge_command == "init":
        return _init_reforge(args)
    if args.reforge_command == "open" and args.which == "last":
        return _open_last_reforge()
    print("unsupported reforge command")
    return 2
