# Orket — Behavioral Review
_April 2026 — System-level patterns, design decisions, operational risks._

---

## What This System Is

Orket is a **local AI agent governance layer** — not the agent brain, not the execution muscle, but the deterministic gate between an untrusted agent decision and the systems that decision wants to touch. Every action proposal runs through: projection → admission → approval → execution → result validation → append-only ledger commit.

This is a sophisticated and well-architected system. The behavioral review identifies patterns that undermine the correctness guarantees the system is trying to provide, or that will cause operational pain at scale.

---

## 1. Governance-by-Document Drift Risk

**Severity: High**

The codebase contains hundreds of specification documents, protocol rollout checklists, contract delta files, and architecture records. The correctness of the governance layer depends substantially on humans reading and following these documents correctly — the code does not mechanically enforce all the constraints described in specs.

Examples:
- `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md` defines receipt schema fields that must match runtime emission. The match is validated by the parity campaign, which is a separate periodic script, not a continuous runtime assertion.
- `CURRENT_AUTHORITY.md` lists 50+ implementation paths. Whether any given path is actually implemented correctly can only be verified by running the proof slices — there is no always-on invariant check.
- The `CONTRACT_DELTA_*.md` files record schema evolution decisions, but there is no mechanism to detect when code diverges from a contract delta that was agreed upon.

**Pattern:** The system treats documentation as a source of truth and then validates code against it periodically. This is better than nothing, but the gap between "spec says X" and "code does X" widens over time. As the team grows or velocity increases, the protocol campaign windows (two per rollout) may not catch regressions introduced between campaigns.

**Recommendation:** Critical contract invariants (e.g., receipt schema version fields, run_id format constraints) should be enforced by unit tests that are co-located with the schema definitions, not just by periodic campaign scripts. The campaign scripts should remain as regression gates, but they should not be the only enforcement layer.

---

## 2. Benchmark Determinism Theater

**Severity: High**

The published benchmark report (`live_100_determinism_report.json`) shows `determinism_rate: 1.0` across 100 tasks. The `runs_per_task` field is `1`. A single run always produces one unique hash. The reported 100% determinism rate is mathematically guaranteed regardless of whether the system is actually deterministic.

The nightly benchmark workflow also runs with `--runs 1`. The CI quality workflow does not appear to run multi-pass determinism checks as a required gate.

**Consequence:** The determinism guarantee — which is load-bearing for the entire governance value proposition — is not actually being continuously verified. If a change introduced non-determinism in the ODR kernel, the benchmark suite would continue reporting 100% determinism on 1-run-per-task indefinitely.

**Recommendation:** The determinism benchmark should require `--runs 2` minimum for any task tagged as a determinism gate. The ODR gate (`repro_odr_gate.py`) does test multi-permutation determinism, but it is a separate tool invoked manually (or in specific CI workflows), not the primary published benchmark.

---

## 3. Self-Approver Problem in Protocol Rollout

**Severity: Medium**

The protocol enforce-window signoff records show:

```
Approver: "Orket Core (local quality workspace)"
```

The system is signing off its own rollout windows. The signoff schema has an `--approver` parameter that implies external review. In a pre-production context where there is no production traffic and no team beyond the solo developer, self-attestation is pragmatic. But the cutover readiness gate (`check_protocol_enforce_cutover_readiness.py`) does not distinguish between self-signed and externally-signed windows when determining readiness.

As the system grows toward production use with real operators, this pattern will need a human review step. If it is never added, the governance approval path will have always been a formality — the same entity that built the feature also signed off on its deployment.

---

## 4. Fail-Open Defaults in Auth Configuration

**Severity: Medium**

Two settings in `.env.example` are fail-open:

**`ORKET_ALLOW_INSECURE_NO_API_KEY`:** Disables all API authentication when set to `true`. Documented as "local override only" but has no runtime enforcement of that restriction. Copying `.env.example` to `.env` without reviewing this line in a CI or staging environment would expose the API without authentication, silently.

**`ORKET_COMPANION_KEY_STRICT=false` (default):** When an operator sets `ORKET_COMPANION_API_KEY`, they almost certainly intend for that key to be the only valid key on companion routes. The default of `false` means the primary key remains valid on companion routes — the scoped key provides no actual isolation unless the operator also knows to set `ORKET_COMPANION_KEY_STRICT=true`.

Both of these are examples of security configuration that requires the operator to know what they don't know. The safe behavior should be the default, with the unsafe behavior requiring explicit opt-in.

---

## 5. CI Workflows Contain Untestable Business Logic

**Severity: Medium**

The quality and sandbox CI workflows contain multi-line Python blocks executed via `python - <<'PY'` heredocs. These include:

- The sandbox leak gate (checks for leftover Docker resources)
- The migration smoke validator
- The memory fixture contract check

These are not just glue scripts — they contain actual business logic (e.g., JSON parsing, Docker resource enumeration, database record validation). They cannot be unit-tested, are invisible to ruff, have no type annotations, and will silently fail if library APIs change.

The pattern was likely adopted for brevity, but it creates a class of production-critical code that has zero test coverage by construction.

---

## 6. Approval Workflow Does Not Guard Against Edit-After-Approval

**Severity: Medium**

The engine's `decide_approval` path handles `approve`, `deny`, and rejects unknown decisions with a `ValueError`. The approval record stores the original proposal. However, there is no mechanism visible in the reviewed code to prevent a caller from submitting a different `edited_proposal` on a second `decide_approval` call after the first has already resolved.

The test `test_engine_decide_approval_conflict_after_resolution_raises` confirms that a second decision after resolution raises `RuntimeError`, which is correct. But the window between "approval submitted" and "approval recorded" in an async system means there is a potential TOCTOU race where two concurrent approval decisions could both see the record as PENDING. Whether the repository layer provides the necessary serialization is not visible in the reviewed files.

---

## 7. Baseline Retention Is Dry-Run-Only in Production

**Severity: Low / Operational**

The `baseline-retention-weekly` workflow runs a `--dry-run` prune that produces a JSON plan of what would be pruned, but never actually prunes. The `apply` mode is only available via `workflow_dispatch`. This means baseline artifacts accumulate indefinitely under normal operation, and the retention policy is purely advisory.

If the repository is self-hosted on Gitea with limited disk, this will eventually cause artifact storage failures that manifest as CI failures with confusing error messages (disk full during artifact upload).

---

## 8. Tool Parser Has Three Parallel Extraction Strategies With No Consistent Priority Signal

**Severity: Low / Architectural**

The `ToolParser` tries three strategies in order:
1. Stack-based JSON extraction (primary)
2. Legacy DSL regex fallback
3. Truncated JSON recovery

The strategy used is logged as a diagnostic string (`"stack_json"`, `"legacy_dsl"`, etc.) but this is not surfaced in the run summary or approval record. If the system is in production and model responses start routing through `legacy_dsl` due to a prompt format regression, operators have no alert — they would only notice if they were examining per-turn diagnostic logs.

**Recommendation:** The strategy used for tool call extraction should be a first-class field in the run summary artifact. A change in distribution (e.g., 10% of turns switching from `stack_json` to `legacy_dsl`) is a signal that something changed in the model's response format and should trigger investigation.

---

## 9. `FIXTURE_SECONDARY = True` Comment in Acceptance Tests Is Unexplained

In `tests/integration/test_system_acceptance_flow.py`:

```python
FIXTURE_SECONDARY = True
```

This constant is defined but its effect on test execution is not visible in the reviewed file. It may be a marker used by a test runner plugin, a filtering script, or a documentation convention. If it causes these tests to be skipped or deprioritized in some execution contexts, that would mean integration acceptance tests are not running in the primary CI pass.

---

## 10. Architectural Observation: The System Is Well-Structured But Is Approaching Complexity Ceiling

The architecture — separate control plane, execution pipeline, protocol ledger, run ledger, dual-write adapter, parity campaign — is well-principled. Each layer has a defined responsibility and explicit contracts.

However, the codebase has reached a point where understanding any single failure path requires traversing 6–10 layers of abstraction. The W3 series of prior fixes, the contract delta files, and the implementation path list (50+ items in `CURRENT_AUTHORITY.md`) all suggest that maintaining correctness is increasingly demanding.

This is not a criticism — it is an observation about where the system is in its lifecycle. The next phase of work should consider:
- Which abstraction layers can be collapsed now that the protocol is stable?
- Which contracts can be promoted from documents to runtime assertions?
- Where can the complexity be made visible to operators who aren't the author?

The governance machinery is excellent. The challenge ahead is making it legible.

---

_End of behavioral review. 10 items: 2 high, 4 medium, 4 low/architectural._
