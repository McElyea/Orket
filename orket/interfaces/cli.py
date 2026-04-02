import argparse
import sys
import io
import asyncio
import json
from pathlib import Path
from orket.orchestration.engine import OrchestrationEngine
from orket.discovery import print_orket_manifest, perform_first_run_setup
from orket.extensions import ExtensionManager


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run an Orket Card. Use --card for the canonical named runtime surface."
    )
    parser.add_argument("command", nargs="?", help="Optional command group (e.g. extensions, run).")
    parser.add_argument("subcommand", nargs="?", help="Optional subcommand (e.g. list, install, <workload_id>).")
    parser.add_argument("target", nargs="?", help="Optional target argument (e.g. repo URL for install).")
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed for extension workloads.")
    parser.add_argument("--ref", type=str, default=None, help="Optional git ref for extension install.")
    parser.add_argument("--epic", type=str, default=None, help="Name of the epic to run.")
    parser.add_argument("--card", type=str, default=None, help="ID or summary of a specific Card to run.")
    # Preserve the legacy alias without advertising it as a canonical operator path.
    parser.add_argument("--rock", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--department", type=str, default="core", help="The department namespace.")
    parser.add_argument("--workspace", type=str, default="workspace/default", help="Workspace directory.")
    parser.add_argument("--model", type=str, default=None, help="Model override.")
    parser.add_argument("--build-id", type=str, default=None, help="Stable ID for continuous reuse.")
    parser.add_argument("--interactive-conductor", action="store_true", help="Enable manual conductor mode.")
    parser.add_argument("--driver-steered", action="store_true", help="Consult Driver for tactical directives.")
    parser.add_argument("--resume", type=str, default=None, help="Resume an Epic from a specific Issue ID.")
    parser.add_argument("--task", type=str, default=None, help="Optional task description override.")
    parser.add_argument("--board", action="store_true", help="Display the project board.")
    parser.add_argument("--loop", action="store_true", help="Start the Vibe Rail Organization Loop.")
    parser.add_argument("--archive-card", action="append", default=[], help="Archive a card by ID (repeatable).")
    parser.add_argument("--archive-build", type=str, default=None, help="Archive all cards in a build.")
    parser.add_argument(
        "--archive-related",
        action="append",
        default=[],
        help="Archive cards matching token in id/build/summary/note (repeatable).",
    )
    parser.add_argument(
        "--archive-reason", type=str, default="manual archive", help="Reason stored with archive transaction."
    )
    parser.add_argument(
        "--replay-turn",
        type=str,
        default=None,
        help="Replay diagnostics for one turn: <session_id>:<issue_id>:<turn_index>[:role].",
    )
    parser.add_argument("--marshaller-request", type=str, default=None, help="Path to marshaller RunRequest JSON.")
    parser.add_argument(
        "--marshaller-proposal",
        action="append",
        default=[],
        help="Path to a marshaller PatchProposal JSON (repeatable).",
    )
    parser.add_argument("--marshaller-run-id", type=str, default=None, help="Optional marshaller run id override.")
    parser.add_argument(
        "--marshaller-allow-path",
        action="append",
        default=[],
        help="Allowed touched path prefix for marshaller intake checks (repeatable).",
    )
    parser.add_argument(
        "--marshaller-promote", action="store_true", help="Promote accepted marshaller result to canonical git branch."
    )
    parser.add_argument(
        "--marshaller-actor-id", type=str, default=None, help="Actor id for marshaller promotion metadata."
    )
    parser.add_argument(
        "--marshaller-actor-source", type=str, default="cli", help="Actor source for marshaller promotion metadata."
    )
    parser.add_argument("--marshaller-branch", type=str, default="main", help="Target branch for marshaller promotion.")
    parser.add_argument(
        "--marshaller-inspect-attempt",
        type=int,
        default=None,
        help="Attempt index to inspect for 'orket marshaller inspect <run_id>'.",
    )
    parser.add_argument("--marshaller-list-limit", type=int, default=20, help="Max rows for 'orket marshaller list'.")
    parser.add_argument(
        "--protocol-run-b",
        type=str,
        default=None,
        help="Second run id for 'orket protocol compare <run_a> --protocol-run-b <run_b>'.",
    )
    parser.add_argument(
        "--protocol-events-a", type=str, default=None, help="Optional explicit events.log path for protocol run A."
    )
    parser.add_argument(
        "--protocol-events-b", type=str, default=None, help="Optional explicit events.log path for protocol run B."
    )
    parser.add_argument(
        "--protocol-artifacts-a", type=str, default=None, help="Optional artifact root path for protocol run A."
    )
    parser.add_argument(
        "--protocol-artifacts-b", type=str, default=None, help="Optional artifact root path for protocol run B."
    )
    parser.add_argument(
        "--protocol-runs-root",
        type=str,
        default=None,
        help="Optional runs root for 'orket protocol campaign'. Defaults to <workspace>/runs.",
    )
    parser.add_argument(
        "--protocol-campaign-run-id",
        action="append",
        default=[],
        help="Optional run id filter for 'orket protocol campaign' (repeatable).",
    )
    parser.add_argument(
        "--protocol-baseline-run-id",
        type=str,
        default=None,
        help="Optional baseline run id for 'orket protocol campaign'.",
    )
    parser.add_argument(
        "--protocol-parity-session-id",
        action="append",
        default=[],
        help="Optional session id filter for 'orket protocol parity-campaign' (repeatable).",
    )
    parser.add_argument(
        "--protocol-parity-discover-limit",
        type=int,
        default=200,
        help="SQLite discovery limit for 'orket protocol parity-campaign'.",
    )
    parser.add_argument(
        "--protocol-max-parity-mismatches",
        type=int,
        default=0,
        help="Allowed mismatches under --protocol-strict for 'orket protocol parity-campaign'.",
    )
    parser.add_argument(
        "--protocol-sqlite-db",
        type=str,
        default=None,
        help="Optional sqlite run ledger DB path for 'orket protocol parity <run_id>'.",
    )
    parser.add_argument("--protocol-strict", action="store_true", help="Return non-zero on protocol replay mismatch.")
    return parser.parse_args()


def _print_extensions_list(manager: ExtensionManager) -> None:
    extensions = manager.list_extensions()
    if not extensions:
        print("No extensions installed.")
        return

    print("Installed extensions:")
    for ext in extensions:
        print(f"- {ext.extension_id} ({ext.extension_version}) [{ext.source}]")
        if ext.manifest_entries:
            for workload in ext.manifest_entries:
                print(f"  workload: {workload.workload_id} ({workload.workload_version})")
        else:
            print("  workload: <none>")


def _install_extension(args, manager: ExtensionManager) -> None:
    repo = str(args.target or "").strip()
    if not repo:
        raise ValueError("extensions install requires a repo path/URL (e.g. 'orket extensions install <repo>').")
    record = manager.install_from_repo(repo=repo, ref=args.ref)
    print(f"Installed extension: {record.extension_id} ({record.extension_version})")
    if record.manifest_entries:
        print("Registered workloads:")
        for workload in record.manifest_entries:
            print(f"- {workload.workload_id} ({workload.workload_version})")


async def _run_extension_workload(args, manager: ExtensionManager) -> None:
    workload_id = (args.subcommand or "").strip()
    if not workload_id:
        raise ValueError("run command requires a workload id (e.g. 'orket run mystery_v1 --seed 123').")
    workspace = Path(args.workspace).resolve()
    result = await manager.run_workload(
        workload_id=workload_id,
        input_config={"seed": args.seed},
        workspace=workspace,
        department=args.department,
    )
    print(f"Executed workload: {result.workload_id} ({result.workload_version})")
    print(f"Extension: {result.extension_id} ({result.extension_version})")
    print(f"Plan hash: {result.plan_hash}")
    print(f"Artifact root: {result.artifact_root}")
    print(f"Provenance: {result.provenance_path}")


def print_board(hierarchy: dict):
    print(f"\n{'=' * 60}\n ORKET PROJECT BOARD (The Card Hierarchy)\n{'=' * 60}")
    for rock in hierarchy["rocks"]:
        print(f"\n[ROCK] {rock['name']} (Status: {rock.get('status', 'on_track')})")
        for epic in rock.get("epics", []):
            if "error" in epic:
                print(f"  - [EPIC] {epic['name']} (Error: {epic['error']})")
                continue
            print(f"  - [EPIC] {epic['name']} (Status: {epic.get('status', 'planning')})")
            for issue in epic.get("issues", []):
                summary = issue.get("summary") or issue.get("name") or "Unnamed Unit"
                priority = issue.get("priority", "Medium")
                status = issue.get("status", "ready")
                print(f"    * [{issue['id']}] {summary} ({issue['seat']}) [Priority: {priority}, Status: {status}]")
    print(f"\n{'=' * 60}\n")


def _emit_startup_status(startup_status: dict[str, str] | None) -> None:
    if not isinstance(startup_status, dict):
        return
    if str(startup_status.get("reconciliation") or "").strip().lower() == "failed":
        print("[STARTUP WARNING] Structural reconciliation failed; continuing in degraded mode.", file=sys.stderr)


async def run_cli():
    # Force UTF-8
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    try:
        startup_status = perform_first_run_setup()
        _emit_startup_status(startup_status)
        args = parse_args()
        extension_manager = ExtensionManager()

        if args.command == "extensions":
            if args.subcommand == "list":
                _print_extensions_list(extension_manager)
                return
            if args.subcommand == "install":
                _install_extension(args, extension_manager)
                return
            raise ValueError(
                "Supported extensions commands: 'orket extensions list' and "
                "'orket extensions install <repo> [--ref <ref>]'."
            )

        if args.command == "run":
            await _run_extension_workload(args, extension_manager)
            return

        if args.command == "marshaller":
            from orket.marshaller.cli import (
                default_run_id,
                execute_marshaller_from_files,
                inspect_marshaller_attempt,
                list_marshaller_runs,
            )

            workspace_root = Path(".").resolve()
            if args.subcommand == "list":
                result = await list_marshaller_runs(workspace_root, limit=max(1, int(args.marshaller_list_limit)))
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return
            if args.subcommand == "inspect":
                run_id = str(args.target or "").strip()
                if not run_id:
                    raise ValueError(
                        "marshaller inspect requires target run_id (e.g. 'orket marshaller inspect <run_id>')."
                    )
                result = await inspect_marshaller_attempt(
                    workspace_root,
                    run_id=run_id,
                    attempt_index=args.marshaller_inspect_attempt,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return

            request_raw = str(args.marshaller_request or "").strip()
            if not request_raw:
                raise ValueError("marshaller command requires --marshaller-request <path>.")
            if not args.marshaller_proposal:
                raise ValueError("marshaller command requires at least one --marshaller-proposal <path>.")
            result = await execute_marshaller_from_files(
                workspace_root=workspace_root,
                run_request_path=Path(request_raw).resolve(),
                proposal_paths=[Path(str(item)).resolve() for item in args.marshaller_proposal],
                run_id=str(args.marshaller_run_id or default_run_id()).strip(),
                allowed_paths=list(args.marshaller_allow_path or []),
                promote=bool(args.marshaller_promote),
                actor_id=args.marshaller_actor_id,
                actor_source=str(args.marshaller_actor_source or "cli"),
                branch=str(args.marshaller_branch or "main"),
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "protocol":
            from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
            from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
            from orket.runtime.protocol_determinism_campaign import compare_protocol_determinism_campaign
            from orket.runtime.protocol_ledger_parity_campaign import compare_protocol_ledger_parity_campaign
            from orket.runtime.protocol_replay import ProtocolReplayEngine
            from orket.runtime.run_ledger_parity import compare_run_ledger_rows

            def _run_root(run_id: str) -> Path:
                base = (Path(args.workspace).resolve() / "runs").resolve()
                candidate = (base / str(run_id).strip()).resolve()
                if not candidate.is_relative_to(base):
                    raise ValueError(f"Invalid run id path: {run_id}")
                return candidate

            def _resolve_events_path(*, run_id: str, override: str | None) -> Path:
                override_value = str(override or "").strip()
                if override_value:
                    return Path(override_value).resolve()
                return _run_root(run_id) / "events.log"

            def _resolve_artifact_root(*, run_id: str, override: str | None) -> Path | None:
                override_value = str(override or "").strip()
                if override_value:
                    return Path(override_value).resolve()
                candidate = _run_root(run_id) / "artifacts"
                return candidate if candidate.exists() else None

            engine = ProtocolReplayEngine()
            if args.subcommand == "replay":
                run_id = str(args.target or "").strip()
                if not run_id:
                    raise ValueError("protocol replay requires target run_id (e.g. 'orket protocol replay <run_id>').")
                events_path = _resolve_events_path(run_id=run_id, override=args.protocol_events_a)
                if not events_path.exists():
                    raise ValueError(f"events.log not found for run '{run_id}' at {events_path}")
                replay = await asyncio.to_thread(
                    engine.replay_from_ledger,
                    events_log_path=events_path,
                    artifact_root=_resolve_artifact_root(run_id=run_id, override=args.protocol_artifacts_a),
                )
                print(json.dumps(replay, indent=2, ensure_ascii=False))
                return

            if args.subcommand == "compare":
                run_a = str(args.target or "").strip()
                run_b = str(args.protocol_run_b or "").strip()
                if not run_a or not run_b:
                    raise ValueError(
                        "protocol compare requires run A target and --protocol-run-b <run_id> "
                        "(e.g. 'orket protocol compare <run_a> --protocol-run-b <run_b>')."
                    )
                events_a = _resolve_events_path(run_id=run_a, override=args.protocol_events_a)
                events_b = _resolve_events_path(run_id=run_b, override=args.protocol_events_b)
                if not events_a.exists():
                    raise ValueError(f"events.log not found for run '{run_a}' at {events_a}")
                if not events_b.exists():
                    raise ValueError(f"events.log not found for run '{run_b}' at {events_b}")
                comparison = await asyncio.to_thread(
                    engine.compare_replays,
                    run_a_events_path=events_a,
                    run_b_events_path=events_b,
                    run_a_artifact_root=_resolve_artifact_root(run_id=run_a, override=args.protocol_artifacts_a),
                    run_b_artifact_root=_resolve_artifact_root(run_id=run_b, override=args.protocol_artifacts_b),
                )
                print(json.dumps(comparison, indent=2, ensure_ascii=False))
                if bool(args.protocol_strict) and not bool(comparison.get("deterministic_match")):
                    raise ValueError("Protocol replay mismatch detected under --protocol-strict.")
                return

            if args.subcommand == "parity":
                run_id = str(args.target or "").strip()
                if not run_id:
                    raise ValueError("protocol parity requires target run_id (e.g. 'orket protocol parity <run_id>').")
                sqlite_db = (
                    Path(str(args.protocol_sqlite_db)).resolve()
                    if str(args.protocol_sqlite_db or "").strip()
                    else (
                        Path(args.workspace).resolve() / ".orket" / "durable" / "db" / "orket_persistence.db"
                    ).resolve()
                )
                if not sqlite_db.exists():
                    raise ValueError(f"SQLite run ledger database not found: {sqlite_db}")
                parity = await compare_run_ledger_rows(
                    sqlite_repo=AsyncRunLedgerRepository(sqlite_db),
                    protocol_repo=AsyncProtocolRunLedgerRepository(Path(args.workspace).resolve()),
                    session_id=run_id,
                )
                print(json.dumps(parity, indent=2, ensure_ascii=False))
                if bool(args.protocol_strict) and not bool(parity.get("parity_ok")):
                    raise ValueError("Run ledger parity mismatch detected under --protocol-strict.")
                return

            if args.subcommand == "campaign":
                runs_root = (
                    Path(str(args.protocol_runs_root)).resolve()
                    if str(args.protocol_runs_root or "").strip()
                    else (Path(args.workspace).resolve() / "runs").resolve()
                )
                campaign = await asyncio.to_thread(
                    compare_protocol_determinism_campaign,
                    runs_root=runs_root,
                    run_ids=list(args.protocol_campaign_run_id or []),
                    baseline_run_id=str(args.protocol_baseline_run_id or "").strip() or None,
                )
                print(json.dumps(campaign, indent=2, ensure_ascii=False))
                if bool(args.protocol_strict) and not bool(campaign.get("all_match", False)):
                    raise ValueError("Protocol replay campaign mismatch detected under --protocol-strict.")
                return

            if args.subcommand == "parity-campaign":
                sqlite_db = (
                    Path(str(args.protocol_sqlite_db)).resolve()
                    if str(args.protocol_sqlite_db or "").strip()
                    else (
                        Path(args.workspace).resolve() / ".orket" / "durable" / "db" / "orket_persistence.db"
                    ).resolve()
                )
                if not sqlite_db.exists():
                    raise ValueError(f"SQLite run ledger database not found: {sqlite_db}")
                campaign = await compare_protocol_ledger_parity_campaign(
                    sqlite_db=sqlite_db,
                    protocol_root=Path(args.workspace).resolve(),
                    session_ids=list(args.protocol_parity_session_id or []),
                    discover_limit=max(0, int(args.protocol_parity_discover_limit)),
                )
                print(json.dumps(campaign, indent=2, ensure_ascii=False))
                if bool(args.protocol_strict):
                    mismatches = int(campaign.get("mismatch_count") or 0)
                    allowed = max(0, int(args.protocol_max_parity_mismatches))
                    if mismatches > allowed:
                        raise ValueError("Run ledger parity campaign mismatch detected under --protocol-strict.")
                return

            raise ValueError(
                "Supported protocol commands: 'orket protocol replay <run_id>', "
                "'orket protocol compare <run_a> --protocol-run-b <run_b>', or "
                "'orket protocol parity <run_id> [--protocol-sqlite-db <path>]', or "
                "'orket protocol campaign [--protocol-runs-root <path>] [--protocol-campaign-run-id <run_id>] "
                "[--protocol-baseline-run-id <run_id>]', or "
                "'orket protocol parity-campaign [--protocol-sqlite-db <path>] [--protocol-parity-session-id <id>]'."
            )

        workspace = Path(args.workspace).resolve()
        engine = OrchestrationEngine(workspace, args.department)

        if args.board:
            print_board(engine.get_board())
            return

        if args.loop:
            from orket.organization_loop import OrganizationLoop

            await OrganizationLoop().run_forever()
            return

        if args.archive_card or args.archive_build or args.archive_related:
            archived_ids = []
            missing_ids = []
            archived_count = 0
            if args.archive_card:
                result = await engine.archive_cards(args.archive_card, archived_by="cli", reason=args.archive_reason)
                archived_ids.extend(result.get("archived", []))
                missing_ids.extend(result.get("missing", []))
            if args.archive_build:
                archived_count += await engine.archive_build(
                    args.archive_build, archived_by="cli", reason=args.archive_reason
                )
            if args.archive_related:
                result = await engine.archive_related_cards(
                    args.archive_related, archived_by="cli", reason=args.archive_reason
                )
                archived_ids.extend(result.get("archived", []))
                missing_ids.extend(result.get("missing", []))

            archived_ids = sorted(set(archived_ids))
            missing_ids = sorted(set(missing_ids))
            archived_count += len(archived_ids)
            print(f"Archived {archived_count} card(s).")
            if archived_ids:
                print(f"Archived IDs: {', '.join(archived_ids)}")
            if missing_ids:
                print(f"Missing IDs: {', '.join(missing_ids)}")
            return

        if args.replay_turn:
            parts = args.replay_turn.split(":")
            if len(parts) not in {3, 4}:
                raise ValueError("--replay-turn format must be <session_id>:<issue_id>:<turn_index>[:role]")
            session_id, issue_id, turn_index = parts[0], parts[1], int(parts[2])
            role = parts[3] if len(parts) == 4 else None
            replay = engine.replay_turn(session_id=session_id, issue_id=issue_id, turn_index=turn_index, role=role)
            print(json.dumps(replay, indent=2, ensure_ascii=False))
            return

        await asyncio.to_thread(print_orket_manifest, args.department)

        if args.rock:
            print(f"Running Orket Card via legacy compatibility alias --rock: {args.rock}")
            await engine.run_card(args.rock, build_id=args.build_id, driver_steered=args.driver_steered)
            print(f"\n=== Card {args.rock} Complete (legacy compatibility alias --rock) ===")
            return

        if args.card:
            print(f"Running Orket Card: {args.card}")
            await engine.run_card(args.card, build_id=args.build_id, driver_steered=args.driver_steered)
            return

        if not args.epic:
            # Interactive Driver Mode
            from orket.driver import OrketDriver

            print(f"\n{'=' * 60}\n ORKET DRIVER (Interactive)\n{'=' * 60}")
            driver = await asyncio.to_thread(OrketDriver, model=args.model)
            while True:
                try:
                    user_input = await asyncio.to_thread(input, "Driver> ")
                    if user_input.lower() in ["exit", "quit", "q"]:
                        break
                    if not user_input:
                        continue
                    print("Thinking...", end="", flush=True)
                    response = await driver.process_request(user_input)
                    print(f"\r{response}\n")
                except EOFError:
                    break
            return

        print(f"Running Orket Epic: {args.epic}")
        transcript = await engine.run_epic(
            args.epic, build_id=args.build_id, driver_steered=args.driver_steered, target_issue_id=args.resume
        )
        print("\n=== Orket EOS Run Complete ===")
        for entry in transcript:
            print(f"\n--- Card {entry.get('step_index', '?')} ({entry['role']}) ---")
            print(entry["summary"])

    except KeyboardInterrupt:
        print("\n[HALT] Interrupted by user.")
    except (RuntimeError, ValueError, OSError, TypeError) as e:
        import traceback

        traceback.print_exc()
        print(f"\n[FATAL] {e}")
