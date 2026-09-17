# ODR preflight and execution provider convergence

## Summary
- Change title: One provider selection from native ODR admission through receipts.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contracts: `ODR_PROVIDER_ADMISSION.md`, `WORKLOAD_CONTRACT_V1.md` and the governed start-path matrix.

## Delta
- Current behavior: preflight invokes `ollama list` while execution uses the shared
  configured provider. Missing Ollama raises outside typed refusal publication.
- Proposed behavior: plan v2 captures provider/endpoint, shared discovery validates
  models, child invocation receives that selection, and output validation checks
  actual provider/model receipts. Owned provider clients close on success/failure.
  Invalid base specs and sweep inputs pass through the same typed preflight error
  publisher. Role prompts reuse canonical kernel builders while retaining seed
  constraints and requesting concise prose; validators and token ceilings stay intact.
- Reason: native failure contradicts BT-5's declared ODR authority chain and the
  existing default-provider policy.

## Migration Plan
1. Compatibility window: no v1 execution shim. Existing plans are diagnostics.
2. Migration steps: compile a fresh v2 plan using explicit or configured provider
   inputs. Preserve historical artifacts; never fabricate missing receipts.
3. Validation gates: native HTTP/file/process controls, corrupted receipt refusal,
   client cleanup, installed Windows/Linux Python 3.11/3.12 and actual llama.cpp
   success/refusal. The canonical plan records the current acceptance disposition.

## Rollback Plan
1. Trigger: provider mismatch, false successful validation or failed required proof.
2. Steps: stop affected sweeps and preserve their artifacts for repair.
3. Recovery: retain old plans/results as historical evidence. Reverting to the
   mismatched preflight cannot establish current admission.

## Versioning Decision
- Version bump type: script plan schema advances to `odr.run_arbiter.plan.v2`;
  `workload.contract.v1`, raw run and error schemas keep their existing shapes
  with added provider evidence and rerun ledgers.
- Effective version/date: unreleased worktree candidate, 2026-09-14.
- Downstream impact: native child accepts explicit provider/endpoint arguments;
  direct output-validator callers supply the required provider selection.
