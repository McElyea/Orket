# Kernel admission policy inputs

Status: Active contract for the 0.6.56 candidate
Last updated: 2026-09-20

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
