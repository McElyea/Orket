$ErrorActionPreference = "Stop"

if (Test-Path dist) {
    Remove-Item -Recurse -Force dist
}

python -m build --sdist --outdir dist .

Write-Host "Release build complete."
