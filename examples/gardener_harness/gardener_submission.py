"""Adapt Gardener inputs to the canonical public report submission example."""
from __future__ import annotations

import json
from pathlib import Path

from orket_extension_sdk import GovernedAgentSubmission, canonical_digest_sha256, canonical_json

TEMPLATE = Path(__file__).resolve().parents[1] / "governed-report" / "submission.json"


def materialized(reference: str, kind: str, content: object) -> dict:
    if len(canonical_json(content).encode("utf-8")) > 262144:
        raise ValueError("E_GARDENER_INPUT_TOO_LARGE: materialized input limit is 262144 encoded bytes")
    return {"reference": reference, "kind": kind, "media_type": "application/json", "encoding": "json",
            "digest": "sha256:" + canonical_digest_sha256(content),
            "encoded_bytes": len(canonical_json(content).encode("utf-8")), "content": content,
            "provenance_refs": [f"gardener-input:{reference}"]}


def token_limits(environment: dict[str, str]) -> tuple[int, int]:
    limits = tuple(int(environment.get(key, default)) for key, default in (
        ("ORKET_GARDENER_MAX_INPUT_TOKENS", "8192"), ("ORKET_GARDENER_MAX_OUTPUT_TOKENS", "2048")))
    if not 256 <= limits[0] <= 131072 or not 64 <= limits[1] <= 8192:
        raise ValueError("input tokens must be 256..131072 and output tokens 64..8192; host limits also apply")
    return limits


def prepare_submission(area: Path, prompt: str, sources: dict, timeout_seconds: int,
                       *, input_tokens: int = 8192, output_tokens: int = 2048) -> tuple[Path, Path]:
    submission = json.loads(TEMPLATE.read_bytes())
    submission.update(objective_ref="objective:gardener-report", acceptance_ref="acceptance:gardener-report",
                      initial_context_refs=list(sources))
    submission["verifier_config"] = {
        "required_sections": ["summary", "findings"],
        "minimum_section_lengths": {"summary": 40, "findings": 80},
        "required_section_prefixes": {"summary": "GARDENER_SUMMARY:"},
    }
    profile = submission["requested_model_profiles"][0]
    profile.update(max_input_tokens=input_tokens, max_output_tokens=output_tokens,
                   timeout_ms=max(1, timeout_seconds - 5) * 1000)
    for scope in ("run_budget", "iteration_budget"):
        budget = submission[scope]
        budget.update(wall_time_ms=timeout_seconds * 1000, input_tokens=input_tokens, output_tokens=output_tokens,
                      output_bytes=1048576)
        budget.pop("snapshot_digest")
        budget["snapshot_digest"] = "sha256:" + canonical_digest_sha256(budget)
    GovernedAgentSubmission.from_wire(submission)
    inputs = [materialized(submission["objective_ref"], "objective", {"task": prompt}),
        materialized(submission["acceptance_ref"], "acceptance", {
            "delivery": "A summary starting with GARDENER_SUMMARY: and a findings checklist. For each finding, "
                        "identify the convention, observed evidence or unknown coverage, and suggested action. "
                        "If no gaps are found, describe the checks and their evidence. Obey verifier_config.",
            "limits": "No factual correctness, complete repository coverage, fixes, or tests are certified.",
        }), *(materialized(ref, "authoritative_context", content) for ref, content in sources.items())]
    paths = area / "submission.json", area / "inputs.json"
    for path, payload in zip(paths, (submission, inputs), strict=True):
        encoded = canonical_json(payload).encode("utf-8")
        if len(encoded) > 1024 * 1024:
            raise ValueError("materialized task exceeds the public input byte limit")
        path.write_bytes(encoded)
    return paths


def failure_reason(payload: dict) -> str:
    if payload.get("error"):
        return str(payload["error"])
    for iteration in payload.get("iterations", []):
        for call in iteration.get("model_calls", []):
            if call.get("normalized_reason"):
                return str(call["normalized_reason"])
        decision = iteration.get("decision") or {}
        if iteration.get("advisory_proposal") is not None:
            return f"E_GARDENER_REPORT_NOT_ACCEPTED: terminal_rule={decision.get('rule', 'unknown')}; inspect the retained proposal and receipts"
    return str(payload.get("normalized_reason") or "report delivery was refused")


def accepted_report(payload: dict, sources: dict) -> str:
    truth = payload.get("final_truth") or {}
    if (payload.get("ok") is not True or truth.get("result_class") != "success"
            or truth.get("completion_classification") != "completion_satisfied"):
        raise ValueError("Orket did not verify report delivery")
    ref = truth.get("authoritative_result_ref")
    matches = [item for item in payload.get("iterations", [])
               if ref == f"agent-result:{item.get('binding', {}).get('invocation_id')}"]
    if len(matches) != 1:
        raise ValueError("accepted report reference does not identify one retained result")
    report = json.loads(matches[0]["advisory_proposal"])
    if (report.get("advisory") is not True or set(report.get("source_refs", [])) != set(sources)
            or set(report.get("sections", {})) != {"summary", "findings"}):
        raise ValueError("retained advisory report does not match the submitted snapshot")
    limitations = "\n".join(f"- {item}" for item in report["limitations"])
    return (report["sections"]["summary"] + "\n\n" + report["sections"]["findings"]
            + (f"\n\nModel-stated limitations:\n{limitations}" if limitations else ""))
