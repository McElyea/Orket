# main.py
import argparse
from pathlib import Path

from orket.orket import orchestrate
from orket.discovery import print_orket_manifest, perform_first_run_setup


def parse_args():
    parser = argparse.ArgumentParser(description="Run an Orket project.")

    parser.add_argument(
        "--project",
        type=str,
        required=True,
        help="Name of the project to run (e.g. 'standard').",
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
        help="Workspace directory for generated files and logs.",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model override (e.g. 'qwen2.5-coder:7b').",
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
        help="Optional task description to override the project's default task.",
    )

    return parser.parse_args()


def main():
    perform_first_run_setup()
    print_orket_manifest()
    args = parse_args()

    workspace = Path(args.workspace).resolve()

    print(f"Running Orket Project: {args.project} (Department: {args.department})")
    print(f"Workspace: {workspace}")
    if args.model:
        print(f"Model Override: {args.model}")
    if args.task:
        print(f"Task Override: {args.task}")

    import asyncio
    transcript = asyncio.run(orchestrate(
        project_name=args.project,
        workspace=workspace,
        department=args.department,
        model_override=args.model,
        task_override=args.task,
        interactive_conductor=args.interactive_conductor,
    ))

    print("\n=== Orket Run Complete ===")
    print(f"Project: {args.project}")
    print(f"Workspace: {workspace}")

    print("\n=== Transcript ===")
    for entry in transcript:
        idx = entry["step_index"]
        role = entry["role"]
        note = entry["note"]
        summary = entry["summary"]
        print(f"\n--- Step {idx} ({role}) ---")
        print(f"Note: {note}")
        print(summary)


if __name__ == "__main__":
    main()