Orket Governance Fabric (Unified Requirements v0.1)

Date: 2026-03-03

Execution status note (2026-03-03):

- Locked implementation plan for Nervous System v1: `docs/projects/future/NervousSystem/IMPLEMENTATION_PLAN.md`
- v1 execution scope is action-path only (`action.tool_call`), with UnifyGate intentionally out of the runtime path

1. Purpose

Define requirements for an optional Orket capability that:

Brokers communication between multiple weak/free model streams and/or untrusted agent “brains”

Applies deterministic governance before and after external communication or execution

Stabilizes outcomes via structured arbitration

Preserves local-first canonical authority

Enables privacy-preserving workflows (PII + credential isolation)

Produces measurable safety and performance outcomes

This document does not commit Orket to implementation. It defines a candidate capability for evaluation.

2. Design Principles (Locked)
2.1 Local Canonical Authority

Canonical ledger and authoritative state remain local.

No external stream/agent can mutate state directly.

All state mutation is performed only by Orket after deterministic gates.

2.2 Everything Is a Proposal

External outputs are proposals, not truth:

Model outputs → Content proposals

Tool call intents → Action proposals

State mutations → State patch proposals

A proposal can be accepted, rejected, or held for approval.

2.3 Deterministic Admission and Commit

All inbound proposals must pass deterministic checks (schema, invariants, normalization, drift scoring).

All outbound payloads must pass deterministic policy filtering (PII scrub, scope restriction, schema lock).

Final unified output must pass deterministic revalidation before ledger commit or tool execution.

2.4 Untrusted External Inputs

External model streams and agent decisions are treated as probabilistic and untrusted.

Orket never assumes external compliance.

2.5 Optionality / Offline-First

Orket must function fully offline.

Federated streams and agent adapters are augmentation layers, not dependencies.

2.6 Measurability

Any claim (stability, safety, speed) must be empirically measurable and reproducible.

Determinism is testable: same inputs → same decisions.

3. Unifying Abstraction

Orket treats all incoming “work” as a ProposalEnvelope with a typed payload:

content.* → drafts, code patches, templates, extraction results

action.* → tool call intent (write file, send email, call API, run command)

state.patch → patch to canonical state/contract

All proposals flow through the same pipeline:

Outbound Projection → Proposal Intake → Inbound Admission Gate → Unify Gate → Commit Gate → Ledger

4. High-Level Architecture
Internet (optional)
   |
Outbound Policy Gate (PII scrub, scope restrict, schema lock)
   |
Untrusted Sources (N model streams, agent adapters, external services)
   |
Inbound Admission Gate (schema validate, invariant check, drift score, normalize)
   |
Unify Gate (deterministic arbitration + optional bounded assist)
   |
Commit Gate (revalidate + approval enforcement)
   |
Canonical Ledger + Canonical State (local, authoritative)

Orket acts as:

Broker

Privacy firewall

Deterministic arbiter

Drift suppressor

Audit journal

5. Core Capabilities (Required)
5.1 Canonical Ledger (Local, Append-Only)

Must:

Record every outbound projection, inbound proposal, gate decision, unify decision, commit, and execution result.

Be append-only and hash-addressable (digest per event).

Be replayable: gating/arbitration decisions must be reproducible from recorded inputs and canonical state snapshots/digests.

Be auditable: structured events with stable schemas.

5.2 Canonical Contract and Invariants

Must:

Define:

schema of canonical state

invariants (hard rules that must hold)

allowed mutation scope (what can change now)

locked decisions (immutable until explicitly unlocked)

Be included (or referenced by digest) in projection packs.

5.3 Projection Pack (Outbound Scoped Context)

Must include:

Canonical contract (or digest reference)

Locked decisions

Explicit invariants

Open mutation scope (allowed mutation surfaces)

Rejected proposal summaries (structured)

Allowed output schema(s)

Policy summary relevant to the request (what’s allowed/forbidden)

Must NOT include:

Raw transcript history

Unbounded conversation

Hidden constraints

Raw credentials

Raw PII (unless explicitly configured)

Determinism requirement:

Given (canonical_state_digest, contract_digest, policy_digest, request_digest, scope_digest), the projection pack is reproducible (or canonical-normalizable to the same digest).

5.4 Outbound Policy Gate

All outbound traffic must pass:

PII scrub + placeholder substitution (configurable categories)

Forbidden token / pattern filter

Schema enforcement (projection pack schema; allowed output schema)

Scope restriction (only allowed fields)

Digest recording (payload digest + policy version)

5.5 Multi-Source Proposal Intake

Must:

Spawn/manage N independent model streams and/or agent adapters.

Identify sources (source_id, source_type, trust_tier).

Collect proposals in a typed envelope.

Rate-limit and timeout per source.

Prune sources for repeated violations or high drift.

5.6 Inbound Admission Gate (Deterministic)

For each proposal, perform (in order):

Schema validation (strict)

Forbidden token/policy filter

Leak detection (PII/secrets)

Invariant compliance check

Diff vs canonical state (if applicable)

Drift scoring (deterministic formula + thresholds)

Canonical normalization + digest

Outcomes:

ACCEPT_TO_UNIFY

REJECT

NEEDS_APPROVAL

QUARANTINE

All outcomes produce structured reason codes and are logged.

5.7 Unify Gate (Deterministic Arbitration)

Consumes admitted proposals and produces:

Accepted patch/action (optional)

Structured rationale

Rejected deltas with reasons

Drift report per source + aggregate

Stabilization score

Determinism requirement:

Same admitted proposals + same canonical state + same arbitration config → same unify output.

Arbitration strategies (configurable):

deterministic scoring selection

validator tournament (tests/linters/schema validators)

merge with deterministic conflict rules (for patches)

optional “bounded assist” (allowed only if pinned to deterministic inputs + recorded digests)

5.8 Commit Gate (Final Revalidation + Execute/Commit)

Before ledger commit or tool execution:

Re-run relevant validations on final unified output.

Enforce approval requirements for high-risk actions.

Record commit event with input proposal digests, validator results, and approvals.

6. Nervous System Path (Agent Actions)
6.1 ToolGate (Action Admission)

Action proposals must declare:

tool identity + version

typed arguments

expected side effects (risk class)

requested scope (resources/targets)

rollback metadata (if available)

Gates:

Scope Gate (tool + target allowed)

Policy Gate (forbidden actions/destinations/data classes)

Credential Gate (replace raw creds with scoped tokens)

Risk Gate (destructive/irreversible → approval required)

Journal Gate (log proposal + decision)

6.2 Approval Flow (Human-in-the-Loop)

Must:

Deterministic rules for requiring approval

UX that shows: intent, diff/targets, risk tier, data leaving machine

Approve / deny / edit

Log approvals as first-class ledger events

6.3 Post-Execution Validation

After tool execution:

Validate result schema

Detect leaked secrets/PII in results

Sanitize before returning to agent

Log result digest + sanitization actions

7. Privacy Firewall (Cross-Cutting)
7.1 PII Placeholder Mapping

Must:

Deterministic placeholder IDs (stable within a session; optional cross-session stability)

Configurable categories (name, address, SSN, etc.)

Reinsertion only into validated template slots

Audit log of every redaction and reinsertion event (category + target + digest links)

7.2 Credential Isolation

Must:

Never expose raw credentials to external sources

Issue scoped capability tokens (least privilege) for tools/resources/time

Log token issuance and usage (without secret material)

8. Performance & Evaluation Criteria (Required)
8.1 Stabilization (Content)

stabilization rounds to convergence

diff shrink rate

validator pass rate (tests/linters/schema)

rejection distribution (schema/invariant/drift/leak)

8.2 Safety (Actions)

blocked dangerous action rate (true positives)

false block rate (user overrides)

approval frequency by risk tier

executed-outside-policy incidents (target: zero in tests)

8.3 Privacy

outbound PII leak rate (target: zero)

credential exposure incidents (target: zero)

redaction/reinsertion correctness rate

“No claims without data.”

9. Non-Goals

Replacing frontier paid models entirely

Achieving frontier-level reasoning depth

Acting as legal counsel

Acting as a certified tax authority

Eliminating all hallucination

“Perfect safety” claims

10. Open Questions

Optimal number of streams (N) for different tasks

Burst vs continuous stream strategy

Drift scoring formula and thresholds

Arbitration weighting strategy

Cost-benefit threshold for enabling fabric

Benchmark suite definition (anti-gaming)

Determinism boundary for any optional assist

Starter Schemas (Draft)

These are intentionally strict and “ledger-friendly.” They’re v0 drafts you can evolve.

A) ProposalEnvelope (JSON Schema)
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://orket.local/schemas/proposal_envelope.v0.json",
  "title": "ProposalEnvelope v0",
  "type": "object",
  "additionalProperties": false,
  "required": ["proposal_id", "proposal_type", "source", "created_at", "payload", "context"],
  "properties": {
    "proposal_id": {
      "type": "string",
      "description": "Stable unique ID for this proposal (UUID or hash).",
      "minLength": 8
    },
    "proposal_type": {
      "type": "string",
      "enum": [
        "content.patch",
        "content.template",
        "content.extraction",
        "content.message",
        "action.tool_call",
        "state.patch"
      ]
    },
    "source": {
      "type": "object",
      "additionalProperties": false,
      "required": ["source_id", "source_type", "trust_tier"],
      "properties": {
        "source_id": { "type": "string", "minLength": 1 },
        "source_type": { "type": "string", "enum": ["model_stream", "agent_adapter", "local_tool", "human"] },
        "trust_tier": { "type": "string", "enum": ["untrusted", "constrained", "trusted_local"] },
        "model": {
          "type": "object",
          "additionalProperties": false,
          "required": [],
          "properties": {
            "provider": { "type": "string" },
            "name": { "type": "string" },
            "version": { "type": "string" }
          }
        }
      }
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "context": {
      "type": "object",
      "additionalProperties": false,
      "required": ["projection_pack_digest", "canonical_state_digest", "contract_digest", "policy_digest"],
      "properties": {
        "projection_pack_digest": { "type": "string", "minLength": 8 },
        "canonical_state_digest": { "type": "string", "minLength": 8 },
        "contract_digest": { "type": "string", "minLength": 8 },
        "policy_digest": { "type": "string", "minLength": 8 },
        "request_id": { "type": "string" },
        "trace_id": { "type": "string" }
      }
    },
    "claims": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "rationale": { "type": "string", "maxLength": 8000 },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "expected_effect": {
          "type": "string",
          "description": "Short claim about what this proposal does (e.g., 'fixes failing test X').",
          "maxLength": 1024
        }
      }
    },
    "payload": {
      "type": "object",
      "description": "Typed payload; validated by proposal_type-specific schemas in code.",
      "additionalProperties": true
    },
    "attachments": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["kind", "digest"],
        "properties": {
          "kind": { "type": "string", "enum": ["diff", "file", "test_report", "validator_report"] },
          "digest": { "type": "string", "minLength": 8 },
          "media_type": { "type": "string" },
          "bytes": { "type": "integer", "minimum": 0 }
        }
      }
    }
  }
}
B) ProjectionPack (JSON Schema)
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://orket.local/schemas/projection_pack.v0.json",
  "title": "ProjectionPack v0",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "pack_id",
    "created_at",
    "canonical",
    "scope",
    "invariants",
    "locked_decisions",
    "allowed_output_schemas",
    "rejection_summaries",
    "policy_summary"
  ],
  "properties": {
    "pack_id": { "type": "string", "minLength": 8 },
    "created_at": { "type": "string", "format": "date-time" },

    "canonical": {
      "type": "object",
      "additionalProperties": false,
      "required": ["canonical_state_digest", "contract_digest"],
      "properties": {
        "canonical_state_digest": { "type": "string", "minLength": 8 },
        "contract_digest": { "type": "string", "minLength": 8 },
        "contract_version": { "type": "string" }
      }
    },

    "scope": {
      "type": "object",
      "additionalProperties": false,
      "required": ["mutation_scope", "visibility_scope"],
      "properties": {
        "mutation_scope": {
          "type": "object",
          "additionalProperties": false,
          "required": ["allowed_paths"],
          "properties": {
            "allowed_paths": {
              "type": "array",
              "items": { "type": "string", "minLength": 1 },
              "minItems": 1,
              "description": "JSON-pointer-like paths that are allowed to change (e.g., '/contracts/0/clauses')."
            },
            "forbidden_paths": {
              "type": "array",
              "items": { "type": "string" }
            },
            "max_patch_bytes": { "type": "integer", "minimum": 0, "default": 20000 }
          }
        },
        "visibility_scope": {
          "type": "object",
          "additionalProperties": false,
          "required": ["allowed_fields"],
          "properties": {
            "allowed_fields": { "type": "array", "items": { "type": "string" } },
            "redacted_fields": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },

    "invariants": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["invariant_id", "description", "severity"],
        "properties": {
          "invariant_id": { "type": "string", "minLength": 1 },
          "description": { "type": "string", "minLength": 1, "maxLength": 2048 },
          "severity": { "type": "string", "enum": ["hard", "soft"] }
        }
      }
    },

    "locked_decisions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["decision_id", "summary"],
        "properties": {
          "decision_id": { "type": "string" },
          "summary": { "type": "string", "maxLength": 2048 }
        }
      }
    },

    "rejection_summaries": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["rejection_id", "reason_codes", "summary"],
        "properties": {
          "rejection_id": { "type": "string" },
          "reason_codes": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
          "summary": { "type": "string", "maxLength": 2048 },
          "example_diff_digest": { "type": "string" }
        }
      }
    },

    "allowed_output_schemas": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["schema_id", "media_type"],
        "properties": {
          "schema_id": { "type": "string", "minLength": 1 },
          "media_type": { "type": "string", "enum": ["application/json", "text/plain"] },
          "schema_digest": { "type": "string" }
        }
      }
    },

    "policy_summary": {
      "type": "object",
      "additionalProperties": false,
      "required": ["policy_digest", "outbound_rules", "data_classes"],
      "properties": {
        "policy_digest": { "type": "string", "minLength": 8 },
        "outbound_rules": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Human-readable policy summary (not authoritative; the digest is authoritative)."
        },
        "data_classes": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Enumerated data classes allowed to appear (e.g., 'anonymized_context', 'public_code')."
        }
      }
    },

    "pii_placeholders": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "enabled": { "type": "boolean", "default": false },
        "placeholder_format": { "type": "string", "default": "{{PII:TYPE:ID}}" },
        "categories": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
C) LedgerEvent (JSON Schema)
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://orket.local/schemas/ledger_event.v0.json",
  "title": "LedgerEvent v0",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_type", "created_at", "digests", "body"],
  "properties": {
    "event_id": { "type": "string", "minLength": 8 },
    "event_type": {
      "type": "string",
      "enum": [
        "projection.issued",
        "proposal.received",
        "admission.decided",
        "unify.decided",
        "commit.applied",
        "approval.recorded",
        "action.executed",
        "action.result_validated",
        "pii.redacted",
        "pii.reinserted",
        "credential.token_issued",
        "credential.token_used",
        "source.pruned",
        "incident.detected"
      ]
    },
    "created_at": { "type": "string", "format": "date-time" },

    "digests": {
      "type": "object",
      "additionalProperties": false,
      "required": ["event_digest"],
      "properties": {
        "event_digest": { "type": "string", "minLength": 8 },

        "canonical_state_before": { "type": "string" },
        "canonical_state_after": { "type": "string" },

        "contract_digest": { "type": "string" },
        "policy_digest": { "type": "string" },

        "projection_pack_digest": { "type": "string" },

        "proposal_digest": { "type": "string" },
        "unify_output_digest": { "type": "string" },
        "commit_digest": { "type": "string" },

        "payload_digest": { "type": "string" },
        "result_digest": { "type": "string" }
      }
    },

    "links": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "trace_id": { "type": "string" },
        "request_id": { "type": "string" },
        "parent_event_id": { "type": "string" }
      }
    },

    "body": {
      "type": "object",
      "description": "Event-type-specific structured body.",
      "additionalProperties": true
    }
  }
}
D) Supporting Schema: AdmissionDecision (Optional but practical)
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://orket.local/schemas/admission_decision.v0.json",
  "title": "AdmissionDecision v0",
  "type": "object",
  "additionalProperties": false,
  "required": ["decision", "reason_codes", "drift", "normalization"],
  "properties": {
    "decision": { "type": "string", "enum": ["ACCEPT_TO_UNIFY", "REJECT", "NEEDS_APPROVAL", "QUARANTINE"] },
    "reason_codes": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
    "drift": {
      "type": "object",
      "additionalProperties": false,
      "required": ["score", "threshold"],
      "properties": {
        "score": { "type": "number", "minimum": 0 },
        "threshold": { "type": "number", "minimum": 0 },
        "signals": { "type": "array", "items": { "type": "string" } }
      }
    },
    "normalization": {
      "type": "object",
      "additionalProperties": false,
      "required": ["normalized_payload_digest"],
      "properties": {
        "normalized_payload_digest": { "type": "string", "minLength": 8 },
        "notes": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
Next step (execution source of truth)

For implementation sequencing and locked v1 semantics, use:

- `docs/projects/future/NervousSystem/IMPLEMENTATION_PLAN.md`

If you want to start implementing immediately, the most “first-week buildable” slice is:

Implement LedgerEvent append-only log + digests

Implement ProjectionPack creation + outbound scrub (PII placeholdering optional)

Implement ProposalEnvelope intake + AdmissionDecision (schema + drift placeholder)

Implement a simple Unify strategy: deterministic winner selection (e.g., lowest drift + passes validators)
