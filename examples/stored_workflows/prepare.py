"""Prepare a fresh project for the stored standard or QA workflow."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE))
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL  # noqa: E402
from scripts.benchmarks.isolated_project import prepare_project  # noqa: E402
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402


def prepare(project: Path, workflow: str, model: str, *, api: bool = False) -> None:
    project = prepare_project(SOURCE, project, "core")
    epic = project / "model/core/epics" / f"{workflow}.json"
    epic.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / "model/core/epics" / f"{workflow}.json", epic)
    workspace = project / ("workspace/default" if api else "workspace")
    output = workspace / "agent_output"
    output.mkdir(parents=True)
    (output / "requirements.txt").write_text(
        "CLI: python agent_output/main.py INTEGER INTEGER\n"
        "Print one JSON integer equal to the sum. Preserve arbitrary precision, negative values and int() whitespace.\n"
        "Use only the Python standard library. Six declared examples are the acceptance scope, not exhaustive proof.\n",
        encoding="utf-8")
    if workflow == "qa_completion_test":
        (output / "main.py").write_text("import json\nimport sys\n\nprint(json.dumps(int(sys.argv[1]) + int(sys.argv[2])))\n",
                                       encoding="utf-8")
    if api:
        shutil.copyfile(SOURCE / "server.py", project / "server.py")
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
    organization = project / "config/organization.json"
    org = json.loads(organization.read_text(encoding="utf-8"))
    org.setdefault("process_rules", {})["disable_runtime_verifier"] = True
    organization.write_text(json.dumps(org, indent=2) + "\n", encoding="utf-8")
    environment = project / "model/core/environments/standard.json"
    environment.write_text(json.dumps({"name": "standard", "model": model, "temperature": 0, "timeout": 120}),
                           encoding="utf-8")
    write_payload_with_diff_ledger(project / "setup.json", {"workflow": workflow, "model": model,
        "proof_mode": "structural", "scope": "Prepared inputs only; use runtime completion evidence for results"})
    print(json.dumps({"project": str(project), "workflow": workflow, "workspace": str(workspace)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--workflow", choices=["standard", "qa_completion_test"], required=True)
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--api", action="store_true", help="Seed the API server's workspace/default entrypoint")
    args = parser.parse_args()
    prepare(args.project.resolve(), args.workflow, args.model, api=args.api)
