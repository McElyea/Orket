"""Exercise shared validator and corrective prompt components with real model responses."""

# ruff: noqa: E402 -- support direct repository script execution.
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from orket.application.services.local_model_factory import create_local_model_provider_async
from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_corrective_prompt import CorrectivePromptBuilder
from orket.application.workflows.turn_read_context import observe_legacy_required_read_paths
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from orket.core.domain.execution import ExecutionTurn
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

OUTPUT = ROOT / "benchmarks/results/protocol/local_prompting/qwen38_promotion/repair_readiness.json"


async def prove() -> dict:
    context = {
        "protocol_governed_enabled": True,
        "local_prompt_task_class": "tool_call",
        "local_prompting_mode": "enforce",
    }
    parser = ResponseParser(ROOT, lambda *args, **kwargs: None)
    validator = ContractValidator(parser)
    builder = CorrectivePromptBuilder()
    client = (await create_local_model_provider_async(model=DEFAULT_LOCAL_MODEL, provider="llama_cpp", timeout=90))
    rows = []
    try:
        # Deliberately request noncompliance to exercise a real validator rejection.
        initial = await client.complete(
            [
                {
                    "role": "user",
                    "content": 'Show this object in a markdown code block with triple backticks: {"content":"","tool_calls":[]}',
                }
            ],
            runtime_context={"local_prompt_task_class": "concise_text", "local_prompting_mode": "enforce"},
        )
        turn = ExecutionTurn(timestamp=None, role="actor", issue_id="repair-proof", content=initial.content, raw=initial.raw)
        diagnostics = validator.local_prompt_anti_meta_diagnostics(turn, context)
        violations = diagnostics["violations"]
        if not violations:
            return {
                "passed": False,
                "reason": "negative stimulus did not produce a validator rejection",
                "initial": initial.content,
            }
        failures = [{"reason": "local_prompt_contract_not_met", "violations": violations}]
        observation = await observe_legacy_required_read_paths(context=context, workspace=ROOT)
        corrective = builder.build_corrective_instruction(failures, context, observation)
        deterministic = corrective == builder.build_corrective_instruction(failures, context, observation)
        for attempt in range(1, 3):
            response = await client.complete([{"role": "user", "content": corrective}], runtime_context=context)
            observed = ExecutionTurn(timestamp=None, role="actor", issue_id="repair-proof", content=response.content, raw=response.raw)
            errors = validator.local_prompt_anti_meta_diagnostics(observed, context)["violations"]
            try:
                payload = json.loads(response.content)
            except json.JSONDecodeError:
                payload = None
            passed = not errors and payload == {"content": "", "tool_calls": []}
            rows.append({"attempt": attempt, "response": response.content, "violations": errors, "passed": passed})
            if passed:
                break
        return {
            "passed": deterministic and rows[-1]["passed"],
            "initial": initial.content,
            "initial_violations": violations,
            "corrective_prompt_sha256": hashlib.sha256(corrective.encode()).hexdigest(),
            "failure_context_included": all(item["prior_output_excerpt_hash"] in corrective for item in violations),
            "deterministic_reprompt": deterministic,
            "max_repairs": 2,
            "repairs": rows,
            "scope": "live model + shared host validator/builder; deliberately induced invalid output; no tools executed",
        }
    finally:
        await client.close()


def main() -> int:
    os.environ["ORKET_DISABLE_SANDBOX"] = "1"
    result = asyncio.run(prove())
    payload = {
        "schema_version": "qwen38_repair_readiness.v1",
        "proof_mode": "live",
        "observed_path": "primary",
        "observed_result": "success" if result["passed"] else "failure",
        "model": DEFAULT_LOCAL_MODEL,
        **result,
    }
    write_payload_with_diff_ledger(OUTPUT, payload)
    print(json.dumps({"output": str(OUTPUT), "observed_result": payload["observed_result"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
