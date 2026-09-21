"""Canonical runtime CLI arguments, grouped without changing option order."""
import argparse


def parse_args(argv: list[str] | None = None, *, prog: str | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Run an Orket Card. Use --card for the canonical named runtime surface."
    )
    parser.add_argument("command", nargs="?", help="Optional command group (e.g. extensions, run).")
    parser.add_argument("subcommand", nargs="?", help="Optional subcommand (e.g. list, install, <workload_id>).")
    parser.add_argument("target", nargs="?", help="Optional target argument (e.g. repo URL for install).")
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed for extension workloads.")
    parser.add_argument("--ref", type=str, default=None, help="Optional git ref for extension install.")
    parser.add_argument("--epic", type=str, default=None, help="Name of the epic to run.")
    parser.add_argument("--card", type=str, default=None, help="ID or summary of a specific Card to run.")
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
    _marshaller_arguments(parser)
    _protocol_arguments(parser)
    return parser.parse_args(argv)


def _marshaller_arguments(parser: argparse.ArgumentParser) -> None:
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
        help="Attempt index to inspect for 'orket runtime marshaller inspect <run_id>'.",
    )
    parser.add_argument(
        "--marshaller-list-limit",
        type=int,
        default=20,
        help="Max rows for 'orket runtime marshaller list'.",
    )


def _protocol_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--protocol-run-b",
        type=str,
        default=None,
        help="Second run id for 'orket runtime protocol compare <run_a> --protocol-run-b <run_b>'.",
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
        help="Optional runs root for 'orket runtime protocol campaign'. Defaults to <workspace>/runs.",
    )
    parser.add_argument(
        "--protocol-campaign-run-id",
        action="append",
        default=[],
        help="Optional run id filter for 'orket runtime protocol campaign' (repeatable).",
    )
    parser.add_argument(
        "--protocol-baseline-run-id",
        type=str,
        default=None,
        help="Optional baseline run id for 'orket runtime protocol campaign'.",
    )
    parser.add_argument(
        "--protocol-parity-session-id",
        action="append",
        default=[],
        help="Optional session id filter for 'orket runtime protocol parity-campaign' (repeatable).",
    )
    parser.add_argument(
        "--protocol-parity-discover-limit",
        type=int,
        default=200,
        help="SQLite discovery limit for 'orket runtime protocol parity-campaign'.",
    )
    parser.add_argument(
        "--protocol-max-parity-mismatches",
        type=int,
        default=0,
        help="Allowed mismatches under --protocol-strict for 'orket runtime protocol parity-campaign'.",
    )
    parser.add_argument(
        "--protocol-sqlite-db",
        type=str,
        default=None,
        help="Optional sqlite run ledger DB path for 'orket runtime protocol parity <run_id>'.",
    )
    parser.add_argument("--protocol-strict", action="store_true", help="Return non-zero on protocol replay mismatch.")
