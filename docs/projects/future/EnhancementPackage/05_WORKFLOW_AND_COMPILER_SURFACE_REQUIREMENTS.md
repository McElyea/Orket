# Workflow and Compiler Surface Requirements

Last updated: 2026-04-02
Status: Draft staged future-lane requirements
Authority status: Staging only. Not current roadmap authority. Not current execution authority until explicitly adopted.
Owner: Orket Core
Lane family: Workflow definition and composition

## Purpose

Define a bounded workflow and compiler surface for Orket without allowing composition abstractions to outrun workload authority or control-plane truth.

## Current shipped baseline

The repo already has current workload-authority, session-boundary, supervision, and control-plane truth surfaces that any future workflow layer must consume.
This doc does not claim that Orket needs a second planner, a second control plane, or invented lineage to support composition.

## Future delta proposed by this doc

This doc proposes a bounded declarative workflow and composition layer over existing runtime authority.
Candidate deltas include:
1. named orchestration patterns,
2. declarative workload specifications,
3. validation before admission,
4. workflow-as-tool composition,
5. explicit durable parent-child lineage where composition is admitted,
6. bounded recursion and cycle rules.

## What this doc does not reopen

This doc does not reopen:
1. a shadow planner,
2. a second control plane,
3. graph-family inventions that outrun durable lineage truth,
4. unconstrained multi-agent chatter as default architecture.

## Usage boundary

This doc should be read as a workflow-definition and validation candidate.

It should not be read as:
1. permission to build a broad workflow DSL before core seams are colder,
2. permission to let declarative workflow convenience become hidden authority,
3. a mandate to mimic external frameworks wholesale.

## In scope

1. named orchestration patterns,
2. declarative workload specifications,
3. validation before admission,
4. workflow-as-tool composition,
5. workflow-as-agent or workflow-as-workload composition where explicitly admitted,
6. explicit parent-child lineage,
7. bounded recursion and cycle rules.

## Out of scope

1. vague agent theater,
2. unconstrained multi-agent chatter loops,
3. hidden in-memory orchestration truth,
4. broad marketplace concerns,
5. composition graphs that invent lineage not present in runtime truth.

## Core requirements

### WC-01. Existing workload authority remains the baseline
Any adoption of this doc must anchor to the canonical workload-authority and control-plane truth that already exist.
The workflow layer must consume that authority rather than replacing it.

### WC-02. Lowest-complexity doctrine
The workflow surface must prefer the lowest admitted orchestration shape that satisfies the task.

### WC-03. Named pattern vocabulary
The runtime must expose a bounded named pattern vocabulary for admitted workflow shapes.
Examples may include:
1. direct action,
2. sequential pipeline,
3. orchestrator-worker,
4. maker-checker,
5. handoff,
6. approval-gated execution,
7. scheduler-triggered run,
8. event-triggered run.

### WC-04. Declarative specs are validated before admission
Supported declarative workflow specs must undergo validation before admission.

### WC-05. Validation covers structure and policy-relevant shape
Validation must cover at minimum:
1. graph connectivity where applicable,
2. binding validity,
3. invalid edges,
4. recursion or cycle rules,
5. approval-policy-relevant declarations,
6. parent-child composition legality.

### WC-06. Workflow composition is explicit
Workflow-as-tool or nested workflow composition must be explicit and attributable.

### WC-07. Parent-child lineage derives from durable control-plane truth
Where composition is admitted, parent-child lineage must be durable and operator-inspectable.
That lineage must derive from durable workload and control-plane truth rather than convenience-layer inference.

### WC-08. Composition must not bypass policy
Nested workflow or workflow-as-tool execution must remain subject to the same host policy, namespace, and approval rules as other governed execution.

### WC-09. No convenience abstraction as shadow planner
A convenience workflow layer must not become a hidden planner or control plane that outruns documented runtime authority.

### WC-10. Time-bounded iterative shapes only
Any admitted iterative pattern must carry explicit bounds, budget posture, or escalation behavior.

### WC-11. Compile-time and runtime truth must align without collapsing
Validation success must not claim runtime success.
Compile-time admissibility and runtime execution truth must remain distinct.

## Acceptance boundary

This lane is acceptable only when:
1. a bounded named pattern vocabulary exists,
2. declarative workflow validation occurs before admission,
3. composition is explicit and policy-bounded,
4. parent-child lineage is durable and control-plane-anchored where admitted,
5. iterative shapes are bounded,
6. compile-time and runtime truth remain separate,
7. the workflow layer does not become shadow authority.

## Proof requirements

Structural proof:
1. no declarative workflow path bypasses validation,
2. no composed workflow path bypasses host policy,
3. no parent-child composition is admitted without durable lineage,
4. no convenience abstraction becomes undocumented authority,
5. no lineage claim is invented beyond durable source truth.

Integration proof:
1. a supported workflow spec validates successfully,
2. invalid shape or policy violations fail closed,
3. a composed workflow invocation remains attributable,
4. iterative bounds are enforced on an admitted looping shape.

Live proof where real surfaces are involved:
1. one supported pattern executes through the admitted workflow path,
2. invalid workflow structure is rejected pre-admission,
3. operator inspection shows lineage and bounded execution posture.

## Ordering note

This doc is fifth in the packet because workflow and compiler work should follow colder supervision, continuity, and selected convergence seams.
