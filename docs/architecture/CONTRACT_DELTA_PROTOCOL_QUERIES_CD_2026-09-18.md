# Protocol query authority and retained lifetime

Owner: Orket Core. Date: 2026-09-18. Effective version: 0.6.23.

## Delta

Before this checkpoint the CLI constructed ledger adapters, while API replay workers could outlive
cancellation and request teardown. Real counterexamples also retain event-loop
blocking during root resolution, an empty campaign reported matched, and an
authenticated parity request reading a session outside its workspace.

Application owns CLI query dispatch and shared query lifetime. Inputs are captured
before awaiting, workers drain before cancellation returns, and campaign session
paths are validated against the selected runs root. HTTP remains workspace-scoped;
explicit CLI file operands retain operator authority. Protocol comparison now
reports insufficient evidence for either empty event sequence and campaigns retain
that result for the baseline. Details: `docs/specs/PROTOCOL_QUERY_LIFETIME.md`.

## Migration and verification

This patch preserves command options and existing payload field types, adding
comparison status/scope/count fields. Empty campaigns no longer pass strict gates.
Escaping run ids are refused; CLI operators use explicit path options when selecting
external input files. No ledger migration, compatibility proxy, new provider or
workload capability is introduced. Retain the five original counterexamples under
`.tmp/c-transport-authority/before/` and record repaired source, installed and actual
CLI/API proof separately in the canonical architectural-truth plan.

## Rollback

Revert implementation and matching authorities together only for a demonstrated
regression. Preserve every original observation. Restoring early teardown, path
escape or empty-evidence success is not acceptable completion. No evidence store
rewrite is part of rollback. Wider C/D/E/CAP and whole-lane acceptance remain open.

## Scoped proof

Final source and Windows/Linux Python 3.11/3.12 installed observations, actual CLI
and TCP API evidence, retained counterexamples and exact artifact hashes are in the
canonical architectural-truth plan's final 0.6.23 subsection. The default router's
ASGI getter regression is covered separately from the explicit-root TCP path.
This is a query-boundary checkpoint; full C/D/E/CAP and release acceptance remain open.
