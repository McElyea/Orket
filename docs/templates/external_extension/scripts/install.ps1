$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($env:ORKET_SDK_INSTALL_SPEC)) {
    throw "Set ORKET_SDK_INSTALL_SPEC to a pip install spec for orket-extension-sdk."
}

python -m pip install --upgrade pip
python -m pip install $env:ORKET_SDK_INSTALL_SPEC

if (-not (Get-Command orket -ErrorAction SilentlyContinue)) {
    if ([string]::IsNullOrWhiteSpace($env:ORKET_HOST_INSTALL_SPEC)) {
        throw "The orket CLI is required. Install it first or set ORKET_HOST_INSTALL_SPEC."
    }
    python -m pip install $env:ORKET_HOST_INSTALL_SPEC
}

python -m pip install -e ".[dev]"

Write-Host "Install complete."
