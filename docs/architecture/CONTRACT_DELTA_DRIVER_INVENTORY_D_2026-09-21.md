# Driver inventory ownership and inputs

Status: Active contract delta
Last updated: 2026-09-21
Owner: Orket Core

For requests that require model context, application preparation captures the
selected project root, model root and environment before scheduling native work.
Both roots must be absolute. One owned worker constructs the config loader and
side-effecting driver resource store, observes department/team/skill filenames,
and collects active rock/epic names through the existing config loader. This
removes event-loop filesystem traversal and synchronous config bridges from
this request path. Constructor config loading and request preparation receive
the driver's detached, read-only construction-time environment; an explicitly
empty mapping cannot fall back to ambient environment values.

Cancellation, timeout and repeated cancellation retain admitted work until it
settles. Native failures remain visible, including when interruption is pending.
Provider dispatch does not occur after interrupted or failed preparation.
No forced thread-stop deadline or atomic multi-directory snapshot is promised.
The existing loader precedence and sorted active-asset names remain unchanged;
department/team/skill enumeration retains native order. A missing model root
remains a failure rather than a fabricated successful empty inventory.

This moves the former private driver inventory implementation into the storage
adapter and composes its effects in application. Supported driver construction
and request behavior remain unchanged within this inventory scope. The subsequent
`CONTRACT_DELTA_DRIVER_LIFETIME_D_2026-09-21.md` defines async construction,
settings capture, console ownership and provider cleanup; direct synchronous
construction refuses an event-loop thread. This does not freeze every mutable
prompt/provider field or establish alias-complete async reachability. Remaining
ConfigLoader sync callers and full D purity/classification obligations stay open. Scoped acceptance and retained failures
belong to the architectural-truth remediation plan.
