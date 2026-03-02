Orket Federated Stream Fabric (Exploratory Requirements v0)
1. Purpose

Define requirements for an optional Orket capability that:

Brokers communication between multiple weak/free model streams

Applies deterministic governance before and after external communication

Stabilizes outputs via structured arbitration

Preserves local-first philosophy

Enables privacy-preserving workflows

This document does not commit Orket to implementation. It defines a candidate capability for future evaluation.

2. Design Principles (Locked)

Local Canonical Authority

The canonical ledger and state remain local.

No external stream can mutate state directly.

Deterministic Admission Control

All inbound proposals must pass schema validation, invariant checks, and normalization.

All outbound payloads must pass policy filtering.

Untrusted External Streams

External model streams are treated as probabilistic and untrusted.

All outputs are considered proposals only.

Optionality

Orket must function fully offline.

Federated streams are an augmentation layer, not a dependency.

Measurability

Any performance claims must be empirically measurable (convergence rate, stabilization rounds, etc.).

3. High-Level Architecture
Internet
   |
Outbound Policy Gate (PII scrub, scope restrict, schema lock)
   |
Federated Streams (N independent model channels)
   |
Inbound Admission Gate (schema validate, diff, invariant check)
   |
Unify Gate (deterministic arbitration + optional model assist)
   |
Canonical Ledger (local, authoritative)

Orket acts as:

Broker

Privacy firewall

Deterministic arbiter

Drift suppressor

4. Core Capabilities
4.1 Multi-Stream Proposal Intake

Spawn N independent model streams

Send structured projection pack (see below)

Collect structured proposals

Score proposals against deterministic metrics

Prune drifting or non-compliant streams

4.2 Projection Pack (Outbound State Snapshot)

Must include:

Current canonical contract

Locked decisions

Explicit invariants

Open mutation scope

Rejected proposal summaries (structured)

Allowed output schema

Must NOT include:

Raw transcript history

Unbounded conversation

Hidden constraints

4.3 Admission Control

For each proposal:

Schema validation

Forbidden token / policy filter

Invariant compliance check

Diff against canonical state

Drift scoring

Canonical normalization + digest

Non-compliant proposals are rejected and optionally fed back as structured rejection summaries.

4.4 Unify Gate

Produces:

Accepted patch (if any)

Rationale (structured)

Rejected deltas

Drift report

Stabilization score

Final output must pass deterministic revalidation before ledger commit.

5. Target Use Case Categories
5.1 Code Generation (Strong Candidate)

Why suitable:

Testable via compilation/unit tests

Diffable

Structured output possible

Deterministic validators available

Fabric value:

Parallel solution exploration

Test-driven arbitration

Failure-based pruning

Reduced hallucinated code patterns

Measurable metrics:

Pass rate on test suites

Time to first stable compile

Iteration count to stability

Diff shrink rate

5.2 Privacy-Preserving Legal Form Drafting (Strong Candidate)

Primary differentiator: Security.

5.2.1 PII Firewall Model

User inputs:

Name

Address

SSN

Business info

Sensitive financial details

Orket:

Extracts and isolates PII locally.

Replaces with structured placeholders.

Sends only anonymized template context to streams.

Receives structured draft template.

Reinserts PII locally into validated template.

Produces final document locally.

No PII leaves the machine.

5.2.2 Security Requirements

Deterministic placeholder mapping

Guaranteed PII non-leak enforcement

Outbound content scanning

Structured reinjection logic

Audit log of all redaction/reinsertion events

5.2.3 Benefits

Free model usage without identity exposure

Structured legal template drafting

Reduced privacy exploitation risk

Lower barrier for basic legal documentation

5.2.4 Limitations

Not a substitute for licensed legal advice

Jurisdiction logic may require deterministic rule tables

Weak models may miss edge-case legal nuance

5.3 Resume / Career Assistance (Moderate Candidate)

Benefits:

Structured rewriting

Style variation via parallel streams

Fact preservation enforcement

Limitations:

Quality subjective

Hard to deterministically score “impact”

5.4 Tax Assistance (High Risk, Conditional)

Viable only if paired with:

Deterministic rule engine

Static regulatory datasets

Strong invariant checks

Pure model-driven tax advice is unsafe.

5.5 Financial Document Reconciliation (Structured Extraction)

Strong candidate when combined with:

Deterministic reconciliation engine

Local parsing pipeline

Model-assisted interpretation only

6. Security Requirements (Cross-Cutting)

All outbound traffic must pass:

PII scrub

Forbidden token filter

Schema enforcement

Scope restriction

All inbound traffic must pass:

Contract validation

Leak detection

Drift detection

Deterministic normalization

Canonical state must remain:

Local

Replayable

Auditable

Hash-addressable

7. Performance & Evaluation Criteria

To justify this capability, it must demonstrate:

Reduced stabilization rounds vs single weak model

Comparable time-to-stable-output vs paid model (within defined bounds)

Acceptable accuracy degradation (quantified)

Measurable drift suppression rate

Clear privacy boundary enforcement

No claims without data.

8. Non-Goals

Replacing frontier paid models entirely

Achieving frontier-level reasoning depth

Acting as legal counsel

Acting as certified tax authority

Eliminating all model hallucination

9. Open Questions

Optimal number of streams (N)

Burst vs continuous streams

Drift scoring formula

Arbitration weighting strategy

Cost-benefit threshold for enabling fabric

Benchmark suite definition

Summary

This exploratory capability positions Orket as:

A deterministic broker over probabilistic model streams

A privacy firewall for identity-sensitive workflows

A stabilizer for weak/free model outputs

A governance-first orchestration layer

Primary promising domains:

Code generation with test-driven arbitration

Privacy-preserving legal form drafting

This document captures direction only. Implementation requires empirical validation.