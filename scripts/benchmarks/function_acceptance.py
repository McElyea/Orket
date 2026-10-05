"""Declared function-example acceptance for the bounded live benchmark lane."""
from __future__ import annotations

import json
from pathlib import Path

from orket.core.contracts.card_acceptance_inputs import PythonCliAcceptance

# Retained alongside model output and captured by the runtime acceptance snapshot.
VERIFIER = '''import json
import runpy
import sys
from pathlib import Path

request = json.loads(sys.argv[1])
namespace = runpy.run_path(str(Path(__file__).with_name("main.py")))
result = namespace[request["function"]](*request["args"], **request.get("kwargs", {}))
print(json.dumps(result, allow_nan=False))
'''


def declare_function_acceptance(epic: dict, task: dict, workspace: Path) -> None:
    evaluation = task.get("evaluation") or {}
    examples = evaluation.get("examples") or []
    name = evaluation.get("function_name")
    if evaluation.get("type") != "function_examples" or not examples or not isinstance(name, str):
        raise ValueError("Benchmark preflight: explicit function_examples acceptance is required; "
                         "metadata-only and program tasks need a declared task-specific verifier")
    issue = epic["issues"][0]
    definition = PythonCliAcceptance.model_validate({
        "acceptance_ref": f"benchmark-{task['id']}.examples.v1", "policy_ref": "benchmark-function-examples.v1",
        "workload_id": str(task["id"]), "entrypoint": "agent_output/benchmark_verify.py",
        "artifact_paths": ["agent_output/benchmark_verify.py", "agent_output/main.py"],
        "cases": [{"criterion_id": f"example-{index}", "description": f"Declared example {index}",
                   "arguments": [json.dumps({"function": name, "args": example["args"],
                                             "kwargs": example.get("kwargs", {})})],
                   "expected_json": json.dumps(example["expected"])}
                  for index, example in enumerate(examples, 1)],
    })
    output = workspace / "agent_output"
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark_verify.py").write_text(VERIFIER, encoding="utf-8")
    issue["params"] = {"completion_acceptance": definition.model_dump(mode="json")}
    issue["note"] += " Do not modify benchmark_verify.py. Request code_review after writing the implementation."
