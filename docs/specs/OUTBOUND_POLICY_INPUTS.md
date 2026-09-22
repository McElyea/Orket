# Outbound policy capture and file observations

Last updated: 2026-09-22
Status: Active implementation contract since 0.6.81; scoped acceptance belongs to the architectural-truth plan

Outbound policy evaluation accepts immutable `OutboundPolicyInputs`. Core owns
normalization, field defaults and value validation. Lists and field mappings are
detached into tuples and a read-only mapping. Equal supplied inputs and payloads
produce equal filtering decisions without environment or filesystem lookup.
`OutboundPolicyGate` also detaches values supplied to its existing constructor.
Its filtering and ledger disclosure rules remain the existing authority.

The application captures environment values before selecting a policy. Existing
`load_outbound_policy_config` and implicit `apply_outbound_policy_gate` calls use
the admitted Kernel environment snapshot, or capture the current process environment
when no snapshot is bound. Explicit `policy_inputs` bypass that lookup. An optional
config argument overlays explicit inputs using the existing merge rules: path and
pattern lists are unioned in order, allowed fields are replaced per event type,
and remaining fields use the later value. Explicit empty environment is authoritative.
Unknown config fields have no filtering effect. This is a presentation policy,
not broker execution authorization or an untrusted-code containment boundary.

API construction captures its environment and project root. Owned native preparation
reads the configured file, merges the captured environment and file configuration,
validates patterns and binds one immutable policy before admission. API response
filtering overlays only the response surface; later process-environment and file
changes cannot change the prepared policy. Reconfiguration requires a new app and
its normal preparation and cleanup. There is no live reload or global policy cache.

Kernel projection captures its request and policy before the observation callback.
Both policy context and tool context use that same captured policy before digesting.
The bound invocation environment remains authoritative across owned worker waits.
This does not authenticate caller-provided policy overrides or extend the Kernel's
independent completion-verification guarantees.

`load_outbound_policy_config_file` captures an absolute lexical selected path using
the admitted invocation root before calling the read-only storage adapter. Direct
file loading on an event-loop thread refuses before I/O with
`E_OUTBOUND_POLICY_REQUIRES_ASYNC_OWNER`; async callers use an owned native worker.
The adapter requires an absolute `Path` and reports
`E_OUTBOUND_POLICY_ABSOLUTE_PATH_REQUIRED` for other operands. Relative paths no
longer follow a later ambient cwd instead of the admitted root. This does not
confine symlinks or authorize arbitrary selected files.

Missing, unreadable, malformed UTF-8/JSON and non-object files remain failures;
there is no silent empty-policy fallback. Invalid regular expressions fail input
validation with `E_OUTBOUND_POLICY_INVALID_PATTERN` before API admission. Typed
value violations use the `E_OUTBOUND_POLICY_*_REQUIRED` errors. The underlying
read/decode failure remains available. Policy-read cancellation or timeout retains
the worker and acquired API container until observation and cleanup settle; a
native failure survives cancellation. API readiness cannot precede successful
policy preparation. This is lifetime ownership, not a bound on native read duration.

Existing redaction order, placeholder behavior, event field selection, and ledger
redaction-to-partial-view semantics remain unchanged. Pattern syntax is validated;
this does not establish a worst-case regular-expression execution bound or complete
PII detection. Source and installed proof must retain BT regressions, exact case
identities and the existing 0.5-second independent SQLite responsiveness bound.
Linux clock, full adapter/async inventory, E/CAP and user acceptance remain separate.
