# Orket as Nervous System (Exploratory Direction v0)

Date: 2026-03-02

## The Metaphor

AI agent (brain) decides what to do. Orket (nervous system) validates, routes, and gates every action. External tools and APIs (muscle) execute.

The brain can be anything: OpenClaw, Claude, a local llama model, whatever comes next. The nervous system doesn't care. Its job is the same regardless of which brain is driving.

## The Problem

Agent frameworks like OpenClaw give AI direct access to email, messaging, filesystems, credentials, and APIs. When something goes wrong — context overflow, prompt injection, malicious extensions, rogue behavior — there is no layer between "the AI decided to do this" and "it happened."

The result: users who want to use agents are too afraid of the consequences. The technology is powerful but uncontrolled.

## The Thesis

Orket is not an agent framework. Orket is the **policy and routing layer** that sits between any agent and the things it can touch. Every action the agent wants to take is a proposal. Every proposal passes through gates. The user defines what's allowed, what requires approval, and what's forbidden.

This is the same architecture as the Federated Stream Fabric (see `future/UIForge/Broker.md`), applied to agent execution instead of model streams:

| Broker Concept | Nervous System Equivalent |
|---|---|
| Untrusted external streams | Untrusted agent decisions |
| Projection pack (outbound) | Scoped context given to agent |
| Admission control (inbound) | ToolGate policy enforcement |
| Unify gate | Action arbitration + approval |
| Canonical ledger | Local state of truth |
| PII firewall | Credential and data isolation |
| Drift detection | Behavioral deviation alerting |

## What Orket Already Has

| Component | Nervous System Role | Status |
|---|---|---|
| ToolGate | Action-level policy enforcement | Working (20/20 tests) |
| State machine | Legal state transition enforcement | Working |
| TurnExecutor | Bounded execution control | Working |
| Sandbox orchestrator | Isolated execution environment | Architecture exists, needs security fixes |
| Reforger | Content/extension validation pipeline | Working |
| PolicyGate (Lie Detector) | Truth/lie detection on outputs | Working |
| SDK capability system | Typed, preflight-checked integrations | Working |

## What's Missing

| Gap | Description |
|---|---|
| Agent adapter protocol | Generic interface for intercepting agent tool calls (OpenClaw, Claude tools, MCP, etc.) |
| Credential vault | Scoped credential access — agent gets a token for "read email" not "full Gmail access" |
| Action journal | Append-only log of every action proposed, approved, rejected, executed |
| Approval flow | Human-in-the-loop for destructive or high-risk actions |
| Behavioral drift detection | "This agent is doing something it hasn't done before" alerting |
| Extension validation | Malicious skill/extension detection before loading (ClawHub has 15% malicious rate) |

## Design Principles (Inherited from Broker)

1. **Local canonical authority.** Orket's state is local. No agent can mutate it directly.
2. **All agent actions are proposals.** Nothing executes without passing gates.
3. **Agents are untrusted.** Doesn't matter if it's your own model or a cloud API.
4. **Orket works offline.** Agents are an augmentation layer, not a dependency.
5. **No claims without data.** Any safety claim must be empirically testable.

## Architecture Sketch

```
Agent (OpenClaw / Claude / local model / future thing)
   |
   | proposes action
   v
Orket Nervous System
   |
   +-- Scope Gate: Is this action within the agent's allowed scope?
   +-- Policy Gate: Does this action violate any policy rules?
   +-- Credential Gate: Does the agent have scoped access for this?
   +-- Risk Gate: Is this destructive/irreversible? Require approval?
   +-- Journal: Log the proposal and decision
   |
   | if approved
   v
Execution (API call, file write, message send, etc.)
   |
   | result
   v
Orket Nervous System
   +-- Validate result against expected schema
   +-- Detect data leakage in response
   +-- Update journal
   |
   v
Agent receives sanitized result
```

## Relation to Existing Projects

The games and SDK extensions are not separate from this direction. They are **training exercises for the nervous system:**

- **TextMystery**: Gates NPC responses. Trains: output validation, leak detection, confession detection.
- **Lie Detector**: Enforces truth policies. Trains: deception detection, behavioral pattern recognition.
- **RuleSim**: Validates workloads against rule sets. Trains: schema enforcement, invariant checking.
- **Audio SDK**: Typed capabilities with preflight checks. Trains: capability protocol, scoped access.
- **Broker/Fabric**: Multi-stream arbitration. Trains: proposal intake, drift suppression, PII firewall.

Each one exercises a different gate. The nervous system is the sum of all these gates applied to real agent execution.

## The SDK + Extension Model

Orket core is the nervous system (gates, journal, state, policies). Everything else is an extension:

- **Agent adapters** are extensions (OpenClaw adapter, Claude adapter, MCP adapter)
- **Tool integrations** are extensions (email, filesystem, messaging, API calls)
- **Validation rules** are extensions (PII detection, credential scoping, drift formulas)
- **Games** are extensions (TextMystery, Lie Detector, RuleSim)

The SDK defines how extensions register capabilities, declare required permissions, and pass through preflight checks. This is already how `orket_extension_sdk` works for audio, LLM, and TUI capabilities.

## First User

The first user is the author. The motivating use case: "I want to run OpenClaw on my machine without being afraid it will delete my emails, leak my credentials, or act on my behalf without asking."

If Orket can make that feel safe, the architecture works. If it can't, it doesn't matter how many features it has.

## Open Questions

- What does the agent adapter protocol look like concretely? (MCP-compatible? Custom?)
- How granular should credential scoping be? (Per-action? Per-session? Per-agent?)
- What's the right approval UX? (CLI prompt? TUI panel? Notification?)
- How do you validate extensions without becoming a gatekeeper?
- What's the minimum viable nervous system that lets you safely run OpenClaw?

## Locked v1 Plan

The first implementation slice is now locked in `docs/projects/future/NervousSystem/IMPLEMENTATION_PLAN.md`.

Live verification evidence for the locked v1 slice is recorded in:

- `docs/projects/future/NervousSystem/LIVE_VERIFICATION.md`
- `benchmarks/results/nervous_system/nervous_system_live_evidence.json`

Scope for that locked slice:

- Action path only (`action.tool_call` proposals)
- Deterministic admission and commit
- Approval queue/API with CLI fallback
- Scoped per-action credential tokens
- Append-only governance ledger
- OpenClaw JSONL subprocess live verification

## Non-Goals

- Building a better agent framework (brain is not our job)
- Competing with OpenClaw on features (muscle is not our job)
- Achieving perfect safety (nervous systems have failure modes too)
- Selling security as a product (this is a workshop, not a firewall)

## This Document

Captures direction only. Not a commitment to implementation. Revisit when the security fixes from the v0.4.5 roadmap are complete — you can't build a safety layer on an insecure foundation.
