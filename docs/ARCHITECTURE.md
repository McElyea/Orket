# Orket Architecture

This is the canonical architecture document for Orket.

## Core Idea
- Role contracts are stable.
- Models are unique specialists with different strengths and failure modes.
- Reliability comes from capability-aware model assignment and mechanical governance.
- Volatile behavior is isolated behind explicit decision seams.

## Architectural Model
Orket applies the same decomposition rule recursively:
1. Stable structure stays in runtime layers.
2. Volatile decisions move to Decision Nodes behind contracts.
3. Decomposition stops when remaining logic is mechanical and low-change.

This applies both to systems built with Orket and to Orket itself.

## Runtime Layers
1. `orket/core`: stable domain rules, contracts, and policies.
2. `orket/application`: orchestration workflows and services.
3. `orket/adapters`: integration seams (LLM, storage, VCS, tools).
4. `orket/interfaces`: API/CLI edges.
5. `orket/decision_nodes`: volatile policy/strategy implementations selected through registry contracts.

## Dependency Direction
Allowed:
1. `interfaces -> application/core`
2. `application -> core/adapters/decision_nodes`
3. `adapters -> core`
4. `decision_nodes -> contracts + core vocabulary`

Disallowed:
1. `core -> application/interfaces/adapters`
2. `adapters -> application/interfaces/decision_nodes`
3. `decision_nodes -> interfaces`

## Decision Node Responsibility
Decision Nodes own behavior that changes often, including:
1. planning
2. routing
3. prompt/model strategy
4. evaluation and stage-gate policy
5. tool strategy

Stable runtime flow remains in orchestrators and services.

## Durable vs Volatile Local State
1. Durable runtime state now defaults under `.orket/durable/`.
2. Workspace execution artifacts remain under `workspace/` and can be sanitized per epic.
3. Key durable defaults:
   - runtime DB: `.orket/durable/db/orket_persistence.db`
   - webhook DB: `.orket/durable/db/webhook.db`
   - live-loop DB: `.orket/durable/observability/live_acceptance_loop.db`
   - user settings: `.orket/durable/config/user_settings.json`
   - gitea export cache/staging: `.orket/durable/gitea_artifacts/`

## Notes on Gitea Artifact Export
`.orket/durable/gitea_artifacts/` is local staging/cache for export payloads and a local git mirror used by the exporter.  
It is not the Gitea server's own storage location.
