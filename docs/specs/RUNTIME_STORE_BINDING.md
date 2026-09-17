# Runtime store binding

Status: Active contract; scoped BT-5 store binding and migration proof accepted
Last updated: 2026-09-13
Owner: Orket Core

## One binding per runtime store

Resolve the runtime SQLite path against the invocation directory once, before
constructing repositories. Retain an absolute workspace separately. The card,
session, snapshot, success, pending-gate and run-ledger repositories use that
runtime path. Card acceptance, epic publication/continuation and memory retain
their declared sibling stores. Engine, epic and turn control-plane owners all use
the runtime database's sibling `control_plane_records.sqlite3`; an output
workspace cannot select a different control-plane authority.

An existing object must not change storage after process CWD changes. New
invocations select their explicit paths independently. This contract does not
make a workspace change equivalent to the originally authorized effect target.

## Migration of old relative bindings

An old relative runtime path may have selected a workspace-relative control-plane
file. Existing epic request scopes also retain the original relative database
reference. Converting a filename alone must not discard that history, fabricate
an empty authority, rewrite an approval or permit duplicate dispatch.

Runtime admission must refuse an unbound historical relative epic scope before
execution or approval mutation. The explicit offline migration must:

1. Inspect the selected runtime, epic journal and original control-plane stores
   together. Retain the original request, approval, run, attempt and effect records.
   Every retained control-plane run must carry a digest-checked configuration
   snapshot naming a session in that journal. Orphaned or mixed-session authority
   refuses cutover; the command does not partition a shared historical store.
2. Back up the original control-plane database through SQLite, including committed
   WAL content, into the canonical sibling location. Preserve the original store;
   never merge or overwrite an unrelated populated target.
3. Record the exact existing session/request identities whose storage references
   were relative. A retained migration binding may reproduce only that session's
   original database reference in request comparison. Every other authorization,
   workload, configuration, target and workspace field must still match.
4. Retain durable migration identity in the selected runtime/control-plane pair.
   Missing, contradictory or interrupted binding cannot admit execution. Restart
   must either complete the same checked migration or refuse with its evidence.
5. Require old runtime owners to be stopped before the offline operation. Migration
   does not fence an arbitrary old executable or establish hostile containment.

The installed entrypoint is:

```text
python -m orket.interfaces.runtime_store_cli --runtime-db <absolute-runtime-db> --legacy-control-plane-db <old-control-plane-db> --legacy-invocation-root <original-project> --actor-ref <operator-reference> --owners-stopped
```

Runtime database, epic journal, artifact roots and native continuation-lock files
remain at their original paths. Only the old control-plane database is copied to
the canonical sibling location. A backup restored at the same paths can retain
those identities; arbitrary relocation or replacement of a native lock file does
not inherit an approval's continuation authority. The command retains its binding
inside the runtime/control-plane stores and prints their identities.

The migration binding is storage provenance, not a second workload-ID allocator
or an approval grant. New session scopes use the absolute database path. Completed
history remains inspectable; pending work resumes only through the existing
same-request, same-attempt pre-effect approval contract. Uncertain or post-effect
work gains no new recovery permission.

## Acceptance

Prove a real card pause/approval after CWD changes and prove that another output
workspace reads the same retained control-plane authority. Prove copied legacy
runtime/journal/control-plane history, committed WAL content, interrupted migration,
conflicting targets, repeated migration, and restart approval/denial without
rewriting the original request or duplicating effects. Repeat the admitted flow
through the rebuilt installed candidate and actual llama.cpp with sandbox disabled.
An initial resolver fix alone does not complete migration or BT-5 acceptance.

The accepted scoped evidence is `.tmp/bt5-store-authority/gate/audit.json`, with
source and installed Windows/Linux Python 3.11/3.12 controls, real prior-wheel
SQLite backups and installed migration/restart, plus actual llama.cpp success and
unsuccessful CLI outcomes using relative durable roots. The canonical plan retains
artifact identities, exact cases and the remaining family-authority obligations.
