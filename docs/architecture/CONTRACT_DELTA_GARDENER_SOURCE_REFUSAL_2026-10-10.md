# Gardener source-refusal inspection contract delta

Date: 2026-10-10
Scope: Rev 2 field review, issue #8's run-identity feedback and upstream native-budget diagnostics.

## Previous behavior

Core 0.8.4 returned retained identities for failed CLI results. When the CLI
succeeded but the wrapper subsequently rejected changed source, the failure
envelope lost that identity and its exact inspection command. The durable
snapshot outcome remained inspectable only by finding the run directory.
The upstream integration suite also exposed a wording mismatch: native llama.cpp
input-budget refusal omitted the explicit non-truncation statement already
present in conservative admission. Input refusal itself worked correctly.

## New behavior and authority

The source wrapper captures the CLI run identity before checking report delivery
and source stability. Those checks preserve it in failed envelopes and include
the database-specific inspection command. Failure remains failure, with the
original blocking classification preserved. Pre-admission failures cannot invent
a run identity. A successful CLI result without an identity is refused.

The wrapper does not rewrite an accepted snapshot result after later source
changes. Orket's retained outcome describes the captured commits; Gardener's
outward refusal describes inability to deliver against an unchanged source tree.
No new verifier, terminal authority, retry or state store is introduced.
Native `E_MODEL_INPUT_BUDGET` messages now include `input was not truncated`.
Token counting, limits and refusal timing are unchanged.

Authority: `docs/specs/GARDENER_REPORT_HARNESS.md`. Migration: update the source
wrapper and core; the 0.8.4 trusted report extension/catalog remains compatible.
SDK wire contracts are unchanged. The only core runtime change is that diagnostic
message in `orket/adapters/llm/llama_cpp_render_verification.py`.

## Verification and limits

The native integration regression changes a tracked README during observed
provider HTTP, requires refusal with the run identity, and reopens the retained
SQLite state through CLI inspection and replay. Controlled responses prove
the integration boundary, not actual inference. The Rev 2 live larger-model
check, final regression results and remaining limits are recorded in
`docs/releases/0.8.5/PROOF_REPORT.md`.
