# Orket — North Star
*Version 1.1 · April 25, 2026*

---

## Purpose

This document defines the product direction for Orket. It is not an implementation plan and does not create new runtime authority by itself.

The purpose of Orket is to provide a governed runtime boundary between AI-driven work and real-world effects. Orket should make consequential AI actions observable, approval-gated where required, and auditable after the fact.

Canonical documents for this lane are `north_star.md`, `pipeline_requirements.md`, and `implementation_plan.md`. Draft filenames with `_revised` are not part of the accepted authority set.

---

## North Star

**Orket is a governed runtime for AI workflows that records what an agent proposed, what was allowed, what was approved, what was executed, and what evidence exists for the outcome.**

Orket should be evaluated by one question:

> Does this make AI-driven work safer, clearer, and easier to audit before or after it affects the outside world?

Work that does not improve that boundary should not be part of the outward-facing roadmap.

---

## Product Boundary

Orket is primarily:

1. **A proposal boundary** — agent outputs are treated as proposals until admitted, approved when required, and committed.
2. **An approval boundary** — consequential tool calls can pause for operator review before effects occur.
3. **A ledger boundary** — run events, decisions, tool calls, and outcomes are written to a durable record.
4. **An inspection boundary** — operators can inspect active and completed runs without changing execution state.
5. **A connector boundary** — external tools and APIs are brought into Orket through governed connectors, not by bypassing the runtime.

Orket should not be positioned as a generic agent framework, a prompt engineering research platform, a benchmark product, or a replacement for existing application infrastructure.

---

## Core Product Claims

The outward-facing product should support these claims first:

1. **Operators can submit governed work.**
   A run has a stable identity, namespace, policy, status, and terminal outcome.

2. **Operators can review consequential proposals before effects happen.**
   Approval-required tools pause execution and expose the proposal, context, risk level, expiration time, and redacted arguments.

3. **Operator decisions are recorded.**
   Approval, denial, and timeout decisions are first-class ledger events.

4. **Operators can inspect what happened.**
   Run status, event history, summaries, and live updates are available through stable API and CLI surfaces.

5. **Operators can export and verify a run ledger.**
   The export is portable JSON, includes hashes, and can be verified without a running Orket instance.

6. **Connectors do not bypass governance.**
   Built-in and third-party connectors must declare schema, risk, timeout, and PII fields, and their calls must be recorded.

These claims are deliberately narrower than Orket's full internal architecture. They define the first outward-facing product path.

---

## First External Demo

The first complete outward-facing demo should be:

```text
Submit a task
→ agent attempts a governed tool call
→ proposal appears for review
→ operator approves or denies
→ run reaches a terminal state
→ ledger is exported
→ export verifies offline
```

This path should be understandable without reading Orket's internal governance history.

---

## Product Priorities

### 1. Approval Surface

The approval surface is the highest-leverage operator experience. It turns the governance model into something visible and usable.

Minimum useful approval surface:

- list pending approvals,
- review one proposal with context,
- approve with optional note,
- deny with required reason,
- record the decision in the ledger,
- resume or fail the run according to the policy.

For v1, denial is terminal. Recovery after denial is a future policy mode and should not be included in the first outward-facing loop.

### 2. Ledger Export

The ledger export is the audit artifact. It should be treated as a product surface, not as an internal debugging file.

The export should answer:

- what work was submitted,
- what policy applied,
- what proposals were made,
- what decisions were made,
- what tools were invoked,
- what artifacts were produced,
- why the run stopped,
- whether the record is intact.

### 3. CLI Before UI

The v1 operator interface should be CLI-first. A graphical UI is valuable later, but it should not block the outward-facing pipeline.

The CLI should cover:

- run submission,
- run status,
- approval review,
- event inspection,
- ledger export,
- offline ledger verification.

### 4. Built-In Connectors Before Connector Ecosystem

Built-in governed connectors should be hardened before investing in third-party connector discovery. The first goal is to prove that Orket can govern effects correctly, not to build a marketplace.

---

## Explicit Non-Goals for the Outward-Facing v1

The following are not part of the first outward-facing product path:

1. Graphical web UI.
2. Multi-tenant identity or role management.
3. Marketplace or connector distribution tooling.
4. Model benchmarking as an operator-facing feature.
5. Prompt reforging as an operator-facing feature.
6. Migrating Orket's internal governance lanes onto the outward-facing pipeline.
7. Claims that legacy artifacts become canonical ledgers retroactively.
8. Recovery-after-denial workflow semantics.
9. General-purpose agent framework positioning.

These may be useful later. They should not be allowed to delay the first complete governed run loop.

---

## Validation Standard

A feature advances the North Star only if it improves at least one of these:

1. proposal visibility,
2. approval control,
3. execution containment,
4. ledger completeness,
5. audit export quality,
6. offline verification,
7. connector governance.

If a feature does not improve one of these, it belongs outside the outward-facing v1 roadmap.

---

## One-Sentence Description

**Orket is a governed runtime that lets operators run AI workflows with approval-gated actions and a verifiable record of what happened.**

---

*End of North Star*
