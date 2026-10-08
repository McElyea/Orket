"""Declare retained function or CLI example acceptance before model inference."""
from __future__ import annotations

import json
from pathlib import Path

from orket.core.contracts.card_acceptance_inputs import PythonCliAcceptance

# One dispatch supports individual final-acceptance cases and the repair-stage batch.
VERIFIER_DISPATCH = '''request = json.loads(sys.argv[1])
result = {"cases": [evaluate(case) for case in request["cases"]]} if "cases" in request else evaluate(request)
print(json.dumps(result, allow_nan=False))
'''

# Retained alongside model output and captured by the runtime acceptance snapshot.
FUNCTION_VERIFIER = '''import json
import runpy
import sys
from pathlib import Path

def evaluate(request):
    namespace = runpy.run_path(str(Path(__file__).with_name("main.py")))
    return namespace[request["function"]](*request["args"], **request.get("kwargs", {}))

''' + VERIFIER_DISPATCH

CLI_VERIFIER = '''import json
import subprocess
import sys
from pathlib import Path

def evaluate(request):
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("main.py")), *request["args"]],
                            capture_output=True, text=True, encoding="utf-8")
    return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}

''' + VERIFIER_DISPATCH


def verifier_for(task: dict) -> str:
    kind = (task.get("evaluation") or {}).get("type")
    if kind == "function_examples":
        return FUNCTION_VERIFIER
    if kind == "cli_examples":
        return CLI_VERIFIER
    raise ValueError("Benchmark preflight: explicit function_examples or cli_examples acceptance is required")


def _case(evaluation: dict, example: dict, index: int) -> dict:
    args = example["args"]
    if evaluation["type"] == "function_examples":
        request = {"function": evaluation["function_name"], "args": args, "kwargs": example.get("kwargs", {})}
        expected = example["expected"]
    else:
        if not isinstance(args, list) or any(not isinstance(value, str) for value in args):
            raise ValueError("CLI example arguments must be strings")
        expected = {"stdout": example["expected_stdout"], "stderr": example["expected_stderr"],
                    "exit_code": example["expected_exit_code"]}
        if (not isinstance(expected["stdout"], str) or not isinstance(expected["stderr"], str)
                or type(expected["exit_code"]) is not int):
            raise ValueError("CLI examples require explicit text stdout/stderr and integer exit codes")
        request = {"args": args}
    return {"criterion_id": f"example-{index}", "description": f"Declared example {index}",
            "arguments": [json.dumps(request)], "expected_json": json.dumps(expected)}


def task_acceptance_definition(task: dict) -> PythonCliAcceptance:
    """Validate the full oracle before a suite can create projects or invoke models."""
    evaluation = task.get("evaluation") or {}
    examples = evaluation.get("examples") or []
    verifier_for(task)
    if not examples:
        raise ValueError("Benchmark preflight: explicit examples are required")
    artifacts = ["agent_output/main.py"]
    if evaluation["type"] == "function_examples":
        if not isinstance(evaluation.get("function_name"), str) or not evaluation["function_name"].isidentifier():
            raise ValueError("Function examples require a valid function_name")
    else:
        artifacts = evaluation.get("artifact_paths") or []
        if evaluation.get("entrypoint") != "agent_output/main.py" or "agent_output/main.py" not in artifacts:
            raise ValueError("CLI acceptance requires main.py and an explicit artifact_paths inventory")
        if "agent_output/benchmark_verify.py" in artifacts:
            raise ValueError("The verifier is reserved for the benchmark owner")
    return PythonCliAcceptance.model_validate({
        "acceptance_ref": f"benchmark-{task['id']}.examples.v1",
        "policy_ref": "benchmark-function-examples.v1" if evaluation["type"] == "function_examples" else "benchmark-cli-examples.v1",
        "workload_id": str(task["id"]), "entrypoint": "agent_output/benchmark_verify.py",
        "artifact_paths": ["agent_output/benchmark_verify.py", *artifacts],
        "cases": [_case(evaluation, example, index) for index, example in enumerate(examples, 1)],
    })


def declare_task_acceptance(epic: dict, task: dict, workspace: Path) -> None:
    definition = task_acceptance_definition(task)
    evaluation = task["evaluation"]
    verifier = verifier_for(task)
    issue = epic["issues"][0]
    issue.setdefault("summary", task.get("description") or f"Implement benchmark task {task['id']}")
    output = workspace / "agent_output"
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark_verify.py").write_text(verifier, encoding="utf-8")
    issue["params"] = {"completion_acceptance": definition.model_dump(mode="json")}
    issue["note"] += " Do not modify benchmark_verify.py. Request code_review after writing the implementation."
    artifacts = [path for path in definition.artifact_paths if path != definition.entrypoint]
    issue["params"]["artifact_contract"] = {
        "kind": "app", "primary_output": "agent_output/main.py",
        "required_write_paths": artifacts, "required_read_paths": ["task_context.json"],
        "review_read_paths": list(definition.artifact_paths),
    }
    issue["note"] += " Required implementation files: " + ", ".join(artifacts) + "."
    contract = task.get("acceptance_contract") or {}
    issue["summary"] += f" Task constraints: {json.dumps(task.get('constraints') or [], ensure_ascii=False)}."
    issue["summary"] += f" Required source features/tokens: {json.dumps(contract.get('quality_required_keywords') or [])}."
    issue["summary"] += f" Forbidden source tokens: {json.dumps(contract.get('quality_forbidden_keywords') or [])}."
    if evaluation["type"] == "cli_examples":
        issue["summary"] += f" Exact CLI evaluation cases, including errors: {json.dumps(evaluation['examples'], ensure_ascii=False)}."
    request = {"cases": [json.loads(case.arguments[0]) for case in definition.cases]}
    issue["params"]["runtime_verifier"] = {
        # RuntimeVerifier binds this portable token to its own sys.executable.
        "commands": [["python", "-I", "-B", definition.entrypoint, json.dumps(request)]],
        "expect_json_stdout": True,
        "json_assertions": [{"path": f"cases[{index}]", "op": "eq", "value": json.loads(case.expected_json)}
                            for index, case in enumerate(definition.cases)],
    }
