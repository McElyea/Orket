$ErrorActionPreference = "Stop"
$Region = "us-west-2"
$Bucket = "orket-smoke-proof-bucket-123456"
$Key = "proof/terraform-plan.json"
$TableName = "TerraformReviewsSmoke"
$PlanPath = "C:\Source\Orket\manual_tmp_test\pytest_run_fresh_0423b\test_setup_packet_with_real_re0\packet\terraform-plan-safe-smoke.plan.json"
$SmokeOwnerMarker = ""

if ($Bucket -like "<*") { throw "Replace the bucket placeholder before running setup." }
if ($Region -eq "us-east-1") {
  aws s3api create-bucket --bucket $Bucket --region $Region
} else {
  aws s3api create-bucket --bucket $Bucket --region $Region --create-bucket-configuration "LocationConstraint=$Region"
}
aws s3api put-public-access-block --bucket $Bucket --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
aws s3api put-object --bucket $Bucket --key $Key --body $PlanPath --metadata "orket-smoke-owner=$SmokeOwnerMarker"
aws dynamodb create-table --table-name $TableName --region $Region --billing-mode PAY_PER_REQUEST --attribute-definitions AttributeName=plan_hash,AttributeType=S --key-schema AttributeName=plan_hash,KeyType=HASH
aws dynamodb wait table-exists --table-name $TableName --region $Region
