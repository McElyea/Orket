# Failure report publication

Last updated: 2026-09-28
Status: Active contract; scoped implementation/proof status is in the architectural truth plan
Owner: Orket Core

`FailureReporter.build_report` constructs the existing frozen value with explicit
timestamp and identity. `FailureReportService.publish` owns its artifact and saved
event. Its admitted concrete workspace is bound against the invocation directory
before the first await through the existing file-root capture policy. Rebinding
the service or changing CWD later cannot select another output root. Drive-relative
roots refuse explicitly. Native resolution and the existing resolved-path
containment checks remain authoritative; this is not handle-bound confinement.

Publication validates the portable card filename, captures scalar card/session
identity and renders the complete JSON document before awaiting native work.
The frozen model already refuses normal scalar assignment. Supported nested
`attempted_action` values are serialized at invocation; later nested mutation
cannot rewrite the admitted document. No arbitrary object/subclass snapshot or
frozen-model bypass guarantee is added.

The existing shared I/O owner retains the complete attempt through root/directory/
target resolution, parent creation, file open/write/close and required native
`policy_violation_report_saved` publication. The saved event follows actual report
closure and carries the same captured session/card and selected artifact path.
Cancellation or deadline cannot return before admitted native work settles;
native failure retains precedence. A failed saved-event acknowledgement can leave
both the report and appended log present. File failure cannot emit a saved event.
These diagnostic artifacts do not authorize completion, recovery or retry.

Application prepared logging context remains the logging-input authority. This
slice does not replace native standalone fallback policy, capture all ambient
logging environment/time inputs, or close other required publication producers.
Current source/installed proof and remaining D work live in
`docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`.
Original boundary: `docs/architecture/CONTRACT_DELTA_CORE_EFFECT_BOUNDARIES_D_2026-09-14.md`.
Capture migration: `docs/architecture/CONTRACT_DELTA_FAILURE_REPORT_CAPTURE_D_2026-09-28.md`.
