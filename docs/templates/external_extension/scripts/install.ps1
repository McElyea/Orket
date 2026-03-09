$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

Write-Host "Install complete."
