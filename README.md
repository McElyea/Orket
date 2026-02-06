# Orket

Orket is a local‑first, multi‑agent orchestration engine for long‑running engineering sessions.  
It coordinates a team of AI agents through a deterministic Flow and exposes a Conductor that can steer the session in real time.

Orket emphasizes transparency, traceability, and control. Every step is logged and auditable. It is designed for engineering work where structure and oversight matter.

---

## Why Orket

Modern AI tools often operate as opaque, single‑shot systems. They produce results but offer limited visibility into how those results were created or how to correct drift.

Orket addresses those gaps:

- **Local execution** — run models on your machine or local cluster.  
- **Deterministic orchestration** — reproducible, step‑by‑step runs.  
- **Role‑based agents** — explicit responsibilities for Architect, Coder, Reviewer, and others.  
- **Session steering** — Conductor can enable/disable roles, patch prompts, and skip steps.  
- **Long‑running sessions** — designed for iterative, multi‑cycle work.  
- **Full traceability** — structured event logs and transcripts.

---

## What Orket is not

- Not a chatbot.  
- Not a cloud service.  
- Not a black box.  
- Not a replacement for engineering judgment.  
- Not an autonomous agent that acts without human oversight.

---

## Core concepts

- **Flow** — orchestration structure and references to Band, Venue, Score.  
- **Band** — role definitions and prompts.  
- **Venue** — model backend configuration.  
- **Score** — ordered steps the Orchestrator executes.  
- **Conductor** — session governor that observes and adjusts between steps.  
- **Orchestrator** — runtime that loads configuration, runs steps, and records events.  
- **Workspace** — files and artifacts produced by a run.  
- **Event Stream** — structured events for UI and auditing.

---

## Small flow diagram

    ┌──────────┐     ┌────────┐     ┌──────────┐
    │ Architect│ →   │ Coder  │ →   │ Reviewer │
    └──────────┘     └────────┘     └──────────┘
            ↑             ↑               ↑
            └────────── Conductor ───────┘

The Conductor sits above the loop and can adjust prompts, skip roles, or change behavior between steps.

---

## Quickstart

1. Install dependencies:

    pip install -r requirements.txt

2. Run a Flow:

    python main.py --flow standard --task examples/hello/task.json

3. Enable interactive Conductor controls:

    python main.py --interactive-conductor

You will be prompted to adjust roles or patch prompts between steps.

---

## Example interaction

A typical run produces a structured transcript and event log. Events include `step_start`, `step_end`, `step_skipped`, and workspace writes. The transcript records each agent's summary for later review.

---

## Documentation

- `docs/ARCHITECTURE.md` — system design, diagrams, and sequence interactions  
- `docs/PROJECT.md` — roadmap and milestones  
- `docs/SECURITY.md` — local execution and safety notes  
- `CONTRIBUTING.md` — contributor guidelines
