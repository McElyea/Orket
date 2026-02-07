# main.py
import argparse
from pathlib import Path
import asyncio

from orket.orket import orchestrate
from orket.discovery import print_orket_manifest, perform_first_run_setup


def parse_args():
    parser = argparse.ArgumentParser(description="Run an Orket Epic.")

    parser.add_argument(
        "--epic",
        type=str,
        required=True,
        help="Name of the epic to run (e.g. 'standard').",
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
        help="Optional task description to override the epic's default example task.",
    )

    return parser.parse_args()


def main():
    perform_first_run_setup()
    print_orket_manifest()
    args = parse_args()

    workspace = Path(args.workspace).resolve()

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
        idx = entry["step_index"]
        role = entry["role"]
        print(f"\n--- Story {idx} ({role}) ---")
        print(entry["summary"])


if __name__ == "__main__":
    main()
