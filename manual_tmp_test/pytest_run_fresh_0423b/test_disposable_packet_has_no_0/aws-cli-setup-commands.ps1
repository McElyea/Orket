$ErrorActionPreference = "Stop"
$Region = "us-east-1"
$Bucket = "orket-smoke-8804d8890306"
$Key = "proof/terraform-plan.json"
$TableName = "TerraformReviewsSmoke_8804d8890306"
$PlanPath = "C:\Source\Orket\manual_tmp_test\pytest_run_fresh_0423b\test_disposable_packet_has_no_0\terraform-plan-safe-smoke.plan.json"
$SmokeOwnerMarker = "northstar-disposable-aws-smoke:8804d8890306"

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
