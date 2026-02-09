# Setup Windows Task Scheduler for Daily Gitea Backups
# Run as Administrator

$ErrorActionPreference = "Stop"

Write-Host "🔧 Setting up Windows Task Scheduler for Gitea backups..." -ForegroundColor Cyan

# Configuration
$TaskName = "Orket-Gitea-Daily-Backup"
$ScriptPath = "C:\Source\Orket\scripts\backup_gitea.sh"
$BackupTime = "03:00"  # 3:00 AM

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Check if bash is available
$bashPath = (Get-Command bash -ErrorAction SilentlyContinue).Path
if (-not $bashPath) {
    Write-Host "❌ ERROR: bash not found in PATH" -ForegroundColor Red
    Write-Host "Install Git Bash or WSL first" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Found bash at: $bashPath" -ForegroundColor Green

# Check if script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "❌ ERROR: Backup script not found at: $ScriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Found backup script" -ForegroundColor Green

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "🗑️  Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create action (run bash script)
$action = New-ScheduledTaskAction `
    -Execute $bashPath `
    -Argument "$ScriptPath" `
    -WorkingDirectory "C:\Source\Orket"

# Create trigger (daily at specified time)
$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $BackupTime

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Create principal (run as current user)
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Limited

# Register task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Daily backup of Gitea repositories and database (Orket)"

Write-Host ""
Write-Host "✅ Task created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Task Details:" -ForegroundColor Cyan
Write-Host "   Name:     $TaskName"
Write-Host "   Schedule: Daily at $BackupTime"
Write-Host "   Script:   $ScriptPath"
Write-Host "   User:     $env:USERNAME"
Write-Host ""
Write-Host "🔍 To view task:" -ForegroundColor Yellow
Write-Host "   Get-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "▶️  To run manually:" -ForegroundColor Yellow
Write-Host "   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "🗑️  To remove:" -ForegroundColor Yellow
Write-Host "   Unregister-ScheduledTask -TaskName '$TaskName'"
Write-Host ""

# Ask if user wants to run backup now
$runNow = Read-Host "Run backup now to test? (y/n)"
if ($runNow -eq "y" -or $runNow -eq "Y") {
    Write-Host ""
    Write-Host "🚀 Running backup now..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName

    # Wait a moment for task to start
    Start-Sleep -Seconds 2

    # Check task status
    $task = Get-ScheduledTask -TaskName $TaskName
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName

    Write-Host "   Status: $($task.State)" -ForegroundColor Green
    Write-Host "   Last Run: $($taskInfo.LastRunTime)" -ForegroundColor Green
    Write-Host ""
    Write-Host "✅ Backup initiated! Check backups/gitea/ for output" -ForegroundColor Green
}

Write-Host ""
Write-Host "🎉 Setup complete!" -ForegroundColor Green
