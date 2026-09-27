# Sandbox cleanup observation

Status: Active
Last updated: 2026-09-27
Owner: Orket Core

Each preview or claimed cleanup obtains one compose-path availability observation
through the existing owned native worker. The same boolean supplies cleanup
authorization and the emitted decision receipt. Decision projection receives that
explicit value and performs no filesystem observation.

Cancellation after metadata admission waits for the native observation to settle.
It prevents subsequent decision publication and cleanup dispatch in that call;
earlier claim, attempt and inventory records can already be durable. Native failure
remains visible, including failure while draining cancellation. Recovery continues
to use existing cleanup claims and reconciliation; this is not a rollback promise.

Availability is the observed existence of the selected compose path. It does not
pin its contents or prevent later replacement/removal. Compose commands, label
authority, fallback selection and post-cleanup absence verification retain their
existing contracts. A preview is advisory and does not establish Docker teardown.

Direct `SandboxCleanupDecisionService.build_decision` callers supply
`compose_path_available` instead of `compose_path`. External decision/event payloads
are unchanged. The application cleanup service owns the actual observation.
