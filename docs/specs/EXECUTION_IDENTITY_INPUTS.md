# Execution identity input ownership

Status: Active contract for the 0.6.51 candidate
Last updated: 2026-09-20
Owner: Orket Core

Application `execution_policy_input_service` captures selected run/session and
build identities at epic setup entry and epic-collection entry, before their first
asset-read await. It observes a missing session ID through RuntimeInputService and
computes the sanitized asset name through the authoritative `orket.naming` helper.
Strategy recommendations are consumed and validated at this same boundary.

Custom build selectors receive `(build_id, original_name, sanitized_name)` with a
plain string as the third argument. They no longer receive a callable sanitizer.
Existing explicit build overrides and default prefixes remain: `build-` for epics
and `epic-collection-build-` for collections. Custom selected identities must be
nonempty plain strings. No new whitespace normalization is applied to selected
IDs and no entered strategy is retried with an old signature.

Later input-source changes or collection-node replacement cannot alter these
captured parent identities. The boundary is setup/collection entry, not an atomic
snapshot of all earlier pipeline routing, initialization or subsequent child
configuration. Each child retains its own admission authority. Trusted in-process
Python is not contained by these value contracts.

Missing-ID observation and strategy refusal can now precede asset validation.
An invalid or missing asset may therefore consume an ID observation without
publishing a session. Invalid recommendations fail before this entry's asset
reads or publication; earlier pipeline initialization may already exist. Existing
durable admission, recovery, approval, completion evidence, lifecycle outcomes and
child identity derivation remain authoritative and are not bypassed.

The canonical architectural-truth plan records scoped source/installed/live proof
and remaining platform and whole-lane acceptance limits.
