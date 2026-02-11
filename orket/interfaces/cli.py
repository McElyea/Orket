import argparse
import sys
import io
import asyncio
from pathlib import Path
from orket.orchestration.engine import OrchestrationEngine
from orket.discovery import print_orket_manifest, perform_first_run_setup

def parse_args():
    parser = argparse.ArgumentParser(description="Run an Orket Card (Rock, Epic, or Issue).")
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
    return parser.parse_args()

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
        workspace = Path(args.workspace).resolve()
        engine = OrchestrationEngine(workspace, args.department)

        if args.board:
            print_board(engine.get_board())
            return

        if args.loop:
            from orket.organization_loop import OrganizationLoop
            await OrganizationLoop().run_forever()
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
