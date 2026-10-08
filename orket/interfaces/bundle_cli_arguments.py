from __future__ import annotations

import argparse
from pathlib import Path

from orket.application.services.extension_scaffold_service import extension_template_kinds
from orket.application.services.governed_run_demo_service import DEFAULT_GOVERNED_RUN_SCENARIO
from orket.interfaces.governed_agent_cli import add_governed_agent_subparser
from orket.reforger.cli import add_reforge_subparser


def _default_review_workspace() -> str:
    return str((Path(__file__).resolve().parents[2] / "workspace" / "default").resolve())


def _add_bundle(subparsers):
    validate_parser = subparsers.add_parser("validate", help="Validate an Orket manifest and bundle references.")
    validate_parser.add_argument("target", nargs="?", default=".", help="Bundle directory or manifest file path.")
    validate_parser.add_argument(
        "--engine-version",
        default="",
        help="Engine version used for compatibility checks.",
    )
    validate_parser.add_argument(
        "--available-model",
        action="append",
        default=[],
        help="Available model identifier. Repeatable.",
    )
    validate_parser.add_argument(
        "--model-override",
        default="",
        help="Requested model override for policy validation.",
    )
    validate_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    pack_parser = subparsers.add_parser("pack", help="Pack a validated Orket bundle into a .orket archive.")
    pack_parser.add_argument("source", nargs="?", default=".", help="Bundle directory path.")
    pack_parser.add_argument("--out", default="", help="Output .orket path.")
    pack_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect an Orket bundle directory or .orket archive.")
    inspect_parser.add_argument("target", nargs="?", default=".", help="Bundle directory or .orket archive path.")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_demo(subparsers):
    demo_parser = subparsers.add_parser("demo", help="Run prepared Orket demos.")
    demo_sub = demo_parser.add_subparsers(dest="demo_command", required=True)
    demo_governed = demo_sub.add_parser("governed-run", help="Run the deterministic governed-run evidence demo.")
    demo_governed.add_argument("--scenario", default=str(DEFAULT_GOVERNED_RUN_SCENARIO), help="Scenario YAML path.")
    demo_governed.add_argument("--workspace", default=".", help="Workspace root for .runs output and read observations.")
    demo_governed.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    local = demo_sub.add_parser("local-agent", help="Run the prepared ticket report with the project's actual provider.")
    local.add_argument("--project", default=".", help="Project created by orket setup.")
    local.add_argument("--output", default=".orket/examples/local-agent", help="Fresh directory inside the project.")
    local.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_extensions(subparsers):
    sdk_parser = subparsers.add_parser("sdk", help="SDK commands.")
    sdk_parser.add_argument("--version", action="store_true", help="Print the Orket SDK version.")
    sdk_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    sdk_subparsers = sdk_parser.add_subparsers(dest="sdk_command")
    sdk_validate = sdk_subparsers.add_parser("validate", help="Validate SDK extension manifest and entrypoints.")
    sdk_validate.add_argument("target", nargs="?", default=".", help="Extension directory or manifest path.")
    sdk_validate.add_argument("--strict", action="store_true", help="Treat unknown capabilities as errors.")
    sdk_validate.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    ext_parser = subparsers.add_parser("ext", help="External extension commands.")
    ext_subparsers = ext_parser.add_subparsers(dest="ext_command", required=True)
    ext_validate = ext_subparsers.add_parser(
        "validate",
        help="Validate external extension manifests, entrypoints, and import isolation.",
    )
    ext_validate.add_argument("target", nargs="?", default=".", help="Extension directory or manifest path.")
    ext_validate.add_argument("--strict", action="store_true", help="Treat unknown capabilities as errors.")
    ext_validate.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    ext_init = ext_subparsers.add_parser(
        "init",
        help="Scaffold an external extension repository from the canonical template.",
    )
    ext_init.add_argument("target", help="Destination directory for scaffolded extension files.")
    ext_init.add_argument(
        "--kind",
        choices=extension_template_kinds(),
        default="default",
        help="Template kind: default application extension or governed agent.",
    )
    ext_init.add_argument("--force", action="store_true", help="Overwrite files in an existing target directory.")
    ext_init.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_generation(subparsers):
    refactor_parser = subparsers.add_parser("refactor", help="Run CP-1.1 transactional refactor (rename only).")
    refactor_parser.add_argument("instruction", help="Refactor instruction. Supported: rename <A> to <B>.")
    refactor_parser.add_argument("--scope", action="append", required=True, help="Write scope path (repeatable).")
    refactor_parser.add_argument("--yes", action="store_true", help="Confirm mutation execution.")
    refactor_parser.add_argument("--dry-run", action="store_true", help="Plan only, no writes.")
    refactor_parser.add_argument(
        "--verify-profile",
        default="default",
        help="Verification profile from orket.config.json.",
    )
    refactor_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    api_parser = subparsers.add_parser("api", help="API generation commands.")
    api_sub = api_parser.add_subparsers(dest="api_command", required=True)
    api_add = api_sub.add_parser("add", help="Generate one API route/controller/types set (v1 adapter).")
    api_add.add_argument("route_name", help="Route name (e.g. member).")
    api_add.add_argument("--schema", required=True, help="Schema fields, e.g. 'id:int,name:string'.")
    api_add.add_argument("--method", default="get", help="HTTP method.")
    api_add.add_argument("--scope", action="append", required=True, help="Write scope path (repeatable).")
    api_add.add_argument("--yes", action="store_true", help="Confirm mutation execution.")
    api_add.add_argument("--dry-run", action="store_true", help="Plan only, no writes.")
    api_add.add_argument("--verify-profile", default="default", help="Verification profile from orket.config.json.")
    api_add.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    init_parser = subparsers.add_parser("init", help="Generate scaffold from local blueprint templates.")
    init_parser.add_argument("template", help="Blueprint name (e.g. minimal-node).")
    init_parser.add_argument("project_name", help="Project name token for template hydration.")
    init_parser.add_argument("--dir", default="", help="Output directory path (defaults to ./<project_name>).")
    init_parser.add_argument("--vars", default="", help="Comma-separated key=value variables.")
    init_parser.add_argument("--no-verify", action="store_true", help="Skip post-generation verify commands.")
    init_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_review_pr(review_sub):
    review_pr = review_sub.add_parser("pr", help="Run review from a pull request snapshot.")
    review_pr.add_argument("--remote", required=True, help="Gitea host URL (e.g. http://localhost:3000).")
    review_pr.add_argument("--repo", required=True, help="Repository id in owner/name format.")
    review_pr.add_argument("--pr", required=True, type=int, help="Pull request number.")
    review_pr.add_argument("--token", default="", help="Gitea token override.")
    review_pr.add_argument("--repo-root", default=".", help="Repo root for local policy resolution.")
    review_pr.add_argument("--policy", default="", help="Optional policy JSON file path.")
    review_pr.add_argument("--workspace", default=_default_review_workspace(), help="Workspace root.")
    review_pr.add_argument("--max-files", type=int, default=None)
    review_pr.add_argument("--max-diff-bytes", type=int, default=None)
    review_pr.add_argument("--max-blob-bytes", type=int, default=None)
    review_pr.add_argument("--max-file-bytes", type=int, default=None)
    review_pr.add_argument("--enable-model-assisted", action="store_true")
    review_pr.add_argument("--code-only", action="store_true", help="Review code files only.")
    review_pr.add_argument("--all-files", action="store_true", help="Review all changed files.")
    review_pr.add_argument("--fail-on-blocked", action="store_true")
    review_pr.add_argument("--verbose", action="store_true")
    review_pr.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_review_diff(review_sub):
    review_diff = review_sub.add_parser("diff", help="Run review from a local diff snapshot.")
    review_diff.add_argument("--repo-root", default=".", help="Local git repository root.")
    review_diff.add_argument("--base", required=True, help="Base ref.")
    review_diff.add_argument("--head", required=True, help="Head ref.")
    review_diff.add_argument("--policy", default="", help="Optional policy JSON file path.")
    review_diff.add_argument("--workspace", default=_default_review_workspace(), help="Workspace root.")
    review_diff.add_argument("--max-files", type=int, default=None)
    review_diff.add_argument("--max-diff-bytes", type=int, default=None)
    review_diff.add_argument("--max-blob-bytes", type=int, default=None)
    review_diff.add_argument("--max-file-bytes", type=int, default=None)
    review_diff.add_argument("--enable-model-assisted", action="store_true")
    review_diff.add_argument("--code-only", action="store_true", help="Review code files only.")
    review_diff.add_argument("--all-files", action="store_true", help="Review all changed files.")
    review_diff.add_argument("--fail-on-blocked", action="store_true")
    review_diff.add_argument("--verbose", action="store_true")
    review_diff.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_review_files(review_sub):
    review_files = review_sub.add_parser("files", help="Run review from selected files at a ref.")
    review_files.add_argument("--repo-root", default=".", help="Local git repository root.")
    review_files.add_argument("--ref", required=True, help="Git ref to read file contents from.")
    review_files.add_argument("--paths", nargs="+", required=True, help="File paths.")
    review_files.add_argument("--policy", default="", help="Optional policy JSON file path.")
    review_files.add_argument("--workspace", default=_default_review_workspace(), help="Workspace root.")
    review_files.add_argument("--max-files", type=int, default=None)
    review_files.add_argument("--max-diff-bytes", type=int, default=None)
    review_files.add_argument("--max-blob-bytes", type=int, default=None)
    review_files.add_argument("--max-file-bytes", type=int, default=None)
    review_files.add_argument("--enable-model-assisted", action="store_true")
    review_files.add_argument("--code-only", action="store_true", help="Review code files only.")
    review_files.add_argument("--all-files", action="store_true", help="Review all changed files.")
    review_files.add_argument("--fail-on-blocked", action="store_true")
    review_files.add_argument("--verbose", action="store_true")
    review_files.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_review_replay(review_sub):
    review_replay = review_sub.add_parser("replay", help="Replay a ReviewRun offline from saved artifacts.")
    review_replay.add_argument(
        "--run-dir",
        default="",
        help="Review run directory containing snapshot/policy artifacts.",
    )
    review_replay.add_argument("--snapshot", default="", help="Path to snapshot.json.")
    review_replay.add_argument("--policy", default="", help="Path to policy_resolved.json.")
    review_replay.add_argument("--repo-root", default=".", help="Repo root for policy context.")
    review_replay.add_argument("--workspace", default=_default_review_workspace(), help="Workspace root.")
    review_replay.add_argument("--fail-on-blocked", action="store_true")
    review_replay.add_argument("--verbose", action="store_true")
    review_replay.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_review(subparsers):
    review_parser = subparsers.add_parser("review", help="Manual ReviewRun commands.")
    review_sub = review_parser.add_subparsers(dest="review_command", required=True)
    _add_review_pr(review_sub)
    _add_review_diff(review_sub)
    _add_review_files(review_sub)
    _add_review_replay(review_sub)


def _add_runs(subparsers):
    run_parser = subparsers.add_parser("run", help="Run commands.")
    run_sub = run_parser.add_subparsers(dest="run_command", required=True)
    run_scenario = run_sub.add_parser("scenario", help="Run a local governed-run scenario YAML file.")
    run_scenario.add_argument("scenario", help="Scenario YAML path.")
    run_scenario.add_argument("--workspace", default=".", help="Workspace root for .runs output and read observations.")
    run_scenario.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    run_submit = run_sub.add_parser("submit", help="Submit outward-facing work through the API.")
    run_submit.add_argument("--run-id", default="", help="Optional stable run id.")
    run_submit.add_argument("--namespace", default="", help="Optional namespace; defaults to issue:<run_id>.")
    run_submit.add_argument("--description", required=True, help="Task description.")
    run_submit.add_argument("--instruction", default="", help="Task instruction.")
    run_submit.add_argument("--instruction-file", default="", help="Read task instruction from a file.")
    run_submit.add_argument("--approval-required-tools", action="append", default=[], help="Approval-required tool name.")
    run_submit.add_argument("--max-turns", type=int, default=None)
    run_submit.add_argument("--approval-timeout-seconds", type=int, default=None)

    run_status = run_sub.add_parser("status", help="Fetch outward-facing run status through the API.")
    run_status.add_argument("run_id")

    run_list = run_sub.add_parser("list", help="List outward-facing runs through the API.")
    run_list.add_argument("--status", default="")
    run_list.add_argument("--limit", type=int, default=20)
    run_list.add_argument("--offset", type=int, default=0)

    run_events = run_sub.add_parser("events", help="Fetch outward-facing run events through the API.")
    run_events.add_argument("run_id")
    run_events.add_argument("--types", default="")
    run_events.add_argument("--from-turn", type=int, default=None)
    run_events.add_argument("--to-turn", type=int, default=None)
    run_events.add_argument("--agent-id", default="")

    run_summary = run_sub.add_parser("summary", help="Fetch outward-facing run summary through the API.")
    run_summary.add_argument("run_id")

    run_watch = run_sub.add_parser("watch", help="Watch outward-facing run events through the API stream.")
    run_watch.add_argument("run_id")
    run_watch.add_argument("--types", default="")


def _add_replay(subparsers):
    replay_parser = subparsers.add_parser("replay", help="Replay a governed-run evidence bundle offline.")
    replay_parser.add_argument("target", help="Path to .runs/<run_id>.")
    replay_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_approvals(subparsers):
    approvals_parser = subparsers.add_parser("approvals", help="Outward pipeline approval commands.")
    approvals_sub = approvals_parser.add_subparsers(dest="approvals_command", required=True)
    approvals_list = approvals_sub.add_parser("list", help="List pending outward approvals through the API.")
    approvals_list.add_argument("--status", default="pending")
    approvals_review = approvals_sub.add_parser("review", help="Review one outward approval proposal.")
    approvals_review.add_argument("proposal_id")
    approvals_approve = approvals_sub.add_parser("approve", help="Approve one outward approval proposal.")
    approvals_approve.add_argument("proposal_id")
    approvals_approve.add_argument("--note", default="")
    approvals_deny = approvals_sub.add_parser("deny", help="Deny one outward approval proposal.")
    approvals_deny.add_argument("proposal_id")
    approvals_deny.add_argument("--reason", required=True)
    approvals_deny.add_argument("--note", default="")
    approvals_watch = approvals_sub.add_parser("watch", help="Poll pending outward approvals once.")
    approvals_watch.add_argument("--status", default="pending")


def _add_ledger(subparsers):
    ledger_parser = subparsers.add_parser("ledger", help="Outward pipeline ledger commands.")
    ledger_sub = ledger_parser.add_subparsers(dest="ledger_command", required=True)
    ledger_export = ledger_sub.add_parser("export", help="Export an outward run ledger through the API.")
    ledger_export.add_argument("run_id")
    ledger_export.add_argument("--types", default="")
    ledger_export.add_argument("--include-pii", action="store_true")
    ledger_export.add_argument("--out", required=True)
    ledger_verify = ledger_sub.add_parser("verify", help="Verify a ledger export file offline.")
    ledger_verify.add_argument("file")
    ledger_summary = ledger_sub.add_parser("summary", help="Fetch live ledger verification summary through the API.")
    ledger_summary.add_argument("run_id")


def _add_connectors(subparsers):
    connectors_parser = subparsers.add_parser("connectors", help="Outward pipeline built-in connector commands.")
    connectors_sub = connectors_parser.add_subparsers(dest="connectors_command", required=True)
    connectors_list = connectors_sub.add_parser("list", help="List built-in connector metadata.")
    connectors_list.add_argument("--workspace", default=".", help="Workspace root for local connector context.")
    connectors_show = connectors_sub.add_parser("show", help="Show one built-in connector metadata record.")
    connectors_show.add_argument("name")
    connectors_show.add_argument("--workspace", default=".", help="Workspace root for local connector context.")
    connectors_test = connectors_sub.add_parser("test", help="Invoke one built-in connector through the local harness.")
    connectors_test.add_argument("name")
    connectors_test.add_argument("--args", required=True, help="Connector args as JSON.")
    connectors_test.add_argument("--workspace", default=".", help="Workspace root for local connector context.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orket", description="Orket bundle tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("setup", add_help=False, help="Configure a local project and run first-use checks.")
    subparsers.add_parser("doctor", add_help=False, help="Check the selected provider, hardware and native execution.")

    subparsers.add_parser(
        "runtime",
        add_help=False,
        help="Run the canonical card runtime; pass --help to inspect runtime options.",
    )
    _add_bundle(subparsers)
    _add_demo(subparsers)
    _add_extensions(subparsers)
    _add_generation(subparsers)
    _add_review(subparsers)
    _add_runs(subparsers)
    _add_replay(subparsers)
    _add_approvals(subparsers)
    _add_ledger(subparsers)
    _add_connectors(subparsers)
    add_governed_agent_subparser(subparsers)
    add_reforge_subparser(subparsers)
    return parser
