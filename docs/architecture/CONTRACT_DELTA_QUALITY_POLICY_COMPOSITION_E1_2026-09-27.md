# Quality configuration and request policy composition

## Summary
- Owner: Orket Core
- Date: 2026-09-27
- Affected contracts: `docs/specs/QUALITY_CHECKER_CONTRACT.md` and
  `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.

## Delta
- Previous Quality coverage invocation discovered configuration implicitly.
  Native Python children launched elsewhere could collect statement data while
  the parent collected branches, preventing combination.
- Quality now supplies `--cov-config=pyproject.toml` while preserving the
  89-percent floor. Three native controls retain same-directory success,
  foreign-directory configuration loss and explicit-configuration success.
- The API router previously constructed `RuntimePolicyInputService`, violating
  its existing composition boundary. `ApiRuntimeContainer` now constructs and
  awaits that service using the router's captured environment and invocation root.
  Each request still observes current operator inputs and retains native work
  through interruption. Response and settings-conflict semantics are unchanged.
- Workflow selector checks inspect actual command arguments separately in each
  required job. Inserting another selector cannot hide an existing gate; a
  duplicate in the wrong job, comment or echo cannot satisfy it.

## Migration Plan
1. No public runtime compatibility window or caller migration is needed.
2. Use the explicit coverage configuration in local reproductions of Quality.
3. Retain API composition, actual request/file/lifetime controls, native coverage
   controls and adverse workflow-selection checks. Record exact source proof in
   the architectural-truth plan; focused success cannot close full-suite debt.

## Rollback Plan
1. Regressed request semantics or coverage injection requires restoring the
   previous implementation and retaining the newly exposed failure as open debt.
2. No persistent data migration or recovery is involved.

## Versioning Decision
- Patch checkpoint: 0.6.114, 2026-09-27.
- Compatibility: preserved; internal composition and contributor command change.
- Full Quality, installed/platform acceptance and whole-plan completion remain
  separate obligations.
