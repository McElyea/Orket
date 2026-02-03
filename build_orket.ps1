Param(
    [string]$Root = ".\orket"
)

$ErrorActionPreference = "Stop"

Write-Host "Creating project at $Root"

# Directories
$dirs = @(
    "$Root",
    "$Root\orket",
    "$Root\tools",
    "$Root\tests",
    "$Root\workspace",
    "$Root\task_memory",
    "$Root\docs"
)

foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

# Core files (empty placeholders – paste code after generation)
$files = @(
    "README.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "NOTICE",
    ".gitignore",
    "config.json",
    "main.py",

    "orket\__init__.py",
    "orket\orchestrator.py",
    "orket\agents.py",
    "orket\tools.py",
    "orket\utils.py",

    "tools\__init__.py",
    "tools\python_exec.py",

    "tests\__init__.py",

    "docs\architecture.md",
    "docs\security.md",
    "docs\examples.md"
)

foreach ($f in $files) {
    $path = Join-Path $Root $f
    if (-not (Test-Path $path)) {
        New-Item -ItemType File -Path $path | Out-Null
        Write-Host "Created $path"
    } else {
        Write-Host "Exists  $path"
    }
}

Write-Host "Done. Paste code into the created files."