# Orket Docs Index

Last reviewed: 2026-04-01

This index is the canonical map for `docs/*.md` (excluding `docs/projects/**`).

## Canonical Root Docs
1. `docs/ROADMAP.md`
   - Active execution priority and project index.
2. `docs/ARCHITECTURE.md`
   - Runtime layers, dependency direction, and decision-node boundaries.
3. `docs/RUNBOOK.md`
   - Operator startup, health checks, and incident response.
4. `docs/SECURITY.md`
   - API/webhook trust boundary and required posture.
5. `docs/TESTING_POLICY.md`
   - Test lanes and required command set.
6. `docs/API_FRONTEND_CONTRACT.md`
   - Implemented API and websocket surface expected by UI clients.
7. `docs/CONTRIBUTOR.md`
   - Contributor workflow and operating protocol.

## Requirements
1. `docs/requirements/sdk/VERSIONING.md`
   - SDK version source-of-truth and tag policy.

## Specifications
1. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
2. `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md`
3. `docs/specs/RUNTIME_INVARIANTS.md`
4. `docs/specs/TOOL_CONTRACT_TEMPLATE.md`
5. `docs/specs/OFFLINE_CAPABILITY_MATRIX.md`
6. `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`
7. `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
8. `docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md`
9. `docs/specs/PROTOCOL_ERROR_CODE_REGISTRY.md`
10. `docs/specs/PROTOCOL_REPLAY_CAMPAIGN_SCHEMA.md`
11. `docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md`
12. `docs/specs/WORKLOAD_CONTRACT_V1.md`
13. `docs/specs/workload-contract-v1.schema.json`
14. `docs/specs/SIDECAR_PARSE_SCHEMA.md`
15. `docs/specs/REVIEW_RUN_V0.md`
16. `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
17. `docs/specs/EXPLORER_SCHEMA_POLICY.md`
18. `docs/specs/EXPLORER_FRONTIER_SCHEMA.md`
19. `docs/specs/EXPLORER_CONTEXT_CEILING_SCHEMA.md`
20. `docs/specs/EXPLORER_THERMAL_STABILITY_SCHEMA.md`
21. `docs/specs/COMPANION_UI_MVP_CONTRACT.md`
22. `docs/specs/COMPANION_AVATAR_POST_MVP_CONTRACT.md`
23. `docs/specs/ORKET_OPERATING_PRINCIPLES.md`
24. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
25. `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`
26. `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`
27. `docs/specs/CORE_RELEASE_PROOF_REPORT.md`
28. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
29. `docs/specs/TRUTHFUL_RUNTIME_REPAIR_LEDGER_CONTRACT.md`
30. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`
31. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`
32. `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`
33. `docs/specs/TRUTHFUL_RUNTIME_MEMORY_TRUST_CONTRACT.md`
34. `docs/specs/TRUTHFUL_RUNTIME_CONFORMANCE_GOVERNANCE_CONTRACT.md`
35. `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`
36. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
37. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
38. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
39. `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`
40. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
41. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
42. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md`

## Process
1. `docs/process/PR_REVIEW_POLICY.md`
2. `docs/process/PUBLISHED_ARTIFACTS_POLICY.md`
3. `docs/process/PRODUCT_PUBLISHING.md`
4. `docs/process/LOCAL_CLEANUP_POLICY.md`
5. `docs/process/GITEA_WEBHOOK_SETUP.md`
6. `docs/process/GITEA_STATE_OPERATIONAL_GUIDE.md`
7. `docs/process/GITEA_BACKUP_STRATEGY.md`
8. `docs/process/FAILURE_RECOVERY.md`
9. `docs/process/QUANT_SWEEP_RUNBOOK.md`
10. `docs/process/GITEA_MONOREPO_CI_TEMPLATE.md`
11. `docs/process/requirement-refactor-loop-template.md`
12. `docs/process/decision-log-template.md`

## Observability
1. `docs/observability/BENCHMARK_DETERMINISM.md`
2. `docs/observability/BENCHMARK_FAILURE_LEDGER.md`
3. `docs/observability/bottleneck_thresholds.md`
4. `docs/observability/stream_scenarios.md`
5. `docs/observability/textmystery_bridge.md`

## Guides and Context
1. `docs/guides/CONTRIBUTOR-MENTAL-MODEL.md`
2. `docs/guides/examples.md`
3. `docs/guides/PROJECT.md`
4. `docs/guides/external-extension-authoring.md`

## Architecture Deep Dives
1. `docs/architecture/ADR-0001-volatility-tier-boundaries.md`
2. `docs/architecture/CONTRACT_BREAK_WORKFLOW.md`
3. `docs/architecture/CONTRACT_DELTA_TEMPLATE.md`
4. `docs/architecture/ARCHITECTURE_COMPLIANCE_CHECKLIST.md`
5. `docs/architecture/event_taxonomy.md`
6. `docs/architecture/CONTRACT_DELTA_TRUTHFUL_RUNTIME_PACKET1_BOUNDARY_REALIGNMENT_2026-03-15.md`
7. `docs/architecture/CONTRACT_DELTA_TRUTHFUL_RUNTIME_PHASE_C_CLOSEOUT_2026-03-16.md`
8. `docs/architecture/CONTRACT_DELTA_TRUTHFUL_RUNTIME_PHASE_D_CLOSEOUT_2026-03-17.md`
9. `docs/architecture/CONTRACT_DELTA_TRUTHFUL_RUNTIME_PHASE_E_CLOSEOUT_2026-03-17.md`
10. `docs/architecture/CONTRACT_DELTA_TERRAFORM_PLAN_REVIEWER_V1_2026-03-22.md`
11. `docs/architecture/CONTRACT_DELTA_RUN_EVIDENCE_GRAPH_V1_CLOSEOUT_2026-03-30.md`
12. `docs/architecture/CONTRACT_DELTA_RUN_EVIDENCE_GRAPH_V1_APPENDIX_SYNC_2026-03-30.md`
13. `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_PACKET1_APPROVAL_SLICE_REALIGNMENT_2026-03-31.md`
14. `docs/architecture/dependency_graph_snapshot.md`
15. `docs/architecture/VOLATILITY_BASELINE.md`
16. `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_SESSION_CONTINUITY_CLOSEOUT_2026-04-01.md`
17. `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_WRITE_FILE_APPROVAL_CONTINUATION_2026-04-01.md`
18. `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_HARDENING_2026-04-01.md`
19. `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_HARDENING_2026-04-01.md`

## Projects
1. Active plans: `docs/projects/<project>/`
2. Historical records: `docs/projects/archive/`
3. Long-lived contracts and schemas: `docs/specs/`
