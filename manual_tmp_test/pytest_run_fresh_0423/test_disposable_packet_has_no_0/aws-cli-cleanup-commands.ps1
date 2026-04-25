$ErrorActionPreference = "Stop"
$Region = "us-east-1"
$Bucket = "orket-smoke-8804d8890306"
$Key = "proof/terraform-plan.json"
$TableName = "TerraformReviewsSmoke_8804d8890306"

if ($Bucket -like "<*") { throw "Replace the bucket placeholder before running cleanup." }
aws s3 rm "s3://$Bucket/$Key"
aws s3api delete-bucket --bucket $Bucket --region $Region
aws dynamodb delete-table --table-name $TableName --region $Region
aws dynamodb wait table-not-exists --table-name $TableName --region $Region
