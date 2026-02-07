# main.py
import argparse
from pathlib import Path

from orket.orket import orchestrate
from orket.discovery import print_orket_manifest, perform_first_run_setup


def parse_args():
    parser = argparse.ArgumentParser(description="Run an Orket flow.")

    parser.add_argument(
        "--flow",
        type=str,
        required=True,
        help="Path to the flow JSON file.",
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
        help="Model name for LocalModelProvider (defaults to user_settings.json).",
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Model temperature.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed for deterministic model behavior.",
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
        help="Optional task description to override the flow's default task.",
    )

    return parser.parse_args()


def main():
    perform_first_run_setup()
    print_orket_manifest()
    args = parse_args()

    # Resolve flow path
    flow_arg = args.flow
    if not flow_arg.endswith(".json"):
        flow_arg += ".json"
    
    flow_path = Path(flow_arg)
    if not flow_path.exists():
        # Try relative to model/flow
        potential_path = Path(__file__).parent / "model" / "flow" / flow_arg
        if potential_path.exists():
            flow_path = potential_path
        else:
            flow_path = flow_path.resolve() # Let it fail with absolute path if still not found

    workspace = Path(args.workspace).resolve()

    print(f"Running Orket flow: {flow_path}")
    print(f"Workspace: {workspace}")
    print(f"Model: {args.model or 'Default (from settings)'}")
    if args.task:
        print(f"Task Override: {args.task}")

    result = orchestrate(
        flow_path=flow_path,
        workspace=workspace,
        model_name=args.model,
        task_override=args.task,
        temperature=args.temperature,
        seed=args.seed,
        interactive_conductor=args.interactive_conductor,
    )

    print("\n=== Orket Run Complete ===")
    print(f"Flow: {result.flow_name}")
    print(f"Workspace: {result.workspace}")

    print("\n=== Transcript ===")
    for entry in result.transcript:
        idx = entry["step_index"]
        role = entry["role"]
        note = entry["note"]
        summary = entry["summary"]
        print(f"\n--- Step {idx} ({role}) ---")
        print(f"Note: {note}")
        print(summary)


if __name__ == "__main__":
    main()
