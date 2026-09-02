# Alpaca Trading Scheduler - PowerShell Script
# Usage: .\run_scheduler.ps1 [-IntervalMinutes 60] [-DryRun] [-Profile <profile>]

param(
    [int]$IntervalMinutes = 60,
    [switch]$DryRun,
    [string]$Profile = ""
)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "ALPACA TRADING SCHEDULER" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Interval: $IntervalMinutes minutes"
if ($DryRun) {
    Write-Host "  Mode: DRY RUN (no real orders)" -ForegroundColor Green
} else {
    Write-Host "  Mode: LIVE (real orders will be placed)" -ForegroundColor Red
}
Write-Host ""
Write-Host "Press Ctrl+C to stop the scheduler" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Build arguments
$args = @("--start", "--interval", $IntervalMinutes)
if ($DryRun) {
    $args += "--dry-run"
}
if ($Profile) {
    $args += "--profile"
    $args += $Profile
}

# Run the scheduler
try {
    & python run_scheduler.py @args
} catch {
    Write-Host "Error running scheduler: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Scheduler stopped." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
