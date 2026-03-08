# OBT03072026 Current-State Implementation Plan

Last updated: 2026-03-07  
Status: Completed  
Owner: Orket Core

## Purpose

Convert the validated findings in `orket_behavioral_truth_review_current_state.md` into a minimal-scope remediation lane that improves truthful behavior, truthful verification, and authority coherence without broad refactoring.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/ROADMAP.md`
4. `docs/projects/techdebt/orket_behavioral_truth_review_current_state.md`
5. Current live repository state on 2026-03-07

## Validated Scope

In scope:
1. Driver action-surface truth for unsupported structural mutations.
2. Epic child-schema authority in touched driver CLI/resource paths.
3. Provider session-reset truth for OpenAI-compatible local backends.
4. Strict-format truth for Ollama `strict_json` and `tool_call` requests.
5. Driver JSON parsing truth on governed paths.
6. Startup reconciliation operator visibility.
7. Workflow/test truthfulness for memory determinism comparator smoke.
8. Roadmap and cycle-plan updates needed to track this lane truthfully.

Out of scope:
1. Full structural implementation of `adopt_issue`.
2. Broad migration of unrelated historical docs or archived cycles.
3. New feature work outside the review findings.
4. Live external-provider verification that requires unavailable infrastructure.

## Success Criteria

1. The driver no longer advertises `adopt_issue` as a supported structural action unless the action is implemented for real.
2. Touched epic create/read/write paths use one authoritative child key: `issues`.
3. OpenAI-compatible providers that emit explicit session ids rotate or reset session identity when `clear_context()` is called.
4. Ollama strict-format requests fail closed when the client cannot honor `format="json"`.
5. Governed driver paths default to strict JSON parsing unless explicitly overridden.
6. CLI startup surfaces reconciliation failure to the operator instead of only logging it.
7. CI workflow steps and tests stop presenting identical-fixture comparison as runtime determinism evidence.
8. Targeted verification passes or any remaining blocker is stated concretely.

## Execution Order

1. `OBT-CS-1` driver action-surface truth
2. `OBT-CS-2` epic schema authority
3. `OBT-CS-3` provider session-reset truth
4. `OBT-CS-4` strict-format fallback truth
5. `OBT-CS-5` governed driver JSON parsing default
6. `OBT-CS-6` startup reconciliation visibility
7. `OBT-CS-7` determinism workflow/test truthfulness
8. verification and closeout

## Work Items

### OBT-CS-1: Remove Message-As-Action From Driver Surface

Problem:
1. `adopt_issue` is advertised and routed like a real structural action even though the runtime only returns narration.

Implementation:
1. Remove `adopt_issue` from the canonical supported action registry.
2. Ensure unsupported `adopt_issue` plans fail with the same stable unsupported-action path as other unsupported actions.
3. Update driver help/action-surface tests so operator-visible text matches the actual executor surface.

Acceptance:
1. `adopt_issue` is absent from supported-action help, prompt text, and parity tests.
2. No driver path claims the action was executed.

Proof target:
1. contract test
2. integration test

### OBT-CS-2: Canonicalize Epic Child Schema To `issues`

Problem:
1. Touched driver paths still create or smooth over both `cards` and `issues`.

Implementation:
1. Make new epic templates write `issues`.
2. Make structural issue-add paths mutate `issues`.
3. Remove silent `cards`-versus-`issues` masking in touched driver CLI/resource logic.
4. Normalize existing canonical model epic fixtures that still use `cards` when that is the smallest truthful fix.

Acceptance:
1. Touched code paths use `issues` as the single authoritative child key.
2. Existing canonical epic assets touched by this lane no longer encode `cards`.

Proof target:
1. contract test
2. integration test

### OBT-CS-3: Make `clear_context()` Truthful For Explicit Session Backends

Problem:
1. OpenAI-compatible paths attach explicit session ids while `clear_context()` is a no-op.

Implementation:
1. Track provider session-epoch state for OpenAI-compatible backends.
2. Rotate the emitted session id after each successful `clear_context()` so the next turn does not reuse the prior backend session namespace.
3. Expose the session epoch in response telemetry to make the reset observable.

Acceptance:
1. A request after `clear_context()` uses a different session id than the prior request for the same runtime context.
2. Existing non-session backends remain unaffected.

Proof target:
1. contract test

### OBT-CS-4: Fail Closed On Unsupported Ollama Strict-Format Requests

Problem:
1. A strict-json/tool-call request can silently downgrade to a plain request when the client rejects `format`.

Implementation:
1. Treat `TypeError` on the `format` keyword as a hard failure for strict tasks.
2. Keep telemetry explicit about the blocked strict-format path.
3. Add tests proving both the success path and the fail-closed path.

Acceptance:
1. Strict-format requests do not silently succeed without format enforcement.
2. The failure message identifies the unsupported client capability.

Proof target:
1. contract test

### OBT-CS-5: Default Governed Driver Parsing To Strict JSON

Problem:
1. Governed driver paths can still default to compatibility slicing even though strict parsing exists.

Implementation:
1. Resolve driver parse mode so governed prompting defaults to `strict` unless the caller or environment explicitly requests compatibility.
2. Keep fallback prompting compatible by default.
3. Update tests so the default-mode story is explicit and verified.

Acceptance:
1. Governed driver construction defaults to strict JSON parsing.
2. Compatibility mode remains an explicit opt-in.

Proof target:
1. contract test
2. integration test

### OBT-CS-6: Surface Startup Reconciliation Failure To Operators

Problem:
1. CLI startup records reconciliation status but ignores it operationally.

Implementation:
1. Inspect `perform_first_run_setup()` results in `run_cli()`.
2. Emit a clear operator-visible warning when reconciliation fails and the CLI continues in degraded mode.
3. Add a startup semantics test for the warning path.

Acceptance:
1. Reconciliation failure is visible on stdout/stderr during CLI startup.
2. The warning is deterministic and test-covered.

Proof target:
1. integration test

### OBT-CS-7: Reclassify False-Green Determinism Comparator Steps

Problem:
1. CI step names still frame identical-fixture comparison as determinism enforcement rather than comparator smoke.

Implementation:
1. Rename workflow step text to describe fixture-contract validation plus comparator smoke precisely.
2. Update workflow tests so they assert the truthful wording, not just command presence.

Acceptance:
1. Workflow text no longer presents same-file comparison as runtime determinism proof.
2. Tests enforce the new truthful labels.

Proof target:
1. contract test

## Verification Plan

Targeted commands:
1. `python -m pytest tests/application/test_driver_action_parity.py tests/application/test_driver_conversation.py tests/application/test_driver_json_parse_modes.py tests/application/test_driver_cli.py tests/adapters/test_local_model_provider_telemetry.py tests/interfaces/test_cli_startup_semantics.py tests/platform/test_quality_workflow_gates.py tests/platform/test_nightly_workflow_memory_gates.py -q`
2. `python scripts/governance/check_docs_project_hygiene.py`

## Stop Conditions

1. Stop when all scoped items above are complete and verified.
2. Stop early if the change set would exceed 10,000 changed lines.
3. If live verification requires unavailable external infrastructure, mark it as an environment blocker instead of over-claiming completion.

## Working Status

1. `OBT-CS-1` completed
2. `OBT-CS-2` completed
3. `OBT-CS-3` completed
4. `OBT-CS-4` completed
5. `OBT-CS-5` completed
6. `OBT-CS-6` completed
7. `OBT-CS-7` completed
8. verification completed

## Verification Summary

Repo-local verification completed:
1. `python -m pytest tests/application/test_driver_action_parity.py tests/application/test_driver_conversation.py tests/application/test_driver_json_parse_modes.py tests/application/test_driver_cli.py tests/adapters/test_local_model_provider_telemetry.py tests/interfaces/test_cli_startup_semantics.py tests/platform/test_quality_workflow_gates.py tests/platform/test_nightly_workflow_memory_gates.py -q`
2. `python -m pytest tests/platform/test_model_asset_integrity.py -q`
3. `python -m pytest tests/scripts/test_provider_runtime_warmup.py tests/scripts/test_check_model_provider_preflight.py tests/scripts/test_provider_model_resolver.py -q`
4. `python scripts/governance/check_docs_project_hygiene.py`

Live verification completed where infrastructure was available:
1. Ollama strict-json success path verified live with installed model `qwen2.5-coder:7b`; observed result `success`, path `primary`.
2. OpenAI-compatible session-rotation path verified live against LM Studio after warmup/loading local model `qwen3.5-4b`; observed result `success`, path `primary`.
3. Provider preflight now verifies warmup/fallback truth through the shared script path:
   1. `python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen3.5-coder --auto-select-model --smoke-stream`
   2. `python scripts/providers/check_model_provider_preflight.py --provider lmstudio --auto-select-model --smoke-stream`

Live verification blocked where infrastructure was not ready:
1. Initial pre-fix evidence found two environment-prep failures:
   1. `qwen3.5-coder` was not installed in Ollama.
   2. LM Studio had no model loaded.
2. This cycle formalized warmup/fallback handling so those are no longer open blockers for live verification.

## Closeout Status

1. Completed on 2026-03-07.
2. The driver no longer advertises `adopt_issue` as a real executable structural action.
3. Touched epic create/list/write paths now treat `issues` as authoritative, and canonical core epic fixtures no longer encode `cards`.
4. OpenAI-compatible `clear_context()` now rotates emitted session identity for the next request, while Ollama strict-format requests fail closed when the client cannot honor `format="json"`.
5. Governed driver construction now defaults to strict JSON parsing unless compatibility mode is explicitly requested.
6. CLI startup now surfaces reconciliation failure to operators, and workflow labels now describe memory comparator steps as fixture-contract/comparator smoke rather than runtime determinism proof.
7. Local provider live verification now has a shared warmup/preflight path that uses `ollama list`, `lms ls --json`, `lms ps --json`, and `lms load` to auto-select runnable installed models and load LM Studio models when needed.
8. Provider-backed runtime execution no longer carries separate model-selection logic in runtime versus verification paths; `orket/runtime/provider_runtime_target.py` is now the shared authority consumed by `LocalModelProvider`, `model_stream_v1`, and the provider verification scripts.
9. This completed cycle plan remains in the active `techdebt` folder because the user explicitly requested the plan be created there.
