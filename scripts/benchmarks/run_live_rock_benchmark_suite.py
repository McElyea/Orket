"""Run the current executable task bank through the live rock path."""
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.benchmarks.live_suite import main

if __name__ == "__main__":
    raise SystemExit(main("rock"))
