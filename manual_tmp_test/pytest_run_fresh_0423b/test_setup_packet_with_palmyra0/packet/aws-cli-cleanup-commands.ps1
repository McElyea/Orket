$ErrorActionPreference = "Stop"
$Region = "us-east-1"
$Bucket = "orket-smoke-proof-bucket-123456"
$Key = "proof/terraform-plan.json"
$TableName = "TerraformReviewsSmoke"

if ($Bucket -like "<*") { throw "Replace the bucket placeholder before running cleanup." }
aws s3 rm "s3://$Bucket/$Key"
aws s3api delete-bucket --bucket $Bucket --region $Region
aws dynamodb delete-table --table-name $TableName --region $Region
aws dynamodb wait table-not-exists --table-name $TableName --region $Region
