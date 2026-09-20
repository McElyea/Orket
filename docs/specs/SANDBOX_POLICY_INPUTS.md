# Sandbox policy inputs

Status: Active
Last updated: 2026-09-20
Owner: Orket Core

Application `sandbox_policy_input_service` owns policy input capture and result
admission. At `create_sandbox` entry, before its first await, it captures the
selected policy, creation timestamp and two fresh secret tokens through
`RuntimeInputService`. The constructor's explicit environment also supplies the
decision registry. These observations belong to this invocation; later registry
or secret-source changes do not replace them.

Custom `get_database_url` implementations receive the tech-stack string value,
a frozen `SandboxPortInput`, and the captured database password. The frozen port
projection inherits the authoritative port fields without borrowing allocator
state. Custom `generate_compose_file` receives `SandboxComposeInput`: id, rock_id,
tech-stack string and frozen ports. It receives database/admin passwords as
explicit arguments. Workspace paths, container handles and the mutable runtime
Sandbox are absent. Direct `_generate_compose_file` calls capture their policy
and any missing admin token at their own call boundary; creation supplies the
earlier captured values explicitly.

Sandbox id, compose project, database URL and compose text recommendations must be
plain strings. Existing empty-string behavior is preserved. Unknown or unsupported
tech stacks retain the default refusal; diagnostics now display string values.
Supported default URLs and compose text retain prior output bytes for identical
explicit inputs. This change adds no credential persistence or rotation protocol.

If policy admission fails after a fresh in-memory port allocation, the application
releases only that allocation. Existing allocations survive and the allocation
counter is not rewound. Failure to allocate does not release another reservation.
Once durable creation publications have begun, later compose refusal preserves
their evidence. Existing lifecycle handling retains the `starting` record with
`requires_reconciliation=true`; it does not invent a successful deployment or
silently undo prior publications.

These are trusted in-process value contracts, not hostile-code containment or an
atomic snapshot of all runtime state. Later lifecycle clocks, deployment, health,
lease fencing and teardown retain their existing owners and deadlines. Fresh
secret values must not be retained in verification receipts; parity fixtures use
synthetic inputs. Scoped source, installed and Docker observations belong in the
canonical architectural-truth plan, with their actual proof limits.
