"""Prepare a fresh project for a bounded stored workflow with declared acceptance."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE))
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL  # noqa: E402
from orket.runtime.config.config_loader import ConfigLoader  # noqa: E402
from scripts.benchmarks.isolated_project import prepare_project  # noqa: E402
from scripts.benchmarks.stored_factorial import prepare_factorial  # noqa: E402
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402


def runtime_environment(workflow: str) -> dict[str, str]:
    """Bound repeated history for the challenge; required file context remains intact."""
    return {"ORKET_CONTEXT_WINDOW": "1"} if workflow == "challenge_workflow_runtime" else {}


def prepare_inputs(project: Path, workspace: Path, workflow: str, organization_name: str) -> None:
    epic = project / "model/core/epics" / f"{workflow}.json"
    epic.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / "model/core/epics" / f"{workflow}.json", epic)
    output = workspace / "agent_output"
    output.mkdir(parents=True, exist_ok=True)
    if workflow == "challenge_workflow_runtime":
        shutil.copyfile(SOURCE / "examples/stored_workflows/challenge_acceptance_runner.py",
                        output / "challenge_acceptance_runner.py")
    if workflow == "factorial":
        prepare_factorial(SOURCE, project, workspace)
    if workflow == "sanity_test":
        (output / "organization.json").write_text(json.dumps({"name": organization_name}), encoding="utf-8")
        definition = json.loads(epic.read_text(encoding="utf-8"))
        card = definition["issues"][0]
        expected = f"Orket is Operational | Organization: {organization_name} | Scope: file-write acceptance only."
        card["params"]["completion_acceptance"]["cases"][0]["expected_text"] = expected
        card["note"] = f"Read agent_output/organization.json. Write agent_output/sanity_receipt.md with exactly this single line and no newline: {expected} Then request code_review. This is only a file-write receipt; do not claim general system health."
        epic.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")
    elif workflow not in {"challenge_workflow_runtime", "factorial"}:
        (output / "requirements.txt").write_text(
            "CLI: python agent_output/main.py INTEGER INTEGER\n"
            "Print one JSON integer equal to the sum. Preserve arbitrary precision, negative values and int() whitespace.\n"
            "Use only the Python standard library. Six declared examples are the acceptance scope, not exhaustive proof.\n",
            encoding="utf-8")
    if workflow == "qa_completion_test":
        (output / "main.py").write_text("import json\nimport sys\n\nprint(json.dumps(int(sys.argv[1]) + int(sys.argv[2])))\n",
                                       encoding="utf-8")


def prepare_policy(project: Path, workflow: str, model: str) -> None:
    for role in ("coder", "code_reviewer", "integrity_guard"):
        path = project / "model/core/roles" / f"{role}.json"
        definition = json.loads(path.read_text(encoding="utf-8"))
        definition.update(
            description="Perform only the current card's declared artifact task and acceptance scope.",
            responsibilities=["Read exactly the current card's required input paths.",
                              "Use declared acceptance diagnostics to decide the card's status."],
            constraints=["Emit JSON tool calls without markdown fences.",
                         "Only reference paths declared by the current card; no assumed design or test files.",
                         "The runtime executes acceptance; never claim to have executed unavailable shell tools."],
            tools=["read_file", "update_issue_status"] + (["write_file"] if role == "coder" else []))
        path.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")
    architecture = project / "config/architecture.json"
    policy = json.loads(architecture.read_text(encoding="utf-8"))
    policy.setdefault("process_rules", {})["disable_runtime_verifier"] = workflow != "challenge_workflow_runtime"
    if workflow == "challenge_workflow_runtime":
        policy["process_rules"]["project_surface_profile"] = "cli"
    architecture.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    environment = project / "model/core/environments/standard.json"
    environment.write_text(json.dumps({"name": "standard", "model": model, "temperature": 0, "timeout": 120}),
                           encoding="utf-8")


def prepare(project: Path, workflow: str, model: str, *, api: bool = False) -> None:
    project = prepare_project(SOURCE, project, "core")
    organization = ConfigLoader(project).load_organization()
    if organization is None:
        raise ValueError("Prepared workflows require a canonical organization")
    workspace = project / ("workspace/default" if api else "workspace")
    if workflow == "test_rock":
        collection = SOURCE / "model/core/rocks/test_rock.json"
        shutil.copyfile(collection, project / "model/core/rocks/test_rock.json")
        members = json.loads(collection.read_text(encoding="utf-8"))["epics"]
        for member in members:
            if member["department"] != "core":
                raise ValueError("This preparation recipe requires core members")
            prepare_inputs(project, workspace / member["epic"], member["epic"], organization.name)
    else:
        prepare_inputs(project, workspace, workflow, organization.name)
    if api:
        shutil.copyfile(SOURCE / "server.py", project / "server.py")
    prepare_policy(project, workflow, model)
    write_payload_with_diff_ledger(project / "setup.json", {"workflow": workflow, "model": model,
        "runtime_environment": runtime_environment(workflow),
        "proof_mode": "structural", "scope": "Prepared inputs only; use runtime completion evidence for results"})
    print(json.dumps({"project": str(project), "workflow": workflow, "workspace": str(workspace),
                      "runtime_environment": runtime_environment(workflow)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--workflow", choices=["standard", "qa_completion_test", "sanity_test", "challenge_workflow_runtime", "factorial", "test_rock"], required=True)
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--api", action="store_true", help="Seed the API server's workspace/default entrypoint")
    args = parser.parse_args()
    prepare(args.project.resolve(), args.workflow, args.model, api=args.api)
