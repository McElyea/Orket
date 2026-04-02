# RuntimeOS Turn Executor Seam Extraction And Facade Reduction Requirements
Last updated: 2026-04-01
Status: Completed archived requirements authority
Owner: Orket Core
Lane type: RuntimeOS / turn-executor seam extraction and facade reduction requirements

Paired implementation authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/TURN_EXECUTOR_SEAM_EXTRACTION_FACADE_REDUCTION_IMPLEMENTATION_PLAN.md`

Closeout authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/CLOSEOUT.md`

Historical staging source:
1. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

Related historical narrowing:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`

## Authority posture

This document is the archived requirements companion for the completed RuntimeOS `runtime seam extraction and facade reduction` lane.

It records the bounded `TurnExecutor` seam family that was selected and completed.
It no longer acts as active roadmap authority and does not reopen broader orchestration modularization, cold-down work, or Graphs.

## Source authorities

This archived requirements companion is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`
5. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`

## Purpose

Reduce change blast radius on the hottest turn-execution seam without claiming a broader architecture convergence finish.

This lane existed to answer:
1. how the `TurnExecutor` seam becomes more explicit in composition and responsibility
2. how `__getattr__`-style delegation on that seam is reduced or removed truthfully
3. what direct helper files belong in the selected seam family
4. what parity proof is required so seam cleanup does not become structural churn disguised as progress

## Selected bounded scope

This completed lane was limited to:
1. one seam family centered on `orket/application/workflows/turn_executor.py`
2. the exact directly coupled helper workflow files:
   - `orket/application/workflows/turn_executor_model_flow.py`
   - `orket/application/workflows/turn_executor_ops.py`
   - `orket/application/workflows/turn_executor_control_plane.py`
   - `orket/application/workflows/turn_executor_control_plane_evidence.py`
   - `orket/application/workflows/turn_failure_traces.py`
3. explicit composition and responsibility boundaries on `TurnExecutor` and those directly coupled helper workflow files
4. reduction or removal of `TurnExecutor.__getattr__` delegation where it hid the real executor surface
5. bounded extraction or decomposition only where it reduced hot-path ambiguity on the selected seam family
6. one truthful behavior-parity proof set for the touched seam family
7. same-change authority sync where lane-state docs changed

## Non-goals

This lane did not:
1. modularize the repo as an end in itself
2. perform broad directory reshaping
3. do outward identity cleanup that belongs in the later cold-down lane
4. reopen Graphs work
5. redesign unrelated runtime behavior just because the seam was being touched

## Decision lock

The following remained fixed while this lane was active:
1. the selected seam family was `TurnExecutor` plus directly coupled helpers, not the whole orchestration stack
2. parity proof was required for behavior on the touched seam family
3. no new runtime entrypoint or public API was admitted by implication
4. cleanup ideas that belonged primarily to outward identity or wrapper retirement stayed out of scope for this lane
5. cleanup ideas that depended on reopened graph views stayed out of scope for this lane

## Final outcome

This archived requirements companion closed successfully because:
1. the lane stayed bounded to one exact `TurnExecutor` seam family
2. the seam now reads through explicit collaborator access rather than executor-wide magic delegation
3. `TurnExecutor.__getattr__` was removed instead of relocated
4. targeted parity proof exists for the touched seam family

## Requirements completion gate

This requirements companion was complete only when:
1. one exact turn-executor seam family was selected truthfully
2. explicit composition and delegation-reduction goals were written for that family
3. parity proof expectations were explicit
4. same-change update targets remained aligned
