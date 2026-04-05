# Contract Delta: Challenge Runtime Truth Surface

## Summary

- Change title: challenge runtime truth-surface follow-up
- Owner: Orket Core
- Date: 2026-04-03
- Affected contract(s):
  - `model/core/contracts/local_prompt_profiles.json`
  - `orket/application/services/runtime_verifier.py`
  - `model/core/epics/challenge_workflow_runtime.json`

## Delta

- Current behavior:
  - qwen local tool-call profiles permit empty intro denylist coverage, so prose-prefixed tool JSON is caught only after output drift occurs
  - legacy tool-call prompts still demonstrate fenced tool JSON and legacy validation tolerates that fence shape on non-protocol tool paths
  - runtime verifier collapses stdout JSON parse failures and stdout assertion failures into generic `command_failed`
  - the challenge runtime proof payload can report `dependency_cycle: true` without an explicit policy verdict, and the final proof surface does not require corruption, double-resume, or broader invocation-shape evidence
- Proposed behavior:
  - qwen local tool-call profiles carry explicit intro denylist coverage for common prose/meta prefixes
  - legacy tool-call prompt/validator contracts reject fenced JSON on required-action tool paths instead of relying on repair
  - Ollama `tool_call` turns use provider JSON mode because the active runtime contract now requires one canonical `{"content":"","tool_calls":[...]}` envelope rather than repeated top-level tool objects
  - runtime verifier classifies stdout JSON parse failures and stdout assertion failures distinctly and marks the affected command result as failed
  - the challenge runtime proof contract explicitly states that cycles are expected validation rejections, and the generated proof surface must cover checkpoint corruption, double resume, and multiple invocation contexts
- Why this break is required now:
  - the archived TD04032026 closeout left an avoidable false-green reading open and tolerated corrective repair in a place that should fail closed earlier

## Migration Plan

1. Compatibility window:
   - existing callers may continue reading `returncode`, `exit_code`, and `stdout_contract_ok`, but should accept the narrower `failure_class` values
2. Migration steps:
  - update local prompt profile tests
   - update Ollama tool-call transport tests and local prompting contract wording so the adapter and active contract agree on single-envelope JSON mode
  - update runtime verifier service tests to assert the new stdout failure classes
  - update challenge runtime asset tests to require the widened proof surface
3. Validation gates:
   - targeted local prompt, runtime verifier, challenge asset, and docs hygiene checks
   - fresh live rerun of `challenge_workflow_runtime` if feasible

## Rollback Plan

1. Rollback trigger:
   - stable integrations prove they depend on the old generic `command_failed` classification or the new qwen denylist produces a truthful false positive
2. Rollback steps:
   - revert the new profile denylist entries, restore prior stdout-contract classification behavior, and remove the widened challenge-runtime contract assertions
3. Data/state recovery notes:
   - no durable data migration is involved; rollback is code-and-contract only

## Versioning Decision

- Version bump type: none at the Orket package level in this working change
- Effective version/date: 2026-04-03 contract change
- Downstream impact:
  - runtime-verifier consumers should stop assuming every stdout-contract failure is `command_failed`
  - challenge-runtime proof consumers should expect explicit cycle-policy fields
