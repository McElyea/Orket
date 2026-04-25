# NorthStar Disposable AWS Smoke Operator Runbook

Last updated: 2026-04-24
Status: Active operator runbook

This runbook creates disposable live inputs for the paused NorthStar Terraform admission lane.
It does not admit `trusted_terraform_plan_decision_v1` publicly.

## Safe Order

1. Generate packet:
   `python scripts/proof/prepare_northstar_disposable_aws_smoke_packet.py --seed <seed> --fixture-kind safe --fixture-seed <fixture-seed>`
2. Validate fixture:
   `python scripts/proof/check_trusted_terraform_plan_fixture.py --plan-fixture workspace/trusted_terraform_live_setup/terraform-plan.json --metadata workspace/trusted_terraform_live_setup/terraform-plan-fixture-metadata.json`
3. Run no-spend preflight:
   `python scripts/proof/check_trusted_terraform_live_setup_preflight.py --packet-dir workspace/trusted_terraform_live_setup`
4. Execute AWS setup:
   `python scripts/proof/run_trusted_terraform_disposable_aws_setup.py --packet-dir workspace/trusted_terraform_live_setup --execute-live-aws --acknowledge-cost-and-mutation`
5. Load env:
   `. workspace/trusted_terraform_live_setup/live-run-env.ps1.template`
6. Run runtime smoke:
   `python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json`
7. Run publication gate:
   `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py`
8. Cleanup:
   `python scripts/proof/run_trusted_terraform_disposable_aws_cleanup.py --packet-dir workspace/trusted_terraform_live_setup --execute-live-aws --acknowledge-delete`
9. Write handoff:
   `python scripts/proof/write_northstar_trusted_terraform_smoke_handoff.py`
10. Verify hygiene:
   `python scripts/governance/check_docs_project_hygiene.py`

## Boundaries

The AWS setup runner is inert unless both live setup flags are present.
The cleanup runner is inert unless both cleanup flags are present.
Setup success, fixture generation success, and preflight success are not admission evidence.
Only a successful provider-backed runtime smoke can produce live smoke evidence, and NorthStar admission still requires the dependent same-change proof envelope rerun.
