$ErrorActionPreference = "Stop"
$Region = "us-east-1"
$Bucket = "<replace-with-globally-unique-smoke-bucket>"
$Key = "orket/trusted-terraform-plan-decision/terraform-plan-safe-smoke.plan.json"
$TableName = "TerraformReviews"

if ($Bucket -like "<*") { throw "Replace the bucket placeholder before running cleanup." }
aws s3 rm "s3://$Bucket/$Key"
aws s3api delete-bucket --bucket $Bucket --region $Region
aws dynamodb delete-table --table-name $TableName --region $Region
aws dynamodb wait table-not-exists --table-name $TableName --region $Region
