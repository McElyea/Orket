$ErrorActionPreference = "Stop"

python -m orket_extension_sdk.validate . --json
python -m orket_extension_sdk.import_scan src --json
if (Get-Command orket -ErrorAction SilentlyContinue) {
    orket ext validate . --json
} else {
    $hasOrketModule = python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('orket') else 1)"
    if ($LASTEXITCODE -eq 0) {
        python -m orket.interfaces.orket_bundle_cli ext validate . --json
    } else {
        Write-Host "Skipping host CLI extension validation (orket CLI/package unavailable)."
    }
}
$env:PYTHONPATH = "src"
python -m pytest -q tests/

Write-Host "Validation complete."
