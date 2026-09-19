# API startup ownership and retained quality corrections

Owner: Orket Core. Date: 2026-09-18. Effective version: 0.6.22.

## Delta

API initialization previously ran outside admitted request ownership. Immediate
close could release the engine before initialization cleanup, and a newly queued
broadcaster could reacquire an already closed app context. Application now captures
startup owners before awaiting, admits initialization through the shared lifetime,
registers subscription cleanup and starts the broadcaster through managed background
admission. Shutdown drains initialization before engine close. Broadcaster failures
close admission and remain failed teardown; delivery releases queue bookkeeping.

The posture event now reports effective anonymous authentication. A bypass flag
alongside a configured key no longer claims disabled authentication. Existing
production/staging rejection of that flag remains. The unused startup `logs/`
directory creation is removed; actual logging manages its destination.

Affected authority: `docs/specs/API_RUNTIME_LIFECYCLE.md`, `CURRENT_AUTHORITY.md`.
This introduces no new HTTP schema, compatibility shim, shutdown deadline,
cross-process owner or remote-effect termination guarantee. Manually registered
API tasks retain their existing limits.

## Quality and portability

Repository-owned Phase 4 and benchmark-suite child commands retain `sys.executable`.
Explicit runner-template executable selection remains caller-owned. Test launchers
select the actual test interpreter. Settings API tests persist/read temporary files;
preview/driver transport tests use explicit async ports and assert driver close.
The SQLite interruption fixture holds actual queued I/O without replacing execute's
awaitable/context-manager contract. Other fixtures bound Git discovery, deterministically
vary serializer output, and recognize exact migrated aliases/intentional CLI output.
No broad policy waiver is added.

Marshaller clone uses command-local and clone-local `core.longpaths=true`; source
and global Git config are unchanged. Actual clone/patch/gate proof covers Git object
paths beyond Windows MAX_PATH while the native working directory stays launchable.
Retained probes also show Windows refusing Python/Git launch when the working
directory itself exceeds 260 characters, including an extended-path prefix. That
host limitation remains; this correction does not promise arbitrary path lengths
or reopen the future-held marshaller requirements lane.

## Migration, verification and rollback

This is a compatible patch; embeddings continue to run the app lifespan. Consumers
of `api_security_posture` should interpret bypass as effective anonymous access.
No persisted state migration is required. Revert the scoped implementation and
matching authorities only if regressions require rollback; preserve all observed
failures and proof artifacts. Reverting startup ownership restores the demonstrated
race and is not an acceptable completion state.

Source, native installed, structural and full-suite outcomes are recorded separately
in the canonical architectural-truth plan. Controlled factory/worker faults are
not provider execution proof. C/D/E, capability acceptance and whole-lane acceptance
remain open until their own gates pass.


Final verification retains the first failed full-source observation and the
benchmark expectation correction. All 19 predecessor failure outcomes pass in
the full observation; its sole stale assertion passes corrected focused proof.
No fresh all-green full run is claimed. The installed 667-case matrix
precedes the disclosed fixture EOF/expectation edits and compatibility-token fix;
runtime package bytes are unchanged. Quoted Windows benchmark runner paths remain
unverified beyond the retained failure. Canonical lint/dependency gates remain red.
See the canonical plan for exact counts, artifact bindings and acceptance limits.
