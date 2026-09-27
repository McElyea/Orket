# Supporting runtime failure diagnostics

Status: Accepted target contract; implementation and scoped acceptance pending
Last updated: 2026-09-27
Owner: Orket Core

The scope is the cancellation-drain warning in `owned_io`, API preparation and
acquired-resource cleanup, `ApplicationRuntimeLifetime` managed background and
teardown diagnostics, and the directly nested runtime-resource cleanup diagnostic.
These observations support an already failed operation; they do not establish
success, cleanup, readiness, authorization or a durable effect.

The existing native task/worker owner retains one admitted diagnostic attempt
through completion, repeated cancellation and caller timeout. A standard logging
handler runs natively with the owning invocation context. A handler that never
returns can keep the caller and application close pending. No forced stop or
shutdown deadline is introduced.

The primary/native outcome is selected before the supporting diagnostic. Native
failure retains precedence where `preserve_failure=True`; the first caller
cancellation retains precedence where that flag is false. A successful operation
after caller interruption still propagates cancellation. Existing cooperative
operation cancellation and non-cancelled failure branches retain their behavior.

Supporting handler/executor failure never replaces that selected exception.
At most one fixed `E_OWNED_DIAGNOSTIC_FAILED` note is added through the base
exception implementation. No diagnostic message, payload, label, representation,
handler identity or secondary exception is attached. Existing exception identity,
cause, context and prior notes remain. This is a failure disclosure marker, not
complete diagnostic history, durable retention or delivery acknowledgement.
There is no recursive attempt to log failure of a supporting diagnostic.
This guarantee assumes ordinary exception attribute state and a normal notes
list. Calling `BaseException.add_note` directly bypasses a public `add_note`
override. Exception state remains borrowed and additively mutated; hostile
attribute hooks, malformed notes and concurrent external mutation are outside
this bounded contract and receive no compatibility fallback.

The owner captures the bound logger method before its relevant first wait and
binds message, supplied arguments, extra fields and the explicit exception triple
before native dispatch. Logger and exception identities remain borrowed; their
resources are never deep-copied. Capture does not freeze later handler/configuration
changes. Custom handlers on these paths must support native worker invocation.

Preparation and close supervisors retain the primary error before diagnostic
work, and attempt every declared remaining peer and final resource. Existing
cleanup order, close-capability preference, error grouping and API teardown
representation stay authoritative. Diagnostic failure does not add a resource
failure, erase the original, or mark an unsuccessfully closed resource closed.
An error already retained as the managed-background cause is not counted twice
solely because its diagnostic is draining when teardown starts.

Managed background failure closes new application admission immediately. Its
diagnostic remains part of the existing tracked background task, and close drains
it before resources. Done callbacks perform only outcome/bookkeeping observation;
they do not execute native handlers or launch untracked diagnostic tasks. Each
application retains its own tasks and resources, not the process logging writer.

Required proof combines actual API preparation/lifespan, acquired real SQLite
connections, healthy and failing standard handlers, repeated caller cancellation,
explicit context capture and an independent SQLite responsiveness bound fixed
before measurement. Runtime tests inspect resource state before emergency fixture
cleanup. Opening/closing and installed/native-platform results belong to the
architectural-truth plan; this contract alone is not proof of any of them.

Other logging producers, optional publication/preparation, arbitrary synchronous
close ports, abrupt process death and complete D ownership remain separate work.
