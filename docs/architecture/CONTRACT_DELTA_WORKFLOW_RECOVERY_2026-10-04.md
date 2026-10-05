# Scoped workflow recovery and CLI verdict separation

## Summary
- Owner: Orket Core
- Date: 2026-10-04
- Affected contracts: exact UTF-8 file writes, card artifact review inputs, stored challenge admission,
  local prompt fence validation, benchmark CLI correctness/repeatability reporting,
  and streaming scenario receive ownership.

## Delta

Windows text writers previously translated LF to CRLF and could duplicate CR in
submitted CRLF. Standard async file tools and the handle-bound outward writer now
disable newline translation and preserve the exact serialized UTF-8 text. Reads
retain their existing text-mode behavior. Exact artifact acceptance continues to
compare captured bytes without normalization; historical files are not rewritten.
The challenge's first live attempt demonstrated this failure despite matching
displayed text. Ten native regression cases reproduced it before repair.

Artifact final review previously acquired app-default design and runtime-report
paths merely because the builder seat was a reviewer. It now follows the declared
artifact review paths. Application final review retains its existing defaults.
The prepared QA note no longer requests a write from a role with no write tool.

The twelve-card workflow-runtime challenge previously declared support checks but
no completion acceptance. Its requirements, design and fixture cards now declare
exact artifact checks. Later cards use the bounded Python CLI acceptance family
to execute the existing RuntimeVerifier commands and assertions through a prepared
CLI adapter. The adapter retains inner command results on stderr in the outer
acceptance package. This is a scoped authored migration, not implicit acceptance
for undeclared cards. Prepared challenge projects require the core development
environment, including pytest for the original generated-test commands.

The prepared challenge declares `ORKET_CONTEXT_WINDOW=1` for its runtime process.
Required file context and acceptance remain intact; the bounded role history
avoids repeating earlier generated source within the selected server's existing
8K context. Full transcripts remain retained. The recipe records and prints the
setting without mutating the invoking shell or operator server.

Local anti-meta validation now shares the response parser's lexical fence check.
Markdown fences inside JSON string values are artifact data; fences surrounding
the response remain rejected. A live CWR-12 README write exposed the former false
positive. No other thinking, envelope or payload-only rule changes.

CLI benchmark correctness and observed replay equality are now separate checks.
All declared examples are observed twice even when an earlier answer is wrong.
A repeatable wrong answer still fails the task. Different outputs fail replay;
unobserved cases explicitly report incomplete observation. Two matching executions
per case do not establish general determinism. Old reports remain immutable.

Streaming scenario polling now retains one pending receive across timeouts and
settles it after socket closure. The previous harness abandoned a reader after
each polling deadline, allowing it to consume and lose a later commit event.
The first 1,000-loop attempt exposed this at loop 122 despite a retained native
commit. Native reproduction holds publication across multiple poll deadlines;
quiet-socket and transport-failure controls verify settlement. Scenario budgets,
assertions and historical failed evidence are unchanged.

## Migration and validation

Use the selected development environment for installation and execution. Windows
setup now documents project `.venv` creation and per-shell activation in the root
README, with the same canonical editable SDK/core install. The observed global
core/SDK 0.7.1 installation is distinct from the tested source environment; it is
preserved. The project environment requires an activated-shell workflow proof.

Prepare a new directory with `examples/stored_workflows/prepare.py` and
`--workflow challenge_workflow_runtime`; do not copy the migrated epic into an
old workspace without its prepared verifier. Keep the selected operator model
and provider. Existing failed runs remain historical evidence.

Validation requires native LF/CRLF/mixed/JSON writes through the standard and
approved bound paths, existing file ownership/cancellation controls,
native positive/negative acceptance controls, CLI replay
controls, and fresh Windows QA/challenge flow attempts with actual completion
receipts. The source-bound suite baseline remains on 0.7.6; later proof records
identify the changed candidate. Live verdicts and limitations belong in the
0.7.7 proof report, not in this contract delta.

## Rollback

If a new definition rejects valid admitted work, retain the failed package and
repair the authored definition in a new version. Do not change a historical
receipt, weaken the completion gate, or reset published tags. A runtime rollback
requires a new versioned correction and fresh affected-path proof.

## Versioning

Core patch 0.7.7. Operator migration is required for the changed challenge recipe;
SDK and accepted public release artifacts are unchanged.
