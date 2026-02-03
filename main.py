# main.py
import argparse

from orket import orchestrate, load_venue
from orket.utils import log_event


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Orket with a given venue.")
    parser.add_argument(
        "--venue",
        type=str,
        default="standard",
        help="Venue name (matches venues/<name>.json).",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=20,
        help="Maximum orchestration rounds.",
    )
    parser.add_argument(
        "--no-prelude",
        action="store_true",
        help="Disable the Prelude stage.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    log_event(
        level="info",
        component="orchestrator",
        event="session_start",
        payload={"venue": args.venue},
    )

    venue = load_venue(args.venue)

    print(f"Loaded venue: {venue.name}")
    print(f"Band: {venue.band}")
    print(f"Score: {venue.score}")
    print(f"Tempo: {venue.tempo}")

    while True:
        try:
            task = input("\nEnter a task description (or 'quit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not task:
            continue
        if task.lower() in ("quit", "exit"):
            break

        result = orchestrate(
            venue_name=args.venue,
            task=task,
            max_rounds=args.max_rounds,
            use_prelude=not args.no_prelude,
        )

        print("\n--- Session Result ---")
        print(result)

    log_event(
        level="info",
        component="orchestrator",
        event="session_end",
        payload={"venue": args.venue},
    )


if __name__ == "__main__":
    main()
