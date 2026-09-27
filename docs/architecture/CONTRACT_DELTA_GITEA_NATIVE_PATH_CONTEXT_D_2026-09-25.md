# Gitea retained repository native path context

## Summary

- Owner: Orket Core, architectural-truth D.
- Date and target: 2026-09-25, unpublished v0.6.106 candidate.
- Contract: `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`.
- The canonical remediation plan owns acceptance and publication status.

## Delta

Git for Windows bootstrap and configuration locking can exceed native path
limits before `core.longpaths` is effective. The retained source opening passed
at a 235-character repository root, failed during configuration at 247, and
failed during initialization at 248 and 255. Earlier installed failures remain
retained separately.

For a Windows repository whose lexical `.git/config.lock` path reaches 260 UTF-16
code units, the adapter observes existing native short names for the same
repository and canonical `.git` directory. Only admitted initialization creates
that empty `.git` directory before name observation. One existing owned worker
retains creation, lookup and identity validation through interruption. Ordinary
shorter paths and POSIX Git keep their existing argument/environment path.

Each affected command receives explicit `--git-dir` and `--work-tree` arguments,
plus `GIT_COMMON_DIR` naming that same `.git` directory. Its cwd remains the
original canonical repository. Names must be absolute directories, match the
original filesystem identities and fit the bounded native argument limits.
Unavailable, unchanged-too-long, wrong-directory or invalid observations raise
`E_GITEA_GIT_NATIVE_PATH_UNAVAILABLE` before command admission. The helper refuses
event-loop execution before native effects. Windows does not guarantee short
name availability; the adapter does not create aliases or change OS settings.

Command root, environment and runner are captured before the added await. The
existing command supervisor, 60-second budget, bounded capture, private Git
errors and cancellation lifetime cause remain authoritative. Cancellation waits
for name observation and prevents command admission afterward; native failure
keeps precedence. Partial directory effects can remain.

## Migration Plan

1. Preserve the canonical cache binding, 64-character hash names and original
   `.git/objects`. Existing retained intents still require their original objects.
2. There is no cache move, namespace migration, new resource owner, shorter test
   root, retry through a different repository or global Git configuration change.
3. A host without usable native names reports the explicit path blocker. This
   change does not promise arbitrary-length process cwd, hostile-writer
   containment or handle-bound path identity through concurrent replacement.

## Rollback Plan

An object-location, command-input, teardown or error-precedence mismatch blocks
publication. Retain failed/passing observations and repair the same owner and
repository path. Do not relocate retained objects or weaken acceptance bounds.

## Versioning Decision and proof

The effective target is v0.6.106, still unpublished. All 71 affected cases pass
in fresh source and installed Windows Python 3.11/3.12, including four physical
boundaries, native lifetime/admission controls and all 19 earlier installed
failure identities. Each cell retains 20 actual SQLite observations below the
unchanged 0.5-second limit. The canonical plan binds the exact proof and retained
environments. Full successor acceptance remains required.
Real local Git proof does not establish remote Gitea acceptance.

Primary implementation references:
[Windows native-name contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getshortpathnamew)
and [Git for Windows explicit-directory admission](https://github.com/git-for-windows/git/blob/v2.52.0.windows.1/setup.c#L950).
