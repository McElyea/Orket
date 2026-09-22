# Provider inventory and governance command ownership

Last updated: 2026-09-22
Status: Implementation contract; acceptance remains in the architectural-truth plan

Provider inventory and Packet 1 governance commands must retain admitted native
processes and descendants until their actual lifetime settles. Leader exit alone
cannot establish command completion. Use the existing package-owned OS supervisor;
do not add a direct-child fallback or a second process ownership implementation.

Native inventory entry refuses event-loop execution before effects. Application
callers retain its native worker through interruption; finite command deadlines
and the supervisor's cleanup deadline still apply. Worker failures take precedence
over waiter cancellation. Async governance commands propagate interruption to their
command owner and retain cleanup through repeated cancellation.

Capture command arguments, invocation directory and environment before dispatch.
Preserve inventory parsing, command output decoding, explicit model-load observation
and alias ownership. Output truncation, unavailable containment or uncertain cleanup
must refuse rather than return a normal command result. Inventory caller budgets
remain authoritative, including the existing one-second minimum. Governance commands
have a 300-second default budget; individual invocations may supply a finite budget.
Both use the existing supervisor's 4 MiB output bound. Inventory retains text-mode
newline normalization; governance retains its existing byte-to-text decoding.
Uncertain cleanup or incomplete capture raises the shared typed command uncertainty;
other incomplete inventory commands raise the existing warmup error, while incomplete
governance commands raise an explicit error instead of a normal return tuple. A refused
launch with confirmed cleanup is an ordinary command error: no output was admitted for
capture. Failed cleanup still takes precedence over that launch failure.

Retained process termination does not prove rollback of model loads or alias changes,
daemon-side effects, cross-process alias exclusivity, interrupted-copy reconciliation,
or model inference. Existing ownership rules still remove only aliases successfully
created by this invocation, and unsuccessful removal remains visible.

Acceptance requires actual ordinary and detached descendant trees, successful and
failed leaders, finite timeout, cancellation and repeated cancellation, independently
observed stopped effects, preserved output/parse/refusal behavior, and installed
artifact binding. Actual Ollama acceptance remains a separate unmet live obligation.
No Linux clock repair, full D/E/CAP completion or lane retirement follows from this scope.
