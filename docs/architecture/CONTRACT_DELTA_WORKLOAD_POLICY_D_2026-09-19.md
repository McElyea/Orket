# Captured workload policy

## Summary

Owner: Orket Core. Date: 2026-09-19. Effective version: 0.6.36.
Affected contracts: SDK/legacy execution admission, artifact validation, governed
identity and provenance. Status: active; scoped source and combined installed proof is recorded in the canonical plan.

## Delta

Previously, extension execution reread environment policy across awaited stages.
A successful run could report different policy digests in its result and retained
provenance; changing verbosity could expose configuration that was admitted under
redacted publication. The retained 0.6.35 installed counterexample remains evidence
of that defect.

From 0.6.37, the manager captures one frozen `WorkloadPolicy` before preflight's
first await and passes it explicitly to the executor. The 0.6.36 boundary was the
executor's first await; migration is in `CONTRACT_DELTA_EXTENSION_INSTALL_D_2026-09-19.md`.
The snapshot includes `ORKET_RELIABLE_MODE`, `ORKET_RELIABLE_REQUIRE_CLEAN_GIT`,
`ORKET_EXT_PROVENANCE_VERBOSE`, `ORKET_EXT_ARTIFACT_FILE_SIZE_CAP_BYTES` and
`ORKET_EXT_ARTIFACT_TOTAL_SIZE_CAP_BYTES`. Existing boolean, numeric and default
semantics remain unchanged. Invalid numeric values fail admission before loading
legacy extension code. Each invocation captures independently, including overlapping
runs using the same manager. No mutable policy is assigned to the shared builder.

That same value drives legacy material/clean-Git admission, SDK declared-artifact
validation, manifest limits, result/control-plane identity and provenance policy,
reliable-mode indication and redaction. Result, manifest and provenance retain
their distinct operator surfaces and matching policy/control-bundle identities.
The existing governed identity schema and SDK wire formats do not change.

Legacy material admission resolves the selected root and uses path containment,
refusing similarly prefixed siblings. Its file observations stay in an owned
worker. When required, Git status uses the existing native command supervisor;
acceptance requires complete output, confirmed cleanup and a zero exit code.
The command has a 30-second execution deadline. Cancellation retains native
cleanup through the supervisor; uncertainty or incomplete capture cannot establish
a clean repository. Loading, compilation and admission retain distinct interruption
boundaries. This is neither a repository lock nor a promise that files stay clean
after the observation.

Only these five policy inputs are covered. Provider/capability construction,
extension install/security policy, clocks, identity and other ambient inputs remain
separate obligations. SDK reliable-mode identity does not introduce legacy
material or clean-Git checks into SDK execution. Same-directory concurrent artifact
publication, arbitrary trusted callback mutation and cross-store transactions remain
outside this contract.

## Migration Plan

1. Artifact builders and validators now require explicit `policy`; capture once at
   the invocation boundary and pass it through all stages. No ambient fallback is
   retained inside the builders.
2. Retire the artifact cap/verbosity reader helpers and enforcer/manager
   reliable-mode readers. `validate_clean_git_if_required` is async and requires an
   explicit `required` boolean. Use the existing `compile_workload` helper directly
   instead of the redundant private executor forwarding method. No shims are added.
3. Preserve real SDK/legacy execution, database identity, concurrent policy rotation,
   file limits and Git/material refusal regressions in both Quality selections.
   Preserve prior publication/lifetime cases and installed source-origin checks.

## Rollback Plan

Drain workers and native commands before replacing policy owners and callers
together. Retain control-plane and artifact evidence. Never reconcile mismatching
historical policy identities by rewriting evidence or redispatching execution.
Rollback requires a new version and equivalent input/lifetime proof.

## Versioning Decision

Patch checkpoint 0.6.36. Internal helper signatures change as described; SDK
package versions and wire schemas remain unchanged. Full C/D/E/CAP acceptance is
still open. Local version/tag publication follows the user's work-hours restriction.
