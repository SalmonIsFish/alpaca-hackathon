@echo off
REM Alpaca Trading Scheduler - Windows Batch File
REM Usage: run_scheduler.bat [interval_minutes] [--dry-run]

echo ================================================
echo ALPACA TRADING SCHEDULER
echo ================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    exit /b 1
)

REM Parse arguments
set INTERVAL=60
set DRY_RUN=

:parse_args
if "%~1"=="" goto :done_parsing
if "%~1"=="--dry-run" (
    set DRY_RUN=--dry-run
    shift
    goto :parse_args
)
if "%~1"=="--interval" (
    set INTERVAL=%~2
    shift
    shift
    goto :parse_args
)
if "%~1"=="--profile" (
    set PROFILE=%~2
    shift
    shift
    goto :parse_args
)
REM If it's a number, use it as interval
echo %~1 | findstr /r "^[0-9]*$" >nul
if %errorlevel%==0 (
    set INTERVAL=%~1
)
shift
goto :parse_args

:done_parsing

echo Configuration:
echo   Interval: %INTERVAL% minutes
if not "%DRY_RUN%"=="" (
    echo   Mode: DRY RUN (no real orders)
) else (
    echo   Mode: LIVE (real orders will be placed)
)
echo.
echo Press Ctrl+C to stop the scheduler
echo ================================================
echo.

REM Run the scheduler
if not "%PROFILE%"=="" (
    python run_scheduler.py --start --interval %INTERVAL% %DRY_RUN% --profile %PROFILE%
) else (
    python run_scheduler.py --start --interval %INTERVAL% %DRY_RUN%
)

echo.
echo Scheduler stopped.
pause
