# Orket Architecture

This document describes how Orket works internally: the conceptual model, orchestration flow, and core components.

## Conceptual Model

Orket uses a musical metaphor to structure multi‑agent workflows:

Orket (conductor)  
→ Venue (environment)  
→ Band (performers)  
→ Score (composition)  
→ Prelude (optional warm‑up)  
→ Session (execution)

## Venue

A Venue is a reusable environment configuration. It includes:

- band name  
- score name  
- tempo  
- filesystem permissions  
- write policy  
- environment defaults  

The Venue is the bridge between high‑level intent and concrete configuration.

## Band

A Band defines the performers:

- role names  
- system prompts  
- allowed tools  

The Band is the single source of truth for roles.  
It does not define sequencing or dependencies.

## Score

A Score defines how the Band performs:

- which roles participate  
- dependencies between roles  
- sequencing  
- completion rules  

The Score references roles defined in the Band.  
It never defines prompts or tools.

## Prelude

The Prelude is an optional pre‑Session stage.  
Typically, the architect reflects on the task before orchestration begins.

Input: architect prompt + user task  
Output: a single reflective message  
Behavior: one LLM call, logged into the Session

## Session

A Session is a structured record of a single run:

- unique ID  
- venue name  
- task  
- ordered messages  
- tool calls  
- timestamps  

Sessions are deterministic and auditable.

## Agent Lifecycle

Each agent receives:

- the full message history  
- its system prompt  
- the current round number  

Agents may:

- produce content  
- request tools  
- signal completion  

## Tool Dispatcher

The dispatcher enforces:

- Band‑level tool permissions  
- FilesystemPolicy read/write rules  
- path validation  
- write receipts  

All tool calls flow through the dispatcher.

## FilesystemPolicy

The filesystem model is declarative:

- reference spaces  
- workspace  
- domain  
- write policy  

The policy determines:

- which paths can be read  
- which paths can be written  
- which paths are forbidden  

## Orchestration Loop

1. Load Venue  
2. Load Band  
3. Load Score  
4. Start Session  
5. Optional Prelude  
6. Determine ready roles  
7. Run agents  
8. Handle tool calls  
9. Update Session  
10. Repeat until completion  

## Determinism

Orket is designed for:

- reproducibility  
- explicit configuration  
- traceability  
- auditability  
