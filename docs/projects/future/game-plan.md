# Orket — Next Phase Game Plan

**Date:** 2026-03-18  
**Status:** Working document; Phase 1 closed on 2026-03-18; Phase 2 next  
**Thesis:** Small local models, coordinated and verified, can produce trustworthy output on real tasks without requiring frontier-scale VRAM.

---

## North Star

Orket's value is not running tasks. It is answering the question: **did the model actually do the thing, and can you prove it?**

That reframing matters for everything below. Every script, every workload, every new capability should be evaluated against it. If a piece of work doesn't help answer that question more reliably or for more kinds of tasks, it should wait.

---

## Phase 0 — Close the Behavioral Review

This is not optional before Phase 1. The audit infrastructure has confirmed bugs in the canonicalization system, the ODR state management, the artifact chain, and the ledger. Building workloads on top of these before fixing them means any "evidence" those workloads produce is suspect.

**Gate:** All Wave 1 items from the remediation plan must be merged before new workload or script work begins. Wave 2 items can be worked in parallel with Phase 1.

See: `orket_behavioral_review_remediation_plan.md`

---

## Phase 1 — Understand Where the Cards Engine Actually Is

Before writing new workloads, you need an honest map of what the orchestration engine can do right now with a real Ollama model. The goal of this phase is not to demonstrate success — it is to observe actual behavior and measure the gap between what the engine claims to do and what it does.

This requires a small set of targeted probe scripts. Not tests (tests have expected outcomes). Probes collect observations.

**Observed snapshot (2026-03-18):**
- P-01 completed end-to-end, but not in the shape the draft expected: the run took two turns (`coder` then `integrity_guard`), emitted observability artifacts, and finalized cleanly, but wrote `agent_output/main.py` instead of the requested `agent_output/fibonacci.py`.
- P-02 completed five live ODR runs and showed unstable behavior: `STABLE_DIFF_FLOOR` once, `FORMAT_VIOLATION` four times, four unique signatures, and no `CODE_LEAK` stops.
- P-03 failed on the first issue with `GovernanceViolation`: the `coder` seat is still bound to the `agent_output/main.py` write-path contract, so a request for `agent_output/schema.json` is rejected after corrective reprompt.
- P-04 found no ODR fingerprints in cards-engine observability artifacts and no targeted cards-path code references to the ODR kernel, so the current conclusion remains that ODR and the cards path are independent subsystems.

---

### Probe Script P-01: Single-Issue Bare Minimum

**What it exercises:** `ExecutionPipeline.run_card` → single issue → single role → one model turn → output captured.  
**Model:** `qwen2.5-coder:7b` via Ollama.  
**Task:** A trivially well-defined issue: "Write a Python function that returns the Fibonacci sequence up to N terms."  
**What to observe:**
- Does it complete without error?
- Does `model_response.txt` appear in `observability/`?
- Does `parsed_tool_calls.json` appear?
- Does the run ledger record a `run_finalized` event?
- What is the `stop_reason` in the run summary?

**Location:** `scripts/probes/p01_single_issue.py`

**Shipped behavior:** The probe writes a probe-only JSON config root inside the workspace, forces the protocol run ledger so lifecycle events are inspectable, runs `ExecutionPipeline.run_card`, and persists a structured observation report to `benchmarks/results/probes/p01_single_issue.json`.

**Usage:**

```bash
ORKET_LLM_PROVIDER=ollama \
ORKET_LLM_OLLAMA_HOST=http://localhost:11434 \
python scripts/probes/p01_single_issue.py \
  --workspace .probe_workspace_p01 \
  --model qwen2.5-coder:7b \
  --json
```

**Current truth surfaced by the shipped probe:** artifact presence and `run_finalized` are directly observable; `stop_reason` is also checked, but the current cards-engine run summary does not expose a canonical `stop_reason` field, so the probe reports that absence explicitly instead of inventing one.

**Observed on 2026-03-18:** the run completed with `run_summary.status=done`, emitted `model_response.txt`, `parsed_tool_calls.json`, `checkpoint.json`, and a `run_finalized` ledger event, but the actual artifact write was `agent_output/main.py`, not `agent_output/fibonacci.py`. The run was also not a single-model-turn path: it used a `coder` turn followed by an `integrity_guard` turn.

---

### Probe Script P-02: ODR Isolation Probe

**What it exercises:** `run_round` directly, with a real Ollama model generating architect and auditor responses. No Cards engine involved.  
**Purpose:** Establish a baseline for whether the ODR convergence detection works in practice with actual model output, not fixture data.  
**What to observe:**
- How many rounds until `STABLE_DIFF_FLOOR` or `LOOP_DETECTED`?
- Does `CODE_LEAK` fire on legitimate requirement discussion?
- Is the convergence behavior stable across repeated runs with `seed=0`?
- What does the `stop_reason` distribution look like across 5 independent runs?

**Location:** `scripts/probes/p02_odr_isolation.py`

**Shipped behavior:** The probe uses Orket's canonical `LocalModelProvider`, runs repeated architect/auditor loops through `run_round`, records the full round trace for each run, and persists the result to `benchmarks/results/probes/p02_odr_isolation.json`.

**Usage:**

```bash
ORKET_LLM_PROVIDER=ollama \
ORKET_LLM_OLLAMA_HOST=http://localhost:11434 \
python scripts/probes/p02_odr_isolation.py \
  --model qwen2.5-coder:7b \
  --runs 5 \
  --task "Define requirements for a Python CLI tool that renames files based on metadata" \
  --json
```

**Observed on 2026-03-18:** across 5 live runs with `qwen2.5-coder:7b`, stop reasons were `STABLE_DIFF_FLOOR` once and `FORMAT_VIOLATION` four times. The raw-signature count was 4, so the convergence behavior was variable even with `seed=0`. No run stopped for `CODE_LEAK`.

---

### Probe Script P-03: Cards Engine Pipeline Trace

**What it exercises:** Full `run_epic` against a multi-issue epic with a real model. Not trying to succeed — trying to see what the engine does under real conditions.  
**What to observe:**
- Which issues complete, which fail, which stall?
- What do the `turn_complete` and `turn_failed` log events contain?
- Does the critical path priority queue match the actual execution order?
- What artifacts are written and which are missing?

**Location:** `scripts/probes/p03_epic_trace.py`

**Shipped behavior:** The probe writes a probe-only three-issue JSON epic, forces the protocol run ledger, executes `ExecutionPipeline.run_epic`, captures the observed issue order, compares it to the dynamic critical-path order, and persists the trace to `benchmarks/results/probes/p03_epic_trace.json`.

**Usage:**

```bash
ORKET_LLM_PROVIDER=ollama \
ORKET_LLM_OLLAMA_HOST=http://localhost:11434 \
python scripts/probes/p03_epic_trace.py \
  --workspace .probe_workspace_p03 \
  --model qwen2.5-coder:7b \
  --json
```

**Observed on 2026-03-18:** the first issue (`P03-SCHEMA`) reached a deterministic failure and ended `blocked`; `P03-WRITER` and `P03-READER` remained `ready`. The trace captured a corrective reprompt followed by `write_path_contract_not_met_after_reprompt`, and the run finalized with `run_summary.status=failed`. None of the requested probe artifacts (`schema.json`, `writer.py`, `reader.py`) were produced.

---

### Probe Script P-04: ODR + Cards Integration Probe

**What it exercises:** Whether the ODR convergence loop is wired into the Cards engine turn executor, or whether they are currently independent subsystems.  
**What to observe:**
- Does a Cards engine turn invocation trigger an ODR loop, or is ODR currently only exercised directly via the kernel API?
- Are `history_rounds` artifacts written to observability during a card run?
- Is there a `CODE_LEAK` guard in the turn executor path?

**Location:** `scripts/probes/p04_odr_cards_integration.py`

This probe is primarily a read/trace probe. The shipped version does two things:

1. Scans P-03 observability artifacts and the run summary for ODR fingerprints.
2. Falls back to a targeted code scan of `orket/application`, `orket/runtime`, and `orket/orchestration` so the report can still say something truthful even when no P-03 artifacts exist yet.

**Usage:**

```bash
python scripts/probes/p04_odr_cards_integration.py \
  --workspace .probe_workspace_p03 \
  --session-id probe-p03-epic-trace \
  --json
```

**Observed on 2026-03-18:** no ODR signals were present in the P-03 observability inventory or run summary, and the targeted code scan found no cards-path references to `run_round`, `ReactorConfig`, `ReactorState`, `history_rounds`, or `CODE_LEAK`. The current integration status is therefore `independent_subsystems`.

---

### Phase 1 Closeout

**Closeout decision:** Phase 1 is closed.

The Phase 1 objective was to produce an honest map of current behavior, not to make the cards engine succeed on the planned workloads. That objective is now met. The shipped probes answered the Phase 1 questions with live evidence where possible and structural evidence where live evidence was not the right tool.

**Exit criteria met:**
- The cards path was exercised live for a single issue and a multi-issue epic with a real local Ollama model.
- The ODR loop was exercised live, repeatedly, with a real local Ollama model.
- The cards/ODR integration question was answered with a structural audit instead of speculation.
- The observed gaps are now explicit enough to define the next phase truthfully.

**What Phase 1 established as current reality:**
- The current small-project cards path is a governed builder/guard flow, not the draft single-role single-turn path.
- The current `coder` seat is effectively constrained to `agent_output/main.py`, which blocks arbitrary requested artifact paths in cards runs.
- The current cards run summary does not expose a canonical `stop_reason`.
- The ODR loop is live but unstable with this model and prompt contract.
- The ODR loop is not currently wired into the cards executor path.

**Implication for Phase 2:** move forward assuming the current engine behavior above is the baseline truth. Phase 2 should harden auditability around that reality first, then decide which Phase 1 blockers must be remediated before Phase 3 workloads are credible.

---

## Phase 2 — Harden Auditability

Once Phase 0 (behavioral review closure) and Phase 1 (honest mapping) are complete, you have the information needed to decide what "a trustworthy audit record" looks like for Orket.

The output of Phase 2 is a definition, not just more code. Specifically:

**The Minimum Auditable Record (MAR):** The smallest set of artifacts that, given a completed run, allows a person to independently verify:

1. What input was given to the model (prompt + context)
2. What the model produced
3. Whether the output met the task contract
4. Whether the result was stable (would produce the same outcome if replayed)

Orket already generates most of this. The work of Phase 2 is ensuring it's complete, correct, and consistently present — not adding new things.

---

### Phase 2 Script Ideas

**S-01: `scripts/audit/verify_run_completeness.py`**  
Given a `session_id` and workspace, check whether all required MAR artifacts are present. Output a pass/fail report with specific missing items. This becomes the gold standard for "did a run produce a complete audit record."

**S-02: `scripts/audit/compare_two_runs.py`**  
Given two `session_id` values for the same input, compare their audit records and report where they diverge. This is the practical test for the determinism claim. Uses `first_diff_path` from `canon.py` for structural comparison. Note: this depends on W1-C (run_round immutability) and W1-B (canonicalization clarity) being resolved first.

**S-03: `scripts/audit/replay_turn.py`**  
Given a `session_id`, `issue_id`, and `turn_index`, load the persisted `messages.json` and re-run the model with the same input. Compare the new response to the original `model_response.txt`. Report whether the output is semantically equivalent or diverged. This tests whether model behavior is consistent over time for the same prompt — which is a practical question for anyone running repeated jobs.

---

## Phase 3 — First Real Workloads

Once Phase 2 is complete, you have a trustworthy audit layer. Now the question becomes: can you use it to demonstrate something real about small model coordination?

**Start with code review.** It has three properties that make it the right first workload:

1. **Ground truth exists.** You can run a review on code you already understand and check whether the model caught the real issues.
2. **It decomposes naturally.** File reading, issue identification, evidence gathering, synthesis — each is a small bounded task that a 7B model can do.
3. **Output quality is legible.** A person reading the output can immediately tell if it's good or garbage.

---

### Phase 3 Script Ideas

**S-04: `scripts/workloads/code_review_probe.py`**  
Run a single code review against a known-buggy Python file. Use the ODR to refine the review output across architect/auditor rounds. Capture the complete audit record. Compare the final output to a human-written review of the same file. This is the first real hypothesis test.

**S-05: `scripts/workloads/generate_and_verify.py`**  
Given a function signature and docstring, use the Cards engine to: generate a Python implementation, verify it is syntactically valid (deterministic check), run a basic test harness against it (small model role), and produce a pass/fail verdict with confidence. This tests whether a small model under coordination can produce working code more reliably than a single unconstrained call.

**S-06: `scripts/workloads/decompose_and_route.py`**  
Given a large task that a 7B model would fail if attempted in one shot, automatically decompose it into sub-tasks using the ODR, route each sub-task through the Cards engine as a separate issue, and collect the results. This is the core "whole is greater than the sum of its parts" hypothesis test.

---

## Tracking: What We Know vs. What We Need to Learn

| Question | Current Status | How to Answer |
|---|---|---|
| Does `run_round` work correctly with real Ollama output? | Partially: one live run reached `STABLE_DIFF_FLOOR`, but 4/5 live runs ended `FORMAT_VIOLATION`, so behavior is real but unstable | P-02 |
| Does the Cards engine complete a single issue without error? | Yes, but only through the current small-project path (`coder` then `integrity_guard`) and with a hard-wired write to `agent_output/main.py` instead of the requested artifact path | P-01 |
| Are observability artifacts consistently present after a run? | Partially: P-01 emitted the expected turn artifacts, but P-03 failed before requested workload artifacts were created | P-03 + W2-B fix |
| Is ODR wired into the Cards turn executor? | No evidence of wiring in live artifacts or targeted cards-path code | P-04 |
| Does a run produce a complete audit record? | Unknown | S-01 after Phase 2 |
| Are two runs of the same input deterministic? | Claimed but untested end-to-end | S-02 after Phase 2 |
| Can a 7B model produce a useful code review under ODR coordination? | Unknown — this is the thesis | S-04 after Phases 1+2 |
| Does task decomposition improve output quality over single-shot? | Unknown — this is the hypothesis | S-06 after all phases |

---

## Execution Order

```
Phase 0 (Wave 1 bugs) → Phase 1 (closed: probes P-01 through P-04) → Phase 2 (active: Wave 2 bugs + S-01, S-02, S-03) → Phase 3 (S-04, S-05, S-06)
                                                                       ↑
                                                        Wave 2 items run in parallel here
```

Phase 1 is now complete as a mapping exercise. The probes produced the honest starting point for everything after: not a success story, but a bounded description of what the engine currently does, where the audit record is already useful, and where the runtime still blocks credible workload claims.

---

## What This Is Not

This plan is not a roadmap to build everything at once. It is a sequenced process for getting honest answers to honest questions about what Orket can do right now, then building on what actually works.

If the Phase 1 probes reveal that the Cards engine is fundamentally broken with a real model, Phase 2 changes. If P-04 reveals that ODR is completely unwired from the execution engine, that becomes the most important gap to close before Phase 3. The probes are designed to surface reality, not confirm assumptions.

That's the point.
