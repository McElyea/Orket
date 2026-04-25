$ErrorActionPreference = "Stop"
$Region = "us-east-1"
$Bucket = "orket-smoke-e32df7ff87a1"
$Key = "proof/terraform-plan.json"
$TableName = "TerraformReviewsSmoke_e32df7ff87a1"

if ($Bucket -like "<*") { throw "Replace the bucket placeholder before running cleanup." }
aws s3 rm "s3://$Bucket/$Key"
aws s3api delete-bucket --bucket $Bucket --region $Region
aws dynamodb delete-table --table-name $TableName --region $Region
aws dynamodb wait table-not-exists --table-name $TableName --region $Region
