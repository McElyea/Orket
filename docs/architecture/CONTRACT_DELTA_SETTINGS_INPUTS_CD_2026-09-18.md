# Captured settings operations and owned persistence

Owner: Orket Core
Date: 2026-09-18
Status: scoped source/installed proof passed; full quality and whole-plan gates remain open

## Summary and delta

Seven retained counterexamples against 0.6.20 demonstrate nested runtime settings
and preferences mutation, mutated cache exports, stale default paths after an
invocation-directory switch, malformed input reported as empty, an abandoned
canceled file worker, and filesystem probing by a cold synchronous event-loop
read. Original observations remain under `.tmp/d-settings-inputs/before/`.

Replace the implicit cache and reflective global lookup with captured operation
locations and serialized runtime inputs. Application owns read/write/migration
policy, while storage uses existing verified publication and native file locks.
Missing files remain a valid empty input; malformed and unreadable files refuse.
Synchronous cold access fails before filesystem work in an event loop.

Actual HTTP counterexamples additionally retain a settings response reporting a
runtime snapshot instead of persisted values and a shutdown dropping request
ownership while its outer file thread still runs. The settings router now awaits
the async persistence callbacks directly. A retained overlapping-request probe
also shows two HTTP 200 responses while the later stale write loses the earlier
change. Conditional publication now compares the validation input under native
writer ownership and returns HTTP 409 on changed inputs or busy ownership. The
caller reloads before retrying; unconditional full-object saves remain explicit
replacement operations.

Preference migration also retains pending source/destination binding before
stripping legacy keys, so a failed second-file publication can resume after
process restart. A completion marker alone no longer conceals conflicting
leftover source values. Cancellation drains admitted work and preserves failures.

## Migration plan

Patch checkpoint 0.6.21. Follow `docs/specs/SETTINGS_INPUT_OWNERSHIP.md`:

1. Bind runtime snapshots explicitly or await persistence reads; remove reliance
   on empty-file synchronous access in an event loop or implicit cache mutation.
2. Rotate runtime snapshots explicitly after settings changes. Configure global
   path overrides before concurrent work; they do not isolate application owners.
3. Correct malformed/unreadable files instead of relying on silent defaults.
4. Retain both files and native ownership files during pending migration. Resume
   through the preference loader; do not mix writers from older binaries.
5. Test the actual persistence path with explicit temporary settings roots and
   bootstrap inputs. Production no longer has a pytest detection bypass.

## Rollback plan

Stop all cooperating writers, preserve both settings files and retained pending
records, and resolve or complete a pending migration before using an older binary.
Revert runtime, callers and test bootstrap together. Reverting restores the
observed mutation/cache/lifetime defects; it does not establish conformance.

## Verification and limits

Source counterexamples and actual file/restart/native-admission tests are retained
with their exact inputs in the canonical plan. Consumer regressions exposed an
existing test still targeting the retired runtime API factory; its mock target
now follows `orket.interfaces.runtime_entrypoints`, matching `server.py`.
This structural fixture correction is not deployed-server proof.

No new provider, host-clock, cross-host locking, hostile-editor containment,
multi-file atomicity or whole-plan acceptance claim is admitted. Remaining
dependency, explicit-input, async and quality obligations remain active.

The final 617-case source selection and all four Windows/Linux Python 3.11/3.12
installed selections pass on the journal-fixed runtime wheel. Four actual Gitea
server flows also pass with verified teardown. The fresh full Windows source run
still fails; its exact counts, failure index, artifact bindings and file inventory
are recorded in the canonical architectural-truth plan. This is a local versioned
checkpoint, not release readiness or whole-plan acceptance.
