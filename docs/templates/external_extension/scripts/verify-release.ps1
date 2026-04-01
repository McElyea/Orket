param(
    [string]$Tag = ""
)

$ErrorActionPreference = "Stop"

$args = @("scripts/check_release.py", "--dist-dir", "dist", "--json")
if (-not [string]::IsNullOrWhiteSpace($Tag)) {
    $args += @("--tag", $Tag)
}

python @args

Write-Host "Release verification complete."
