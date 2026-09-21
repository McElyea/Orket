# API strategy input ownership

Status: Active contract for the 0.6.50 candidate
Last updated: 2026-09-20
Owner: Orket Core

Application admission owns copies of API strategy inputs and recommendations.
Archive entry captures card IDs, build ID, related tokens, actor and reason before
its first await. Selector strategies receive optional string tuples; effects use
fresh lists from the captured values. An entered strategy is called once. A
selector recommendation must be a boolean. The selected strategy remains the
invocation's strategy through later archive effects.

Archive response normalization receives immutable ID tuples and the observed
build count. Its JSON response must preserve `ok=true`, the default observed
count calculation, and the exact unique archived/missing ID sets. Ordering and
additional JSON presentation fields remain customizable. A contradictory claim
raises `E_API_ARCHIVE_RESULT_CONTRADICTION`; completed archive transactions remain
durable. The count retains existing semantics: build-operation count plus unique
explicit/related archived IDs, not a new global deduplication or atomicity claim.

Metrics strategies receive SDK `FrozenJson` observations. Explorer sorting receives
a tuple of copied read-only entry mappings; preview strategy chaining receives a
copied read-only string target mapping. Application validates and copies their
JSON recommendations. Explorer output must describe observed admitted entries;
sorting cannot invent or alter filesystem facts. Inclusion recommendations must
be booleans. Paths and filesystem authorization remain application-owned.

Invocation recommendations contain a plain-string method name, JSON argument
list and keyword mapping, plus an optional string unsupported-method detail.
Application captures them before intervening awaits, including preview-builder
construction and run-event publication. Existing supported method dispatch remains;
this is not a new method allowlist or an untrusted-code boundary. Invalid shapes
fail before dispatch; earlier preparation effects are not silently undone.

Websocket removal strategies receive the captured error category `runtime_error`,
`value_error` or `other`, rather than a mutable exception. Their result must be a
boolean. WebSocketDisconnect handling remains application-owned. Default behavior
and scalar/path/calendar strategy inputs otherwise retain their existing contracts.

These contracts protect borrowed inputs and retained recommendations from ordinary
mutation. They do not contain hostile in-process Python, freeze all runtime state,
or establish independent success evidence for arbitrary custom presentation data.
Scoped proof and remaining acceptance limits live in the canonical architectural-
truth plan. No lane retirement follows from this transition.
