# Windows scope amendment history

Date: 2026-10-03 (America/Denver)
Status: Historical reference; no execution authority

The user explicitly directed: "Lets remove the blocker from the plan and stop
trying to support linux if this is working in windows".

`PLAN_BEFORE_WINDOWS_SCOPE.md` preserves the exact v0.6.141 canonical plan bytes
from commit `175e5d58bb7159888b1a82882401083432de9547` before that correction.
SHA256: `a09908e03eff66a74d548f3fbd9b2043864260a6dc61d3f7a0a03fd842285714`.
Its Linux, clock, hosted-runner and eleven-job requirements are historical;
the active plan now defines Windows-only ATG-v1 acceptance. Old failed or missing
results remain failed or missing. Removing their obligation does not make them pass.

Continue only from the active [canonical plan](../../../architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md).
The original attempt receipts and workset observations remain retained as history.
