# Extension installation and catalog admission ownership

Owner: Orket Core. Date: 2026-09-19. Effective version: 0.6.37.
Status: active contract; verification disposition is recorded in the canonical
architectural-truth plan. This does not close C/D or admit hostile extensions.

## Delta

Installation previously deleted the catalog-referenced checkout before cloning
and validating its replacement. Retained Windows and Linux observations show
failed replacements leaving the old catalog pointed at damaged or changed files.
Workload preflight also performed synchronous Git and file reads on its event loop.

`ExtensionManager.install_from_repo` is now async. Each attempt captures source
policy environment and the supplied clock before awaiting, allocates a distinct
checkout under the selected durable extensions root, clones, resolves a commit,
checks out that commit and validates its manifest before catalog publication.
No installation deletes or reuses a previously allocated checkout. Unpublished
attempts and superseded installations remain on disk for operator inspection;
this contract introduces no automatic garbage collection.

Git commands use the shared native process supervisor. Clone has a 120-second
execution deadline; checkout and commit observation have 30 seconds. Success
requires zero exit status, complete capture and confirmed cleanup. Interruption
retains native descendants through cleanup.

Interruption with confirmed cleanup and complete capture raises the exact base
`asyncio.CancelledError`, retaining the native observation as its cause; Python
3.12 caller timeout scopes can therefore convert it to `TimeoutError`. Incomplete
cleanup/capture raises `E_EXT_GIT_INTERRUPTION_UNCERTAIN`; a failed cancellation
record raises `E_EXT_GIT_CANCEL_RECORD_FAILED`. Both retain the original observation
and cause. Neither uncertain outcome becomes an ordinary cancellation.

Repository-local Git environment
overrides are removed and terminal prompting is disabled. Integrity observation
names the checkout's `.git` explicitly: missing metadata cannot skip validation
or discover an enclosing repository. Inline HTTP(S) credentials are refused;
command errors do not echo remote arguments or output. Credentials supplied by
normal Git credential mechanisms are outside recorded source values.

Application publishes the new row under native, nonblocking catalog ownership at
`<catalog>.extension-locks/<sha256("catalog")>.lock`. Preserve that lock identity
beside the catalog. Contention refuses the operation; successful writers merge
against the catalog observed under ownership. Malformed catalog containers or
non-object rows fail admission instead of becoming an empty replacement. Storage
writes a same-directory temporary file, flushes it, replaces the catalog and
verifies the exact closed-file bytes before returning success.

Interruption during allocation or manifest admission drains the worker and does
not advance to the next stage. Interruption after catalog publication starts
drains that publication and can leave a verified durable new row, even though the
caller receives cancellation. Failure after replacement can also leave a changed
catalog without a successful acknowledgement. Inspect the catalog and retained
checkouts; failure is not evidence that no effect occurred. The old checkout is
retained in every case. These are separate checkout/catalog effects, not a
cross-file transaction or crash-proof publication protocol.

`run_workload` captures nested caller inputs, workload policy and Git environment
before its first await. A retained worker resolves one catalog record, validates
integrity and constructs its control-plane admission value. The same policy is
then required by the executor. Controller children pass their SDK requirement to
that admission, inside their existing timeout; separate prechecks no longer race
against a later catalog read. Governed-agent wake catalog preparation likewise
retains its worker. CLI construction/listing use retained workers and installation
awaits the async service. Synchronous catalog/agent preparation APIs are worker or
standalone surfaces; synchronous Git observation refuses an active event loop.

## Migration

Await `manager.install_from_repo(repo, ref)`; standalone synchronous callers can
use `asyncio.run` outside an active event loop. No synchronous installation shim
is retained. Direct executor callers supply an explicit `WorkloadPolicy`; public
manager calls capture it. Source policy is `evaluate_source_policy(repo,
environment)` in `orket.extensions.source_policy`. Installation clock injection
is the keyword-only `utc_now` manager constructor argument. CLI syntax, catalog
row fields and SDK wire schemas remain unchanged.

Previously installed directories remain readable without relocation. A process
that already imported an older module can refuse a new checkout with the same
module name under the existing source-origin contract; restart or a distinct
module identity is required. Installation does not unload modules or claim
in-process hot upgrade.

## Limits and rollback

Retained file workers have no hard stop deadline; caller timeout waits for their
settlement. Native command execution deadlines and cleanup observations remain
separate. Catalog ownership coordinates cooperating local writers, not arbitrary
external mutation, distributed ownership or hostile code. Integrity checks cover
recorded commit identity and manifest digest; they do not establish every source
file's authenticity or prevent later mutation. API/controller composition still
has synchronous construction-time path/store observations requiring further D
work. Wider policy/provider clocks and adapter enforcement also remain open.

Drain workers and native commands before rollback. Keep catalog, native ownership
files and every referenced checkout; never replace an admitted directory in place.
Restore service/caller contracts together under a new version and equivalent
failure/lifetime proof. The checkpoint is not release or whole-lane acceptance.
