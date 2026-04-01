$ErrorActionPreference = "Stop"

if (-not (Get-Command orket -ErrorAction SilentlyContinue)) {
    throw "The orket CLI is required for host validation."
}

python -m orket_extension_sdk.validate . --strict --json
python -m orket_extension_sdk.import_scan src --json
orket ext validate . --strict --json
python -m pytest -q tests/

Write-Host "Validation complete."
