# Extension Git checkout-directory arguments

## Summary

- Owner: Orket Core, architectural-truth D.
- Date and target: 2026-09-25, v0.6.106 development candidate.
- Status: implementation contract; the canonical remediation plan owns proof and publication.
- Affected authority: extension installation and retained-checkout integrity.

## Delta

Reference resolution and detached checkout previously supplied absolute
`--git-dir` and `--work-tree` arguments while also selecting that checkout as the
existing command owner's working directory. On the observed Git for Windows
2.52.0.windows.1, a 217-character checkout produces a 222-character absolute
Git-directory argument and fails before reference resolution with
`'$GIT_DIR' too big`. The earlier invocation-scoped `core.longpaths=true` remains
required but does not remove that argument-admission limit.

Both operations now share the explicit arguments `--git-dir=.git` and
`--work-tree=.`. The existing owner still receives the same checkout directory
as `cwd`; these names therefore refer to the same repository and worktree after
the owner's existing input capture. Neither operation searches for another
repository, changes the checkout location, recaptures ambient cwd, or selects a
fallback. Clone arguments and the catalog's stored absolute checkout path remain.

The existing Git process supervisor, worker, environment filter, cancellation
settlement, private failure diagnostics, 120-second clone budget and 30-second
other-command budget remain authoritative. The commit selector and commit-format
validation remain unchanged. There is no new process or filesystem resource owner.

## Migration and rollback

Public signatures and persisted catalog records need no migration. Internal
reference and checkout callers use the shared checkout argument constant and
continue to supply the admitted checkout directory to the same process owner.
Existing retained repositories, locks and failed checkouts must not be moved,
rewritten or removed.

A different repository identity, changed commit, abandoned child, catalog drift,
or changed failure/cancellation precedence blocks publication. Repair through the
same owner and retain both failed and passing observations; do not restore an
absolute-argument length dependency or weaken the native regressions.

## Proof and limits

The new integration regression uses actual SDK source repositories, native clone,
reference resolution, detached checkout, exact source bytes, native HEAD,
catalog publication and a reconstructed manager. It checks 200- and 217-character
checkout roots, all three successful owned command receipts and absent observed
PIDs. The original implementation passed the shorter control and failed the
217-character case; the correction passed both source cases.

The 60-case affected cohort now passes fresh source and installed Windows Python
3.11/3.12 execution, including all 36 previously failed extension identities.
Physical HEAD/catalog readback, exact case equality, package origins and owner
settlement are retained in the canonical plan. This is scoped live extension
proof; the complete successor acceptance matrix remains required. The separate
Gitea initialization failure at a 255-character repository root remains
unresolved; this extension correction does not change the Gitea cache layout or
promise general Windows long-working-directory support. Linux, remote Git,
provider, wider D/E/CAP and whole-lane acceptance are not established here.
