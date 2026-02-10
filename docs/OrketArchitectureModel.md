# The Orket Architecture Model (Unified)

**Audience:** Orket developers and contributors

**Purpose:** Define a single architectural model that governs:

* how *any* system is built using Orket principles
* how *Orket itself* is designed

The same rules apply at every level.

---

## Fractal Decomposition and Natural Resolution

This architecture is **fractal**, but not infinite.

**Fractal (practical meaning):**
The same rules for separating stability and volatility apply repeatedly *until no meaningful decisions remain*.

Decomposition stops naturally when:

* remaining code is mechanical
* behavior is fully determined
* change is unlikely or trivial

At that point, what remains is:

* boilerplate
* configuration
* wiring

No further Decision Nodes are required.

---

### How Resolution Occurs

At each level:

* volatile behavior is isolated into Decision Nodes
* stable structure remains in the parent

As decisions are refined, volatility narrows.

Eventually:

* decisions collapse into parameters
* parameters collapse into configuration
* configuration collapses into static code

This is the termination condition of the fractal.

---

### How the Architecture Shows Process, Domain, and Structure

The system organizes itself visibly:

* **Process** lives in Decision Nodes (what to do)
* **Domain** lives in contracts and vocabulary (what things mean)
* **Architecture** lives in stable layers (how parts connect)

These concerns never mix.

Zooming in reveals the same separation until resolution.

---

## Delineation of Application

### When the Model Is Applied to *Any System*

You are designing:

* applications
* agents
* workflows
* plugins
* decision logic

In this mode:

* Orket is the *platform*
* Decision Nodes are *user-defined*

---

### Application Boundary: Orket Itself

This mode applies when designing Orket’s internal behavior.

Examples:

* planning logic
* routing decisions
* evaluation strategy
* agent coordination

In this boundary:

* Orket is the system under design
* each internal behavior is a Decision Node

These nodes follow the same rules as any other Decision Node.

---

## Source Lineage

This model is derived from iDesign concepts:

* decomposition by rate of change
* stable abstractions
* dependency direction

Orket defines and enforces the operational form of these ideas.

---

## Core Axioms

1. Stability is architectural.
2. Volatility is behavioral.
3. Volatile code depends on stable contracts.
4. Every decision is a boundary.
5. Boundaries repeat recursively.

---

## Decision Nodes (Volatile Nodes)

A **Decision Node** is any unit whose behavior is expected to change.

Examples:

* planning
* routing
* prompting
* evaluation
* model selection

Properties:

* owns decisions
* isolated behind contracts
* replaceable
* testable

All intelligence lives here.

---

## Fractal Decomposition

Decomposition by volatility is **recursive**:

* Stable systems contain Decision Nodes
* Each Decision Node may contain smaller Decision Nodes
* This continues until remaining logic is trivial

> Design nodes all the way down.

---

## Node-as-Project Model

Each Decision Node is treated as a **project during development**:

* independent iteration
* parallel experimentation
* discardable output

Integration occurs only through contracts.

---

## Plugins (Implementation Strategy)

A Decision Node **may** be implemented as a plugin.

* default strategy (~95%)
* not a requirement
* edge cases exist (~1/20)

Do not optimize for edge cases.

---

## Utilities Classification

Utilities are classified by **volatility**, not convenience.

### Stable Utilities

* logging
* metrics
* tracing
* configuration
* serialization

### Volatile Utilities

* prompt builders
* scoring functions
* ranking heuristics

If it changes often, it is a Decision Node.

---

## Layering Rules (Clean Boundaries)

* hard layer boundaries
* dependencies point inward
* frameworks are outermost

Language is incidental (Python is not the architecture).

---

## Anti-Patterns (Common in AI Frameworks)

Avoid:

* monolithic planners
* shared global prompt state
* implicit agent coupling
* behavior hidden in config-only systems

These collapse volatility boundaries.

---

## Orket Execution Model (Agents)

Orket executes **local models** as first‑class runtime participants.

Terminology:

* **Orket Agent**: a runtime participant backed by a local model.
* **Member**: an Orket Agent assigned a role within a workflow.
* **Decision Node**: the boundary that an Orket Agent implements.

Rules:

* Decision Nodes define the work an Orket Agent performs.
* Orket Agents interact only through stable contracts.
* Volatile behavior lives inside the Decision Node owned by the Agent.
* Replace an Agent by replacing its Decision Node implementation.

This model avoids shared global state and implicit coupling.

---

## Prescribed Development Philosophy

This document is the **development guide** for Orket and for systems built using Orket.

Prescriptions:

* isolate volatility aggressively
* model decisions explicitly
* bind behavior to Decision Nodes
* execute decisions via Orket Agents backed by local models
* prefer replacement over mutation
* decompose recursively until behavior stabilizes
* stop when only boilerplate and configuration remain

These choices are intentional.

They define how Orket is built and how Orket-based systems are built.

Deviation requires explicit justification.
