# Explicit execution-turn time

Owner: Orket Core
Date: 2026-09-18
Effective version: 0.6.24 (patch checkpoint; whole architectural-truth lane open)
Affected contracts: `ExecutionTurn`, `Agent.run`, completed-turn replay and pre-effect resume.

## Delta

`ExecutionTurn` previously supplied the current host time when its caller omitted
`timestamp`. Reconstructing a stored turn consequently invented a new response
time on each read. Core values now require a keyword `timestamp`: a supplied
`datetime`, or explicit `None` when that observation is unavailable. Core does not
read the clock or substitute a sentinel date. Identical explicit inputs yield
identical turn values.

`Agent` accepts a `turn_clock` callable, defaulting to the UTC host-clock adapter.
Each invocation captures that callable before awaiting configuration/provider work
and samples it when constructing the returned response. Replacing the agent's
clock during an admitted invocation affects subsequent invocations only.
The existing application `ResponseParser` already supplies an explicit timestamp;
its direct clock observation remains separate D2 work.

Completed-turn replay and pre-effect checkpoint resume supply `None`. Their
existing snapshots do not record original response timestamps. Checkpoint creation,
publication, lease and replay-observation times are distinct facts and cannot stand
in for that absent value. No stored checkpoint, hash, schema or journal is rewritten.
This change does not add full response reconstruction or durable response-time capture.

## Migration

There is no implicit-clock compatibility shim. Embedded callers must pass
`timestamp=observed_time` or `timestamp=None`; timestamps are keyword-only.
Migrated test/script constructors use explicit absence where time is not observed. Consumers must handle `None`
on reconstructed turns. Existing snapshots remain usable without migration;
their missing observation stays missing. The core/legacy domain import identities
are unchanged.

Source and installed regression gates cover constructor admission, explicit-value
parity, live application replay with real file and SQLite effects, captured Agent
clock selection, and existing pre-effect resume. Controlled response fixtures are
not live provider proof. The canonical plan records exact candidate inputs,
observations and remaining verification obligations.

## Rollback

If downstream callers fail to migrate, revert the versioned change and its caller
updates together, then rerun the affected source/installed envelope. No persistent
data conversion or recovery is needed. Reverting restores the known invented-time
behavior and must not be described as deterministic core conformance.

## Remaining scope

This closes only the implicit `ExecutionTurn` clock. Other core clocks, manifest
reads, schema identity defaults, application clocks, asynchronous reachability and
adapter classification remain C/D obligations. No provider, sandbox containment,
host-clock repair, performance or whole-lane acceptance follows from this checkpoint.
