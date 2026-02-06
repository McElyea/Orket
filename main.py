# main.py
import argparse
from pathlib import Path

from orket.orket import orchestrate


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
        default="qwen3-coder:latest",
        help="Model name for LocalModelProvider.",
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

    return parser.parse_args()


def main():
    args = parse_args()

    flow_path = Path(args.flow).resolve()
    workspace = Path(args.workspace).resolve()

    print(f"Running Orket flow: {flow_path}")
    print(f"Workspace: {workspace}")
    print(f"Model: {args.model}")

    result = orchestrate(
        flow_path=flow_path,
        workspace=workspace,
        model_name=args.model,
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
