# Sandbox deployment publication recovery

Owner: Orket Core. Date: 2026-09-19. Effective version: 0.6.37 (patch).
Status: active contract; proof disposition remains in the architectural-truth plan.

## Delta

Deployment verification updates lifecycle state, resource state, lease and effect
journal through separate publications. Previously, a lease timestamp rejection
after the ACTIVE transition left no deployment journal entry. A subsequent healthy
retry renewed the lease and resource but returned success without repairing the
missing deployment evidence. Retained native observations and a controlled clock
regression reproduce this gap; the physical clock adjustment source is unknown.

For an owned ACTIVE sandbox, `handle_healthy` captures one observation timestamp,
renews the lifecycle lease, publishes the shared lease and resource, and invokes
the existing idempotent deployment-effect publisher before returning. A healthy
retry can repair an interrupted deployment publication. Existing entries remain
unchanged; repeated health observations do not append duplicate deployment effects
for the same sandbox lease epoch. Publication refusal remains a failure. The lease
timestamp monotonicity guard is unchanged.

The orchestrator must observe the live runtime as healthy before this transition.
Lifecycle ACTIVE alone does not prove successful deployment publication. These
operations remain separate database publications, without a cross-store atomicity
or crash-recovery guarantee. This change does not admit hostile sandbox execution
or establish application-level readiness beyond the existing runtime health checks.

## Migration and validation

No caller signature, schema or stored-record migration is required. Existing ACTIVE
records missing their deployment journal can recover on a successful owned health
check when run/attempt authority exists. Missing authority still refuses publication.

Keep regressions for timestamp reversal, native SQLite journal-write refusal,
successful retry and journal idempotence in both Quality selections. Controlled
Docker observations prove the database path only; explicit live acceptance must
also exercise actual Docker observation and verify teardown in the same execution.

## Rollback

If recovery publishes incorrect authority, stop affected sandbox work and inspect
retained lifecycle, lease, resource and journal records before restoration. Restore
the service and contract together under a new patch version; do not delete evidence
or treat a failed acknowledgement as proof that no effect occurred. Reverting the
repair reopens the successful-retry-with-missing-journal defect.
