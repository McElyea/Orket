# Jon Orket NorthStar IAM Migration

Last updated: 2026-04-24

`update_jon_orket_northstar_iam.ps1` moves Orket/NorthStar direct IAM user permissions for `Jon` into one customer-managed policy named `OrketNorthstarWork`.

Inline user policies are removed because IAM user inline policies have a small 2,048 non-whitespace character aggregate limit. The Orket/NorthStar Bedrock, Service Quotas, STS, and scoped S3 permissions fit more safely in a customer-managed IAM policy, where the policy document limit is 6,144 non-whitespace characters and versioned updates are available.

The mutation boundary is intentionally narrow:

1. create or update the customer-managed policy `OrketNorthstarWork`,
2. attach that policy directly to IAM user `Jon`,
3. only after attachment is visible, delete inline policies directly on `Jon`,
4. detach directly attached managed policies from `Jon` except `OrketNorthstarWork`.

The script does not modify IAM groups, group-attached policies, roles, access keys, MFA devices, root account settings, S3 buckets, Bedrock resources, DynamoDB tables, or Terraform state.

If the active AWS caller is the target IAM user and the saved inventory shows no group memberships, the script refuses the old direct-policy removal phase after attaching `OrketNorthstarWork`. That prevents a same-user run from removing its own IAM authority before cleanup and final verification can complete. Use a separate administrator principal for the full delete/detach phase.

If the user already has 10 directly attached managed policies and `OrketNorthstarWork` is not already attached, the script stops after inventory because AWS will reject the required attach-before-remove ordering at the `PoliciesPerUser` quota. Freeing that attachment slot requires an operator decision outside this script's safe ordering.

Use `-DryRun` to write the generated policy JSON and planned AWS CLI command list without executing AWS CLI commands. Real IAM mutation requires `-ExecuteIamMutation`.

This IAM helper only prepares operator permissions. Orket live AWS mutation and delete flows still require their explicit runtime opt-in flags, such as `--execute-live-aws --acknowledge-cost-and-mutation` for setup and `--execute-live-aws --acknowledge-delete` for cleanup.
