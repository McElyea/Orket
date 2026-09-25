# Gitea Artifact Export Contract

Last updated: 2026-09-25
Status: Active contract
Owner: Orket Core

## Authority and intent

Application epic preparation owns export admission. `GiteaArtifactExporter`
prepares a local content-addressed Git commit, performs the admitted push, and
confirms retained effects through remote reads. Export is disabled by default.
A returned workload or completed model turn does not authorize export success.

`gitea_export_intent.v1` contains the original run ID, non-secret binding, run path,
SHA-1 Git commit, exported subtree and optional base commit. The application
retains this intent with its export-started marker in `epic_preparation.v2` before
repository creation or push. It cannot replace a retained intent. Preparing the
payload/local commit may read remote repository state but does not mutate it.

## Inputs and storage

The exporter freezes these inputs at construction:

- `ORKET_GITEA_ARTIFACT_EXPORT` (default disabled).
- `GITEA_URL`, selected owner (`ORKET_GITEA_ARTIFACT_OWNER`, then
  `GITEA_PRODUCT_OWNER`, then authenticated username), repo, branch and path prefix.
- `ORKET_GITEA_ARTIFACT_PRIVATE`, effective source workspace and resolved cache root.
- `ORKET_GITEA_ARTIFACT_AUTHOR_NAME` and `ORKET_GITEA_ARTIFACT_AUTHOR_EMAIL`.

Authentication uses `GITEA_ADMIN_USER` and `GITEA_ADMIN_PASSWORD`; secrets are not
in the retained binding, repository URLs or command diagnostics. Credentials in
URLs, invalid target/ref components and escaping prefixes are rejected. Git uses
a restricted environment, explicit author data and disabled hooks/global config.
HTTP and Git execution are asynchronous. Git diagnostics are bounded, truncated
output is failure, and cancellation drains owned processes through the shared
application command supervisor. Its OS backend confirms descendant teardown before
success; missing cleanup evidence remains command-execution uncertainty. Git keeps
its 60-second command budget and 262,144-byte limit for each output stream. Raw
exporter and Git embeddings supply the command port; the native application factory
binds it with the same captured process environment as HTTP. The restricted Git
environment never consults later ambient values. Explicit empty mappings remain empty
apart from required export/authentication overlays.

Every adapter-owned Git command supplies `core.longpaths=true` before its
subcommand, including the initial `git init`. Initialization also retains the
repository-local setting for later use. Bootstrap cannot depend on configuration
inside a repository that does not yet exist. Cache placement, captured inputs,
command ownership, deadlines, output bounds and private error classifications
retain their existing contracts. Migration and proof limits:
`docs/architecture/CONTRACT_DELTA_GITEA_GIT_BOOTSTRAP_D_2026-09-25.md`.

Payload arguments are copied before the first await. Payload construction and Git
cache preparation run as owned native work: cancellation, repeated cancellation and
caller timeout wait for the admitted worker to settle. A worker failure takes
precedence over cancellation. Partial local effects can remain; interruption does
not authorize a push or establish remote rollback. Command cancellation preserves
the supervisor's lifetime observation as its cause and remains compatible with
caller timeouts. Export owner fencing is defined below; hostile-writer containment,
stuck native workers and remote-effect rollback remain separate obligations.

Standard epic preparation supplies the retained export date and timestamp. The
manifest records that timestamp, original run/build/status/summary and workspace.
Payload files are captured before dispatch. Later workspace changes cannot change
the retained commit. Source symlinks/reparse points and escaping cache paths reject
preparation. This does not replace arbitrary custom-writer or OS-containment proof.

Remote paths use `<prefix>/<YYYY-MM-DD>/<safe-run-slug>-<first-12-sha256-of-run-id>`.
The hash suffix prevents collisions between run IDs with the same normalized slug.
The existing cache root contains `payload/<sha256-of-run-id>` and
`repo_cache/<sha256-of-canonical-binding-and-run-id>`. The latter holds the original
local Git objects needed for a first push; it is not a source repository checkout.
Preserve the publication journal and required Git objects with runtime evidence.

## Dispatch and reconciliation

1. Only the call that durably claimed export may create the selected repository
   and push. An enabled direct `export_run` call requires the retained intent.
2. Repository existence reads distinguish missing repositories from HTTP failure.
   Creation targets the bound user or organization without owner fallback. Git
   fetch/commit/push errors cannot masquerade as an empty remote or no-op success.
3. Push uses the exact retained commit and a normal, non-forced branch update.
   Concurrent branch changes may refuse it. Automatic recovery only confirms;
   explicit owner recovery below can authorize an exact-commit retry. Neither
   path generates a merge, force-push or rebuilt payload.
4. Before success, fetch the selected remote branch, prove the retained commit is
   reachable from its observed head, compare the exported subtree and check manifest
   run/path identity. The receipt includes commit/tree and an immutable commit URL.
5. Automatic reentry after a lost result performs that same remote confirmation without another
   push or workload dispatch. A confirmed result can finish local publication even
   when the original local acknowledgement was lost. Gitea API projections may lag
   the committed Git state; they are not the export receipt authority.
6. Missing/unreachable commit evidence remains `E_EPIC_EXPORT_OUTCOME_UNCERTAIN`.
   Transport or integrity failures propagate without clearing the attempt or
   publishing success. A marker alone does not prove an effect happened or did not
   happen. Unconfirmed attempts need owner recovery/reconciliation; they do not
   acquire automatic retry permission.

## Explicit export owner recovery

This opt-in operation recovers a retained export after workload completion. It
does not transfer ownership of unknown workload effects.

1. New export claims retain `epic_export_dispatch.v1` in the same publication
   journal transaction as the phase-four intent marker. The record binds session,
   intent digest, original claim time, opaque owner and fencing generation. Its
   initial reference is retained in preparation artifacts. The existing run
   admission, workload outcome and Git intent are not replaced.
2. The canonical Python `run_card` surface accepts an explicit `export_recovery`
   only for a bound epic and explicit session. It is mutually exclusive with
   `admission_recovery` and `approval_recovery`. `epic_export_recovery_request.v1` binds a stable request
   ID, expected owner/generation/claim digest, exact intent digest, operator and
   reason references, and the explicit resolution `retry_exact_commit`.
3. A valid request checks the original request, export binding and completion
   evidence. Under the journal writer transaction it fences the old export owner,
   records a canonical `OperatorActionRecord` and grants at most one new local
   dispatch owner. The exporter first confirms remote state; confirmed delivery
   finishes publication without another push. An unavailable or invalid remote
   observation is an error, not absence or permission to mutate another target.
4. If the exact commit is not confirmed, that newly granted owner may repeat
   repository creation/exact-commit export. It cannot regenerate payload, replace
   intent, reset cards, rerun workload, merge, force-push, change branch or widen
   accepted completion. Lost local Git objects remain a blocker. A changed remote
   branch can refuse the ordinary fast-forward push.
5. Before actual export dispatch the local caller must match the current owner
   reference under the same journal transaction that surrounds the export call.
   An old caller paused outside that section cannot dispatch after replacement.
   A callback already inside it must settle or lose its process/connection before
   another caller can acquire the writer. This is local dispatch fencing, not a
   claim that a remote server's previously accepted work has stopped.
6. Repeating an identical recovery request observes its existing disposition and
   never obtains another dispatch grant. Conflicting reuse, stale evidence,
   superseded requests, changed intent and damaged/missing owner history reject.
   Another uncertain delivery requires a new explicit recovery request. There is
   no automatic retry loop and no guarantee of exactly one transport submission.
7. The retry effect is the retained Git commit/tree becoming reachable on its
   bound branch. Content addressing and non-forced updates preserve that scope.
   Arbitrary remote hook side effects, other exporters, untracked writers and
   cross-journal coordination are not included in this retry guarantee.
8. Successful publication atomically settles the dispatch record with preparation
   progress and carries its final reference into published artifacts. Publication
   checks that reference against retained owner history. New preparation markers
   cannot silently fall back to legacy handling when the owner record disappears.
9. Existing phase-four preparations without an owner marker keep read-only remote
   reconciliation. They cannot acquire retry permission through inferred or
   backfilled ownership. Their bytes and digests are preserved. Failed transport,
   cancellation and crash retain uncertainty until confirmation or another
   admitted recovery; local task termination does not establish remote outcome.

## Version and proof boundaries

Preparation v1 lacks the retained Git intent contract and is rejected by the v2
reader. Expanded bindings also reject old insufficient inputs. Do not backfill
intents from current files, rewrite old digests or clear history to force reentry.
No production migration or release is performed by this worktree change.

Source acceptance uses an explicitly selected disposable localhost Gitea instance,
native process restart and a combined live llama.cpp/Gitea run. Test servers and
their anonymous volumes are removed in the same path. Scoped installed Windows
Python 3.11/3.12 acceptance also runs actual Gitea recovery. Linux 3.11/3.12 checks
cover journal/native recovery with simulated export callbacks; Linux Gitea
transport remains unverified because the WSL Docker integration is unavailable.
These checks do not establish production Gitea acceptance, independent historical
authenticity, global atomicity or exactly-once effects under arbitrary writers.
