# Orket Contributor Mental Model

This guide is the shortest reliable path to understand how a user request becomes work completion.

## 1) Entry Point: Driver

`orket/driver.py` owns CLI-style intent handling.

- Reads user input.
- Decides whether the input is conversational or structural (`/create`, `/run`, `/reforge`, etc.).
- Resolves organization/model context.
- Delegates execution to runtime services.

Think of the Driver as the command router and front-door translator.

## 2) Runtime Coordinator: ExecutionPipeline

`orket/runtime/execution_pipeline.py` is the top-level runtime orchestrator for assets.

- Loads and validates organization assets (epics/rocks/issues).
- Starts/finishes session records.
- Chooses run mode (epic, rock, card, optional Gitea state loop).
- Calls the workflow orchestrator to execute actual issue turns.

Think of ExecutionPipeline as the session-level transaction boundary.

## 3) Workflow Engine: Orchestrator

`orket/application/workflows/orchestrator.py` executes the issue backlog.

- Builds candidate work based on state/dependencies.
- Routes each turn to the right seat/role.
- Applies policy nodes (planner/router/evaluator/guard/runtime verification).
- Manages status transitions and retry/replan behavior.

Think of Orchestrator as the per-issue control loop.

## 4) Per-Turn Executor: TurnExecutor

`orket/application/workflows/turn_executor.py` runs one model/tool turn.

- Assembles prompt/context/toolbox.
- Invokes model provider + tool calls.
- Produces structured turn result (content, actions, failures, telemetry).
- Returns deterministic outcome to Orchestrator.

Think of TurnExecutor as the atomic work unit.

## 5) Data and State Flow

- Persistent card/session/snapshot state is read/written through async repositories.
- Runtime/global process state (tasks, websockets, interventions) is managed via `orket/state.py`.
- Observability is emitted through `log_event` and session/run artifacts.

## 6) Fast Trace: Request to Completion

1. Driver receives request.
2. Driver resolves target workload/asset.
3. ExecutionPipeline initializes session and run metadata.
4. Orchestrator loops through ready issues.
5. TurnExecutor executes each turn.
6. Orchestrator updates issue states/retries/escalations.
7. ExecutionPipeline finalizes run status, ledger, and artifacts.

## 7) Practical Debug Order

When behavior is wrong, inspect in this order:

1. `driver.py` (intent routing)
2. `execution_pipeline.py` (session/run wiring)
3. `orchestrator.py` (state transitions and loop decisions)
4. `turn_executor.py` (model/tool behavior)
5. repositories + `state.py` (data consistency)
