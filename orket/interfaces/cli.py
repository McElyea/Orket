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
    parser = argparse.ArgumentParser(description="Run an Orket Card (Rock, Epic, or Issue).")
    parser.add_argument("command", nargs="?", help="Optional command group (e.g. extensions, run).")
    parser.add_argument("subcommand", nargs="?", help="Optional subcommand (e.g. list, install, <workload_id>).")
    parser.add_argument("target", nargs="?", help="Optional target argument (e.g. repo URL for install).")
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed for extension workloads.")
    parser.add_argument("--ref", type=str, default=None, help="Optional git ref for extension install.")
    parser.add_argument("--epic", type=str, default=None, help="Name of the epic to run.")
    parser.add_argument("--card", type=str, default=None, help="ID or summary of a specific Card to run.")
    parser.add_argument("--rock", type=str, default=None, help="Name of the rock to run.")
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
    parser.add_argument("--archive-related", action="append", default=[], help="Archive cards matching token in id/build/summary/note (repeatable).")
    parser.add_argument("--archive-reason", type=str, default="manual archive", help="Reason stored with archive transaction.")
    parser.add_argument("--replay-turn", type=str, default=None, help="Replay diagnostics for one turn: <session_id>:<issue_id>:<turn_index>[:role].")
    return parser.parse_args()


def _print_extensions_list(manager: ExtensionManager) -> None:
    extensions = manager.list_extensions()
    if not extensions:
        print("No extensions installed.")
        return

    print("Installed extensions:")
    for ext in extensions:
        print(f"- {ext.extension_id} ({ext.extension_version}) [{ext.source}]")
        if ext.workloads:
            for workload in ext.workloads:
                print(f"  workload: {workload.workload_id} ({workload.workload_version})")
        else:
            print("  workload: <none>")


def _install_extension(args, manager: ExtensionManager) -> None:
    repo = str(args.target or "").strip()
    if not repo:
        raise ValueError("extensions install requires a repo path/URL (e.g. 'orket extensions install <repo>').")
    record = manager.install_from_repo(repo=repo, ref=args.ref)
    print(f"Installed extension: {record.extension_id} ({record.extension_version})")
    if record.workloads:
        print("Registered workloads:")
        for workload in record.workloads:
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
    print(f"\n{'='*60}\n ORKET PROJECT BOARD (The Card Hierarchy)\n{'='*60}")
    for rock in hierarchy["rocks"]:
        print(f"\n[ROCK] {rock['name']} (Status: {rock.get('status', 'on_track')})")
        for epic in rock.get("epics", []):
            if "error" in epic:
                print(f"  - [EPIC] {epic['name']} (Error: {epic['error']})")
                continue
            print(f"  - [EPIC] {epic['name']} (Status: {epic.get('status', 'planning')})")
            for issue in epic.get("issues", []):
                summary = issue.get("summary") or issue.get("name") or "Unnamed Unit"
                print(f"    * [{issue['id']}] {summary} ({issue['seat']}) [Priority: {issue.get('priority', 'Medium')}, Status: {issue.get('status', 'ready')}]")
    print(f"\n{'='*60}\n")

async def run_cli():
    # Force UTF-8
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    try:
        perform_first_run_setup()
        args = parse_args()
        extension_manager = ExtensionManager()

        if args.command == "extensions":
            if args.subcommand == "list":
                _print_extensions_list(extension_manager)
                return
            if args.subcommand == "install":
                _install_extension(args, extension_manager)
                return
            raise ValueError("Supported extensions commands: 'orket extensions list' and 'orket extensions install <repo> [--ref <ref>]'.")

        if args.command == "run":
            await _run_extension_workload(args, extension_manager)
            return

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
                archived_count += await engine.archive_build(args.archive_build, archived_by="cli", reason=args.archive_reason)
            if args.archive_related:
                result = await engine.archive_related_cards(args.archive_related, archived_by="cli", reason=args.archive_reason)
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

        print_orket_manifest(args.department)

        if args.rock:
            print(f"Running Orket Rock: {args.rock}")
            await engine.run_card(args.rock, build_id=args.build_id)
            print(f"\n=== Rock {args.rock} Complete ===")
            return

        if args.card:
            print(f"Running Orket Card: {args.card}")
            await engine.run_card(args.card, build_id=args.build_id, driver_steered=args.driver_steered)
            return

        if not args.epic:
            # Interactive Driver Mode
            from orket.driver import OrketDriver
            print(f"\n{'='*60}\n ORKET DRIVER (Interactive)\n{'='*60}")
            driver = OrketDriver(model=args.model)
            while True:
                try:
                    user_input = await asyncio.to_thread(input, "Driver> ")
                    if user_input.lower() in ["exit", "quit", "q"]: break
                    if not user_input: continue
                    print("Thinking...", end="", flush=True)
                    response = await driver.process_request(user_input)
                    print(f"\r{response}\n")
                except EOFError: break
            return

        print(f"Running Orket Epic: {args.epic}")
        transcript = await engine.run_card(args.epic, build_id=args.build_id, driver_steered=args.driver_steered, target_issue_id=args.resume)
        print("\n=== Orket EOS Run Complete ===")
        for entry in transcript:
            print(f"\n--- Card {entry.get('step_index', '?')} ({entry['role']}) ---")
            print(entry['summary'])

    except KeyboardInterrupt:
        print("\n[HALT] Interrupted by user.")
    except (RuntimeError, ValueError, OSError, TypeError) as e:
        import traceback
        traceback.print_exc()
        print(f"\n[FATAL] {e}")
