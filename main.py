# main.py
import argparse
from pathlib import Path
import asyncio

from orket.orket import orchestrate, orchestrate_rock, orchestrate_card
from orket.discovery import print_orket_manifest, perform_first_run_setup


def parse_args():
    parser = argparse.ArgumentParser(description="Run an Orket Card, Epic, or Rock.")

    parser.add_argument(
        "--epic",
        type=str,
        default=None,
        help="Name of the epic to run.",
    )

    parser.add_argument(
        "--card",
        type=str,
        default=None,
        help="ID or summary of a specific Card to run.",
    )

    parser.add_argument(
        "--rock",
        type=str,
        default=None,
        help="Name of the rock to run.",
    )

    parser.add_argument(
        "--department",
        type=str,
        default="core",
        help="The department namespace (default: 'core').",
    )

    parser.add_argument(
        "--workspace",
        type=str,
        default="workspace/default",
        help="Workspace directory.",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model override.",
    )

    parser.add_argument(
        "--interactive-conductor",
        action="store_true",
        help="Enable manual conductor mode.",
    )

    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Optional task description override.",
    )

    parser.add_argument(
        "--board",
        action="store_true",
        help="Display the top-down tree view of Rocks, Epics, and Cards.",
    )

    return parser.parse_args()


def print_board(hierarchy: dict):
    print(f"\n{'='*60}\n ORKET PROJECT BOARD (Tree View)\n{'='*60}")
    
    for rock in hierarchy["rocks"]:
        print(f"\n[ROCK] {rock['name']}")
        for epic in rock.get("epics", []):
            if "error" in epic:
                print(f"  ↳ [EPIC] {epic['name']} (Error: {epic['error']})")
                continue
            print(f"  ↳ [EPIC] {epic['name']}")
            for card in epic.get("cards", []):
                print(f"    - [{card['id']}] {card['summary']} ({card['seat']})")
                
    if hierarchy["orphaned_epics"]:
        print(f"\n[ORPHANED EPICS] (ALERT: These should be assigned to a Rock!)")
        for epic in hierarchy["orphaned_epics"]:
            print(f"  ⊷ {epic['name']}")
            for card in epic.get("cards", []):
                print(f"    - [{card['id']}] {card['summary']} ({card['seat']})")

    if hierarchy["orphaned_cards"]:
        print(f"\n[ORPHANED CARDS] (ALERT: These should be assigned to an Epic!)")
        for card in hierarchy["orphaned_cards"]:
            print(f"  ⚡ [{card['id']}] {card['summary']} ({card['seat']})")
            
    if hierarchy["alerts"]:
        print(f"\n[STRUCTURAL ALERTS]")
        for alert in hierarchy["alerts"]:
            print(f"  ! {alert['message']}")
            print(f"    Action: {alert['action_required']}")
            
    print(f"\n{'='*60}\n")


def main():
    try:
        perform_first_run_setup()
        args = parse_args()
        
        if args.board:
            from orket.board import get_board_hierarchy
            hierarchy = get_board_hierarchy(args.department)
            print_board(hierarchy)
            return

        print_orket_manifest(args.department)

        workspace = Path(args.workspace).resolve()

        if args.rock:
            print(f"Running Orket Rock: {args.rock} (Department: {args.department})")
            result = asyncio.run(orchestrate_rock(
                rock_name=args.rock,
                workspace=workspace,
                department=args.department,
                task_override=args.task
            ))
            print(f"\n=== Rock {args.rock} Complete ===")
            return

        if args.card:
            print(f"Running Orket Card: {args.card}")
            asyncio.run(orchestrate_card(
                card_id=args.card,
                workspace=workspace,
                department=args.department
            ))
            return

        if not args.epic:
            print("Error: Must specify --epic, --rock, or --card")
            return

        print(f"Running Orket Epic: {args.epic} (Department: {args.department})")

        transcript = asyncio.run(orchestrate(
            epic_name=args.epic,
            workspace=workspace,
            department=args.department,
            model_override=args.model,
            task_override=args.task,
            interactive_conductor=args.interactive_conductor,
        ))

        print("\n=== Orket EOS Run Complete ===")
        for entry in transcript:
            idx = entry.get("step_index", "?")
            role = entry["role"]
            print(f"\n--- Card {idx} ({role}) ---")
            print(entry["summary"])
            
    except KeyboardInterrupt:
        print("\n[HALT] Interrupted by user. Exiting...")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[FATAL] {e}")


if __name__ == "__main__":
    main()
