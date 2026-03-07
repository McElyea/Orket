# OBT03072026 Implementation Plan

Last updated: 2026-03-07  
Status: Archived  
Owner: Orket Core

## Purpose

Convert the validated findings from `orket_behavioral_truth_review_full.docx` into a minimal-scope implementation lane that improves truthful behavior, truthful verification, and release authority without broad refactoring.

## Source Inputs

1. `docs/CONTRIBUTOR.md`
2. `docs/projects/archive/techdebt/OBT03072026/orket_behavioral_truth_review_full.docx`
3. Current-tree validation performed on 2026-03-07 against the live repo state

## Current-State Validation Summary

The `.docx` review was partially ahead of or behind the current tree, so this plan is grounded in the current repository rather than the review snapshot alone.

Validated as still open:
1. `.gitea/workflows/baseline-retention-weekly.yml` prepares `benchmarks/results/benchmarks/quant_sweep` but redirects and uploads from `benchmarks/results/quant/quant_sweep`.
2. Runtime-context bridge proof is still incomplete on the success path. Current tests mainly prove policy blocking and provider invocation generally, but do not prove the wrapped-client bridge preserves `runtime_context` when the request succeeds.
3. Driver affordance truth is improved but still worth tightening so operator-visible help/capability output states the exact supported action surface instead of implying a broader controller.
4. `CHANGELOG.md` still overclaims broad exception cleanup and is version-drifted from `pyproject.toml`.

Validated as partially resolved and only needing truth-surface cleanup:
1. CLI startup semantics already have a real-path integration proof in `tests/interfaces/test_cli_startup_semantics.py`.
2. Protocol CLI tests still monkeypatch startup away, so they should be explicitly framed as protocol-path tests rather than mistaken for startup proof.

## Scope

In scope:
1. Workflow correctness for the weekly baseline retention lane.
2. Runtime-context bridge proof at the real wrapped-provider seam.
3. Driver/operator-visible action-surface truthfulness.
4. Release/version narration authority alignment.
5. Startup-proof labeling cleanup for protocol CLI tests.
6. Roadmap and cycle-plan updates needed to track the work truthfully.

Out of scope:
1. Driver executor expansion beyond the currently supported action set.
2. Broad changelog curation outside the incorrect top entry/version strategy text.
3. Unrelated cleanup in exploratory or archived docs.
4. New feature work not required to resolve a validated truth gap.

## Success Criteria

1. The weekly baseline retention workflow prepares the exact artifact directory it writes and uploads.
2. There is a passing test proving `runtime_context` survives both:
   1. direct `model_client.complete(..., runtime_context=...)` support
   2. wrapped-client fallback through `model_client.provider.complete(..., runtime_context=...)`
3. Driver capabilities/help text states the supported operations plainly and does not imply unsupported board control.
4. `CHANGELOG.md`, `pyproject.toml`, and runtime exception policy tell one truthful story:
   1. package version remains `0.3.16`
   2. top-level boundary `except Exception` handlers are not falsely claimed removed
5. Protocol CLI tests that bypass startup are visibly framed as non-startup proof.
6. Targeted verification passes and any residual proof gap is stated explicitly.

## Execution Order

1. `OBT-F1` workflow artifact path correctness
2. `OBT-F2` driver/operator action-surface truth
3. `OBT-F3` runtime-context bridge proof
4. `OBT-F4` release/version authority cleanup
5. `OBT-F5` startup-proof labeling cleanup
6. verification, roadmap refresh, and cycle closeout decision

## Work Items

### OBT-F1: Weekly Baseline Retention Workflow Path Fix

Problem:
1. The workflow creates one directory and writes to another, which can fail before the script starts.

Implementation:
1. Make the prepared directory exactly match the redirect/upload directory.
2. Add a workflow-focused test that asserts the workflow text prepares the same directory it writes to.

Acceptance:
1. The workflow contains one canonical quant-sweep artifact directory.
2. The path is asserted by an automated test, not just inspection.

Proof target:
1. contract test

### OBT-F2: Driver Supported-Action Truth Surface

Problem:
1. The driver executor is already narrowed, but operator-visible help should state exactly what the driver can do instead of implying broader board control.

Implementation:
1. Derive a user-facing supported-action summary from the canonical action registry.
2. Include suggestion-only semantics for `assign_team`.
3. Reuse that summary in capabilities/help and unsupported-action responses where appropriate.
4. Add or update tests that assert operator-visible help reflects the actual supported actions.

Acceptance:
1. Capabilities/help names the supported action set directly.
2. Unsupported actions are rejected with a stable, truthful message.

Proof target:
1. contract test
2. integration test

### OBT-F3: Runtime-Context Bridge Success-Path Proof

Problem:
1. Current tests do not prove the successful wrapped-client bridge preserves `runtime_context`.

Implementation:
1. Add direct-call proof for a model client whose `complete()` accepts `runtime_context`.
2. Add wrapped-client proof for a client whose wrapper omits `runtime_context` but whose provider accepts it.
3. Assert the exact runtime context reaches the receiving callable on success.

Acceptance:
1. Success-path bridge behavior is proven at both supported call shapes.
2. The proof does not rely on policy-blocking before invocation.

Proof target:
1. contract test

### OBT-F4: Release/Version Authority Alignment

Problem:
1. `CHANGELOG.md` claims `0.4.0` while package metadata is `0.3.16`.
2. The changelog text overclaims exception-handler cleanup by ignoring allowed top-level boundaries.

Implementation:
1. Align the top changelog entry to `0.3.16`.
2. Rewrite the cleanup claim so it excludes true entry-boundary handlers.
3. Keep the future-version note aspirational rather than presenting `0.4.0` as already released.

Acceptance:
1. Version identity is consistent across changelog and package metadata.
2. Exception cleanup claims are truthful to the actual boundary policy.

Proof target:
1. structural verification

### OBT-F5: Startup-Proof Labeling Cleanup

Problem:
1. Real CLI startup proof exists, but protocol CLI tests still bypass startup and should not be mistaken for startup verification.

Implementation:
1. Add explicit layer docstrings to modified protocol CLI tests describing them as protocol-path tests with startup bypass.
2. Optionally centralize the startup bypass into a named helper if that reduces ambiguity without broad test churn.

Acceptance:
1. Modified tests no longer read like startup-proof claims.
2. The existing real startup integration proof remains the cited startup seam check.

Proof target:
1. test-truthfulness cleanup

## Verification Plan

Targeted commands:
1. `python -m pytest tests/scripts tests/application/test_driver_action_parity.py tests/application/test_driver_conversation.py tests/application/test_turn_executor_runtime_context_bridge.py tests/interfaces/test_cli_protocol_replay.py tests/interfaces/test_cli_protocol_parity_campaign.py -q`
2. `python scripts/governance/check_docs_project_hygiene.py`

If the workflow-path test lands under a different test file, run that file explicitly in the same verification pass.

## Stop Conditions

1. Stop when all scoped work items above are complete and verified.
2. Stop early if the change set would exceed 10,000 changed lines.
3. If a live integration step requires unavailable external infrastructure, mark it as an environment blocker instead of over-claiming completion.

## Closeout Rule

If all scoped items are complete and verified in this cycle:
1. archive the cycle-specific plan and review artifacts under `docs/projects/archive/techdebt/OBT03072026/`
2. update `docs/ROADMAP.md` so active sections remain truthful
3. add an explicit closeout note with residual risk, if any

## Closeout Status

1. Completed and archived on 2026-03-07.
2. The workflow path mismatch, driver truth-surface tightening, runtime-context bridge proof, changelog authority drift, and startup-proof labeling cleanup were all implemented in this cycle.
3. Verification and residual risk are recorded in `docs/projects/archive/techdebt/OBT03072026/Closeout.md`.
