# RuntimeOS Turn Executor Seam Extraction And Facade Reduction Implementation Plan
Last updated: 2026-04-01
Status: Completed archived implementation authority
Owner: Orket Core
Lane type: RuntimeOS / turn-executor seam extraction and facade reduction

Paired requirements authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/TURN_EXECUTOR_SEAM_EXTRACTION_FACADE_REDUCTION_REQUIREMENTS.md`

Closeout authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/CLOSEOUT.md`

Historical staging source:
1. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

Related historical narrowing:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`

## Authority posture

This document is the archived implementation authority for the completed RuntimeOS `runtime seam extraction and facade reduction` lane.

The paired archived requirements companion remains `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/TURN_EXECUTOR_SEAM_EXTRACTION_FACADE_REDUCTION_REQUIREMENTS.md`.
This archived record preserves the bounded seam-family logic used to close the lane.
It no longer acts as active roadmap authority.

## Source authorities

This archived plan is bounded by:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/TURN_EXECUTOR_SEAM_EXTRACTION_FACADE_REDUCTION_REQUIREMENTS.md`
2. `docs/ROADMAP.md`
3. `docs/ARCHITECTURE.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Purpose

Reduce change blast radius on the `TurnExecutor` hot path by making its execution surface more explicit and by reducing facade ambiguity on that seam.

This lane existed to deliver:
1. one selected seam family centered on `TurnExecutor`
2. one explicit composition story for the touched collaborators
3. one concrete reduction of `__getattr__` delegation on that seam
4. one truthful behavior-parity proof set for the touched seam family

## Selected bounded scope

This completed lane was limited to:
1. `orket/application/workflows/turn_executor.py`
2. `orket/application/workflows/turn_executor_model_flow.py`
3. `orket/application/workflows/turn_executor_ops.py`
4. `orket/application/workflows/turn_executor_control_plane.py`
5. `orket/application/workflows/turn_executor_control_plane_evidence.py`
6. `orket/application/workflows/turn_failure_traces.py`
7. removal of `TurnExecutor.__getattr__`
8. bounded parity-preserving extraction or decomposition on that seam family only

## Non-goals

This lane did not:
1. restructure the entire orchestration layer
2. perform repo-wide compatibility cleanup
3. reopen Graphs work
4. rename directories for cosmetic reasons

## Final outcome

This lane closed successfully because:
1. the selected seam family stayed bounded to `TurnExecutor` and its directly coupled helper modules
2. the hot-path helper modules now use explicit collaborators such as `artifact_writer`, `response_parser`, `contract_validator`, `corrective_prompt_builder`, and `tool_dispatcher`
3. `TurnExecutor.__getattr__` was removed instead of narrowed into another hidden facade
4. parity proof passed on the touched application and control-plane seam family
5. the roadmap and future-packet authority now reflect that the lane is archived rather than active

## Current proof baseline used for closeout

Executed proof for the completed seam family:
1. `python -m pytest -q tests/application/test_turn_executor_delegate_surface.py tests/application/test_turn_executor_context.py tests/application/test_turn_executor_replay.py tests/application/test_turn_executor_runtime_context_bridge.py tests/application/test_turn_executor_middleware.py`
2. `python -m pytest -q tests/integration/test_turn_executor_control_plane.py tests/integration/test_turn_executor_control_plane_evidence.py tests/integration/test_turn_tool_control_plane_closeout.py`
3. `python scripts/governance/check_docs_project_hygiene.py`

## Lane completion gate

This lane was complete only when:
1. the `TurnExecutor` seam family was the only selected seam family
2. composition was more explicit on that seam
3. `__getattr__` delegation was reduced or removed on that seam truthfully
4. parity proof existed for the touched seam family
5. same-change authority docs remained aligned
