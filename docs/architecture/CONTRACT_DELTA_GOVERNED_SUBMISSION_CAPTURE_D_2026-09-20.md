# Governed submission and provider input capture

## Summary

- Owner: Orket Core.
- Date: 2026-09-20.
- Affected contracts: governed-agent submission and local provider preparation.
- Effective version: 0.6.41 (patch candidate; acceptance remains in the canonical plan).

## Delta

An async governed submission captures its absolute invocation root and a private
environment snapshot when its body starts, before its first suspension. Relative
project, catalog, request, continuation and database paths bind to that root.
The retained preparation worker receives these captured inputs; later process
working-directory or environment changes cannot select different input files,
extension storage, provider configuration or the submission database. An explicit
relative invocation root, or a path that remains nonabsolute after binding, is
refused before worker scheduling or filesystem effects. This captures path
selection, not file contents, symlink targets or a filesystem transaction.

`submit_governed_agent` accepts optional keyword-only `invocation_root` and
`environment` inputs. Its existing callers remain valid. Provider selection
forwards the captured environment through local runtime preparation. Direct local
runtime preparation copies the role-to-model mapping and environment before its
first inventory await, and uses those same inputs for every role and client.
Explicit provider URL and model choices retain precedence. SDK iteration requests
already provide frozen nested contract values and remain their sole authority.

The retained worker, provider cleanup, exact inventory matching, quarantine,
strict prompt profiles, admission, leases, continuation, replay and terminal truth
contracts remain in force. A captured quarantine refusal is still a refusal;
capturing inputs does not bypass validation. This boundary does not capture an
entire wake-dispatch operation or provide hostile-code containment.

## Migration Plan

1. Pass captured root/environment to submission when the caller owns an earlier
   boundary; otherwise capture occurs when the async submission body starts.
2. Forward explicit environment through shared provider selection and runtime
   preparation. Keep direct synchronous reads inside the existing owned worker.
3. Migrate test wrappers for the explicit private preparation inputs. Require real
   subprocess/SQLite submissions under queued cwd changes, controlled real TCP
   inventory and completions under environment/model mutation, and refusal controls.
4. Preserve earlier failed fixture observations. Separate controlled TCP responses
   and deterministic governed execution from actual model inference; neither is
   evidence of the other. Keep existing interruption/deadline assertions and source
   and installed-package acceptance selections.

## Rollback Plan

Drain owned work before rolling code and callers back together under a new patch
version. Preserve catalogs, databases and retained evidence. Reverting capture
reopens the documented queued-input counterexamples and cannot be represented as
equivalent behavior.

## Versioning Decision

Patch checkpoint for deterministic input ownership. Existing async call signatures
remain usable. Broader C/D, E and CAP work and explicit lane acceptance remain open.
