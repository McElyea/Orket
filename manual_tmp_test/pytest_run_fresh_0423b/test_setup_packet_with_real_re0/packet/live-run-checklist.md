# Trusted Terraform Live Setup Checklist

This packet is setup assistance only. It is not provider-backed proof evidence.

1. Replace the bucket placeholder with a globally unique bucket name.
2. Configure AWS credentials outside the repository using the standard AWS provider chain.
3. Run `aws-cli-setup-commands.ps1` only when you are ready to create the low-cost S3 and DynamoDB resources.
4. Load `live-run-env.ps1.template` values into the shell that will run Orket proof commands.
5. Run `python scripts/proof/check_trusted_terraform_live_setup_preflight.py` before the live smoke; unreplaced S3 placeholders must stay blocked.
6. Run `python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json` only after preflight passes.
7. Run `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py` after a successful provider-backed governed proof run.
8. Run `aws-cli-cleanup-commands.ps1` after the live attempt unless you intentionally keep the resources.

Planned S3 URI: `s3://orket-smoke-proof-bucket-123456/proof/terraform-plan.json`
Planned DynamoDB table: `TerraformReviewsSmoke`
Planned Bedrock model or inference-profile id: `us.amazon.nova-lite-v1:0`
Planned Bedrock inference operation: `Converse`
Expected plan hash: `not-recorded`
Smoke owner marker: `not-recorded`
