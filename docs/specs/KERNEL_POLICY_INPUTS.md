# Kernel admission and credential inputs

Status: Active admission and credential contract (credential boundary: 0.6.75)
Last updated: 2026-09-21

Kernel proposal admission captures `ORKET_ENABLE_NERVOUS_SYSTEM`,
`ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS` and `ORKET_USE_TOOL_PROFILE_RESOLVER`
from one environment snapshot before request validation, hashing or event
publication. The resulting value is immutable and requires plain booleans.
Admission evaluation receives it explicitly and does not reread environment.
Later invocations without an explicit input capture the then-current environment.

Default decoding is unchanged: enabled and pre-resolved flags default false;
the resolver defaults true only when its variable is absent. Existing accepted
true tokens remain `1`, `true`, `yes` and `on`, ignoring surrounding whitespace
and case. An explicitly empty environment is authoritative.

Trusted Python callers may supply the typed policy input through kernel API
admission. It is not populated from request dictionaries, proposals or HTTP JSON.
A disabled selected input refuses admission before events. Existing proposal,
reason-ordering, leak, resolver and approval semantics remain in force. This
change neither authorizes tools nor admits a new workload or trust boundary.

The existing policy-digest snapshot remains the authority for its documented
policy examples and builtin profiles. This input value does not replace that
snapshot, reseal retained events, or add a new durable policy schema. Existing
in-memory ledger limitations and control-plane transaction boundaries remain.

Acceptance compares stable inputs with independently observed published v0.6.55
outcomes, holds real admission hashing while operator flags rotate, verifies
actual events and refusal controls, and exercises source and installed public
paths. Controlled clocks/scheduling and in-memory records are identified as such.
Whole-kernel purity, durable recovery and inference are separate claims.

## Credential observations and authorization

Credential issue and consume wrappers capture their JSON request and trusted key
before validation or waiting on runtime state. Issue also captures time/identity
at that boundary. Default consume samples time after acquiring the runtime lock,
so a wait cannot extend expiry. Explicit
typed inputs are a trusted Python embedding surface; request dictionaries and
HTTP JSON cannot override them. Default application composition samples the
then-current environment once per invocation. A later invocation can observe an
operator key rotation; changing environment during an admitted invocation cannot
replace its selected key. An explicitly empty environment is authoritative.

Retain the existing HMAC-SHA256 algorithm, development-key default, 32-byte URL-safe
token generation and `tok-` plus 12-byte hexadecimal identity format. Never expose
keys or raw credentials in input representations, exceptions or ledger events.
The raw token remains only in the issue response. Hashes are safe event identities;
they do not independently prove a connector executed or a caller owns a workload.
Reusing an already stored token hash or token-identity hash is refused; explicit
identity injection cannot overwrite prior use/invalidation and reset replay state.

One timezone-aware UTC observation determines issue creation, expiry and its
credential event timestamp. TTL retains the minimum of one second. Consume uses
one explicit observation for expiry, use and invalidation; default composition
observes it inside the protected decision. Equality with expiry
is expired. Missing or malformed stored expiry remains expired. Existing binding,
replay and invalidation reason precedence remains authoritative. Token hashing and
expiry/binding decisions use supplied values, without ambient fallback.

Issuance requires an `ACCEPT_TO_UNIFY` admission, or a `NEEDS_APPROVAL` admission
with an APPROVED record for exactly the same session, proposal and admission
decision digest. REJECT, QUARANTINE and unknown decisions cannot issue credentials.
An unrelated approved record cannot satisfy the gate. Observe and validate this
authorization under the same runtime lock as token publication. Scope/profile
inputs retain their existing canonical digest rules and full identity; this does
not invent missing proposal semantics or trust arbitrary profile declarations.

Low-level credential effects require explicit observation inputs. Public wrappers
retain their response shapes; existing trusted callers can omit the input and use
the application capture boundary. Token invalidation takes an explicit observed
time from its owning session-end or approval-decision invocation. Other kernel
events/maps and their in-memory recovery limits remain separate D work. This
contract does not admit a new capability or claim durable credential recovery.
