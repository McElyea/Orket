#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

git config core.hooksPath .githooks
Write-Host "Configured git hooks path to .githooks"
