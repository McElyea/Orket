# Orket — Behavioral Review
*Reviewed April 25, 2026 · Claude Sonnet 4.6*

---

## Overview

This review examines Orket's observable runtime behavior, product posture, and process patterns — distinct from code-level bugs. It covers how the system behaves under real conditions, how the development process shapes outcomes, and where stated intent diverges from actual behavior.

---

## 1. The Governance Process Is Governing the Developers, Not the Product

The most prominent behavioral observation across the entire codebase is the **inversion of governance load**. The project has:

- Dozens of "contract delta" documents
- "Lane closeout" archives for every feature
- "Truth claims" (Claim A through Claim G) with evidence requirements
- A weekly baseline retention job
- A recurring maintenance cycle report with a formal checklist
- A `TRUTHFUL_RUNTIME_CONFORMANCE_GOVERNANCE_CONTRACT.md`

This is remarkable discipline. The problem is that this governance infrastructure appears to be primarily governing the *documentation and proof process* rather than gating on *user-observable product quality*. Features are considered "closed" when they have a proof artifact, not when they have users. The changelog entries for 0.4.8 through 0.4.12 are almost entirely documentation-and-contract moves. A user reading the changelog cannot distinguish a fix that changes runtime behavior from an internal document reorganization.

**Behavioral risk:** The team is optimizing for governance conformance rather than product outcomes. The proof process becomes the product.

---

## 2. The "Fail-Closed" Default Is Inconsistently Applied

Orket's stated design principle is "fail-closed." This appears in the code review, the spec docs, and the `.env.example` comments. But the actual runtime behavior is inconsistent:

**Where it is correctly applied:**
- API key auth: fails closed if `ORKET_API_KEY` is not set (the env var comment confirms this)
- Webhook secret: "fails fast if secret is missing" (confirmed in changelog 0.3.11)
- `NEEDS_APPROVAL` lifecycle: closes the governed run pending operator action

**Where fail-closed is violated:**
- `extract_openai_content` returns `""` on a structurally broken provider response
- `_normalized_tools` silently returns `[]` when no tool context is found — the agent runs unconstrained
- `_to_int` returns `None` silently for malformed token counts — usage tracking proceeds with None
- `build_orket_session_id` generates a derived hash instead of raising when no session context is available

The pattern: fail-closed is applied at the infrastructure/auth boundary but leaks to silent-success at the data extraction boundary. Corrupted LLM responses are normalized into empty strings, zero counts, or empty lists rather than being surfaced as explicit failures.

---

## 3. The "Everything Is a Proposal" Architecture Is Not Fully Implemented

The Nervous System requirements document (the canonical architecture statement) describes a clear pipeline:

```
Outbound Policy Gate → Untrusted Sources → Inbound Admission Gate → Unify Gate → Commit Gate → Canonical Ledger
```

Looking at the actual implementation:

- The **Canonical Ledger** exists (run_summary.json, control plane DB)
- The **Admission Gate** exists (schema validation, cardinality checks, governed seat enforcement)
- The **Commit Gate** partially exists (approval-required workflow)
- The **Outbound Policy Gate** (PII scrub, forbidden token filter, scope restriction) — evidence of this is sparse in the source code visible in this dump

The missing piece is the **PII/outbound scrub layer**. The spec says "All outbound traffic must pass: PII scrub + placeholder substitution, Forbidden token / pattern filter, Schema enforcement." There is no `outbound_policy_gate.py` or equivalent in the visible codebase. If this exists and was simply not dumped, the governance docs should reference it clearly. If it does not exist, the architecture is running without its stated privacy firewall.

---

## 4. Local-First Is the Stated Priority, But the Portability Path Is Stuck

The Gemma Prompt Reforger lane (active as of the dump date, April 2026) records the following as its current checkpoint:

> "The bounded Gemma-only portability path did not clear the frozen corpus. The lane stays paused because the bounded Gemma-only portability path did not clear the frozen corpus."

And:

> `gemma-3-4b-it-qat` remains executable but still only reaches `accepted_slices=2` of `5`

The portability target (a 4B parameter model for 3070 Ti-class hardware) cannot pass the tool-use corpus. This is the model that represents Orket's accessible local-first story — if you don't have a high-end GPU, you run the 4B model. The 4B model does not work.

This is a behavioral product problem: **the local-first value proposition degrades severely below the high-end hardware bar**. The 12B model works. The 4B model doesn't. The lane is paused, not resolved.

---

## 5. The ODR (Orchestrated Decision-Making Round) Has Real Nondeterminism That Is Known and Deferred

The changelog for 0.4.5 ("The Archived Recovery Lane") states:

> "Archived the runtime-stability live recovery lane... moved the remaining Claim E work into a staged hardening lane instead of leaving it as fake active closeout work."

Claim E is about deterministic stability — same inputs producing same outputs. The drift diff summary for Claim E is explicitly marked as "remaining nondeterminism is shareable." The ODR gate tool exists to detect this. The nondeterminism is known. It is tracked. It is not fixed.

This is not inherently a problem — being honest about known nondeterminism is admirable. But the behavioral consequence is that **the system cannot be fully replayed from its run records**. The audit guarantee — one of Orket's core value propositions — has a known hole.

---

## 6. The Approval Checkpoint Is a Sharp Edge for Operators

The `write_file` approval-checkpoint feature (0.4.x closeout) has a specific behavioral contract:

- Approve → same governed run continues
- Deny → same governed run terminates
- Target-run identity drift → fail-closed

But the API contract says:

> "no new operator-visible resume API, no broader approval-required tool family, and no broader namespace scope were added"

This means operators can only approve `write_file` in the `issue:<issue_id>` namespace. Any other tool or namespace gets no approval pathway — just stop. If an operator wants to approve a read-before-write that requires approval, there is no mechanism. This creates a behavioral cliff: the approval system exists, operators expect to use it for tool safety, but it works for exactly one tool.

---

## 7. The Sandbox Lifecycle Is in a False-Active Anti-Pattern

The 0.4.10 changelog ("Sandbox Lifecycle Hardening") specifically addressed:

> "recovery terminalizes non-running or restart-looping runtimes with cleanup scheduling instead of leaving them in false-active state"

This was a bug that was fixed. But the fix description implies the previous behavior was that crashed sandboxes stayed in an "active" state in the database without actually running. This is a silent correctness failure — the control plane said "active" but Docker said "stopped." This class of divergence (database state vs. actual process state) is now addressed with `SandboxRuntimeInspectionService`, but the pattern of divergence (database as truth, process as secondary) is inherently prone to re-emergence.

---

## 8. The Version Cadence Signals Process Overhead, Not Progress

The release cadence is:
- `0.3.16` (Feb 11) — significant functional release (Decision Node Architecture)
- 5-week gap
- `0.3.17` through `0.4.12` — 16 releases in 5 days (March 12–17)
- `0.4.12` → next major release TBD

The 16-release burst in 5 days maps exactly to the governance lane closeout process. Each "cut" is a version bump. This means the versioning system is being driven by documentation events, not by functional changes. The changelog itself confirms this: most of these releases are "compatibility_status: preserved, affected_audience: internal_only, migration_requirement: none."

**Behavioral effect on external trust:** If Orket ever has external users or downstream integrators, this cadence will create update fatigue. Fourteen patch releases in 5 days, even with `migration_requirement: none`, requires tracking. The governance ceremony is generating version noise.

---

## 9. The Benchmark/Proof System Has a Staging-Authority Boundary Problem

The architecture separates:
- `benchmarks/staging/` — candidate artifacts
- `benchmarks/published/` — approved artifacts
- `benchmarks/results/` — raw run artifacts

But the Gemma Prompt Reforger lane records:

> "The current live artifact `benchmarks/staging/General/prompt_reforger_gemma_tool_use_cycle.json` records..."

And then makes claims about the lane's status based on what this staging artifact says. Staging artifacts are supposed to be pre-publication. Using a staging artifact to make a lane completion determination is using unreviewed evidence as lane authority — which contradicts the staging/published separation.

---

## 10. The iDesign Validator Reveals an Architectural Boundary Enforcement Problem

The 0.3.8 changelog adds `orket/services/idesign_validator.py` as "a new service for enforcing architectural boundaries." This is a code-level enforcement tool for the iDesign architectural methodology (separation of managers, engines, accessors, utilities).

The fact that this validator needed to be built suggests the architectural boundaries were already being violated. The validator exists as a reactionary tool to prevent drift, not as a design primitive that made drift impossible. The more interesting question is: is it running in CI? If so, why do Issues 3, 5, and 55 in the code review still exist (empty subclasses, missing protocols, modular antipatterns)?

---

## 11. The "Truthful Runtime" Lane Name Is Philosophically Revealing

The project ran multiple lanes named things like:
- `TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT`
- `TRUTHFUL_RUNTIME_CONFORMANCE_GOVERNANCE_CONTRACT`
- `TRUTHFUL_RUNTIME_MEMORY_TRUST_CONTRACT`

A system that needs an explicit "Truthful Runtime" project lane is acknowledging that its runtime was not previously fully truthful. The lanes exist because there were silent fallbacks, false-green closures, and success-shaped drift in earlier versions. That is honest and the remediation work is real.

The behavioral note is: **Orket's stated value proposition is deterministic, auditable, truthful runtime behavior, and the team has been actively remediating gaps in that guarantee up to v0.4.12 (the most recent release in the dump).** The guarantee is improving but is not yet complete.

---

## 12. The Extension SDK Relationship to the Core Is Underspecified

The `orket_extension_sdk` package is a separate CI package but its relationship to the core runtime is not clear from the visible codebase:
- Does the SDK ship independently?
- Does it have its own versioning?
- Can an extension author rely on the SDK contract independently of the core version?

The extension authority docs say "Extensions and client-facing repos must remain consumers of host-owned runtime contracts, not alternate authority centers." But there is no visible semantic versioning guarantee for the SDK relative to the core. If the core changes a runtime contract, extension authors have no documented SLA on how much notice they get.

---

## 13. The Terraform Plan Reviewer Is a Scope Indicator Worth Watching

The project added a Terraform plan reviewer (v1, March 2026). This is a meaningful scope signal: Orket is not just a code-generation agent orchestration system — it is reaching toward infrastructure-change governance. A system that can review Terraform plans is positioned to gate on infrastructure safety, not just code correctness.

This is either a feature that was added because a specific customer needed it, or it is an early indicator of Orket's intended direction toward DevOps automation beyond code. Either way, it reveals product scope ambiguity: is Orket a code agent runtime, a DevOps automation runtime, or a general-purpose governed agent execution environment?

---

## Summary

| # | Behavioral Issue | Risk Level |
|---|------------------|------------|
| 1 | Governance process governs docs, not user outcomes | High |
| 2 | Fail-closed inconsistently applied at data extraction layer | High |
| 3 | PII outbound scrub may be missing from implementation | High |
| 4 | Portability path (4B model) is stuck and paused | High |
| 5 | Known ODR nondeterminism deferred to "staged hardening" | Medium |
| 6 | Approval checkpoint covers only `write_file` in one namespace | Medium |
| 7 | Sandbox state divergence pattern can re-emerge | Medium |
| 8 | Version cadence driven by doc events, not functional changes | Medium |
| 9 | Staging artifacts used as lane authority | Medium |
| 10 | iDesign validator is reactive, not preventive | Low |
| 11 | "Truthful Runtime" lanes acknowledge known gaps | Low |
| 12 | SDK extension versioning SLA is undefined | Low |
| 13 | Terraform scope indicates product direction ambiguity | Low |

---

*End of Behavioral Review*
