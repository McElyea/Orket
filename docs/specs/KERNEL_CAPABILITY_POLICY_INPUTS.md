# Kernel capability policy inputs

Last updated: 2026-09-21
Status: Active implementation contract since 0.6.78; scoped acceptance belongs to the architectural-truth plan

The legacy `kernel_api/v1` resolve, authorize and execute-turn surfaces use one
immutable `KernelCapabilityPolicy` per evaluation. Its validated document is an
SDK `FrozenJson`; returned evidence and permission lists are caller-owned copies.
Missing fields, extra fields, invalid metadata, invalid permission lists and
invalid role/task mappings refuse. Explicit empty permission lists are valid.

The single shipped default lives at
`orket/runtime/config/assets/contracts/kernel_capability_policy_v1.json`, located
through `orket/runtime/config/contract_assets.py`. Its logical source is
`policy://orket/kernel/v1/default`; version and permission contents are retained.
The former `model/core/contracts/kernel_capability_policy_v1.json` is removed.
Archived OS documents describe that historical location, not current lookup.
The existing package-data declaration includes the new location in wheel and
source archives. There is no working-directory search or cached mutable policy.

Application service `capture_kernel_capability_policy(policy_path=...)` captures
the selected absolute path and asks the read-only storage adapter for one document.
Every implicit evaluation reads anew. Missing files, invalid JSON/encoding and
native I/O errors propagate; none becomes an empty policy or successful denial.
Execute-turn loads policy only for an enabled tool-call check; disabled and
no-tool-call turns retain their existing behavior without policy reads.
An invalid policy prevents the current turn's staging/promotion effects. It does
not roll back effects of earlier turns. An external writer must publish complete
files atomically if it needs atomic file replacement semantics.

Trusted Python callers may supply typed `policy_inputs` to `execute_turn`,
`resolve_capability`, `authorize_tool_call` and their validator counterparts.
Caller request JSON cannot select this typed argument. Requests detach before
policy I/O, and one captured policy provides both evidence and permissions.
Explicit resolve/authorize evaluation performs no policy I/O and is deterministic.
Implicit reads refuse a running event loop with
`E_KERNEL_POLICY_REQUIRES_ASYNC_OWNER`; synchronous execute-turn always refuses
one with `E_KERNEL_INVOCATION_REQUIRES_ASYNC_OWNER`. Use the existing owned worker
and application lifetime. `invoke_kernel` accepts JSON arguments; bind typed
inputs into the operation with `functools.partial` when using that worker helper.
The standard gateway and lifecycle API already use owned native invocation.
Interruption and close retain admitted workers; failure remains visible. Successful
staging may precede the caller receiving cancellation or timeout.

This legacy surface preserves caller-declared context permissions, policy source/
version overrides, `allow_tool_call` and enforcement/resolution flags. Those are
trusted/advisory inputs, not authenticated operator authority or proof that a tool
executed. The separate nervous-system admission policy and real capability broker
retain their own contracts. Local staging is not outward connector or model proof.

Remaining D work includes run identity, other Kernel filesystem inputs/effects,
complete adapter and async-reachability inventories and shared bridge lifetimes.
State remains volatile. This contract establishes neither durable recovery,
hostile-code containment, per-user authorization nor whole-lane acceptance.
