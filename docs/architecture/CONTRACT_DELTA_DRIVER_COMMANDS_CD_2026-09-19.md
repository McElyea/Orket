# Driver command ownership and compiler publication

Owner: Orket Core. Date: 2026-09-19. Effective version: 0.6.28.
Status: Active contract; full architectural-truth acceptance remains open.

## Delta

Driver operator commands enter application `DriverCommandService`. Resource
commands and model-proposed structural writes use `DriverResourceStore` in a
retained worker. Their shared model-root native lock covers read, mutation,
verified file publication and structural event publication. A competing writer
receives `DRIVER_RESOURCE_UNCERTAIN:owner_busy`; it must inspect the completed
first operation before retrying. Existing legacy `cards` normalization and model
acceptance-definition admission remain in force. Selected roots and nested model
proposals are captured before awaiting. Resource paths must remain within the
selected model root. Department fallback reports the department actually used.

Driver commands and ToolBox use application `ReforgerService` for the existing
textmystery compiler tools. It captures arguments and explicit absolute roots,
owns route/compiler selection, and retains its worker through repeated
cancellation or timeout. Each workspace has one cooperating native compiler
owner. ToolBox also retains its existing card-completion mutation guard; that
guard already drained compiler workers before this change.
ToolBox binds invocation-relative workspace/reference locations at construction;
later working-directory changes cannot retarget its compiler commands.

Compilation retains copies of the route's four declared input files and the
selected scenario pack under its artifact root before invoking the compiler.
`run/artifacts/inputs_manifest.json` describes these admitted route inputs, not
every unrelated file in the project. `admitted-scenario-pack.json` retains the
selected pack. Input snapshots and output manifests no longer incorporate prior
compiler outputs or a live native lock. Inspect remains an observation of the
selected source files; it does not reserve them against external modification.

Output directories must be strict workspace children and cannot overlap the
compiler artifact namespace, selected content subtree or scenario pack. `.` is
rejected with `PATCH_OUT_OF_SURFACE`. Failed compiler results do not replace the
published output. Successful compilation verifies the materialized file set and
every published byte before returning `ok=true`. Report files use verified
publication too. The driver prints the actual `materialized_output_dir` instead
of nonexistent `output_paths` and `suite_ready` run fields.

## Migration

The synchronous `orket.adapters.tools.families.reforger_tools.ReforgerTools`
class and its family-package export are retired without an alias. Direct callers
construct `orket.application.services.reforger_service.ReforgerService` with
absolute workspace/reference roots and await `inspect` or `run`. The existing
`OrketDriver(reforger_tools=...)` injection accepts this asynchronous service.
`DriverCliMixin` and `orket.driver_support_cli` are retired; application callers
use `DriverCommandService`, supplying an absolute model root for resource work.
Tool names and ordinary command syntax remain unchanged. Existing callers using
the workspace root as compiler output must select a dedicated child directory.

Native ownership files live beside the model/workspace roots in
`<model-root>.driver-locks` and `<workspace-root>.reforger-locks`. Preserve their
identities while an owner is active; replacing or deleting them does not grant
permission for concurrent execution.

## Proof and limits

Retained before-repair flows demonstrate workspace-root output admission,
event-loop blocking in direct driver inspection, and department traversal that
wrote an epic outside the model root. Integration checks use actual compiler
files, native locks and file publication. Controlled holds require responsiveness
within 0.5 seconds and settlement within 3 seconds of release. Cancellation,
timeout, contention, captured proposals, output overlap, stable input digests and
injected publication corruption/refusal have explicit checks. The canonical plan
records source and native package results. This is deterministic compiler/file
proof, not live model portability or completion acceptance.

Native locks coordinate these admitted callers; they do not sandbox hostile
processes or make arbitrary external edits safe. Existing driver team assignment,
bootstrap and model-conversation flows are outside this lock/worker contract.
Resource files and structural logs remain separate effects. Epic and parent-rock
updates are separate verified writes; failure can leave a partial transition.
Compiler output replacement is also not a directory transaction. A publication
failure may leave partial output, and callers must inspect retained artifacts
before retrying. No crash recovery, hard deadline for hung file/compile workers,
universal driver shutdown guarantee or whole C/D conformance is claimed.

## Rollback

Drain command and compiler owners before a versioned rollback. Restore callers,
service contracts and storage behavior together. Preserve existing model files,
compiler evidence and ownership files. Do not restore workspace-root replacement
or department escape as admitted success merely to maintain old expectations.

Version decision: patch checkpoint with breaking embedding/output semantics.
Compatibility status: breaking. Affected audience: all. Migration: required.
