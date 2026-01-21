@echo off
REM Content Generation Cron Job Runner for Windows
REM This script runs the content generation cron job

echo ========================================
echo Starting Content Generation Cron Job...
echo Time: %DATE% %TIME%
echo ========================================

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo [+] Activating virtual environment...
    call venv\Scripts\activate.bat
    if errorlevel 1 (
        echo [-] ERROR: Failed to activate virtual environment
        goto :error
    )
    echo [+] Virtual environment activated successfully
) else (
    echo [-] WARNING: Virtual environment not found at venv\Scripts\activate.bat
    echo [-] Using system Python installation
)

REM Check Python availability
python --version >nul 2>&1
if errorlevel 1 (
    echo [-] ERROR: Python is not available in PATH
    goto :error
)

echo [+] Python version:
python --version

REM Run the cron job
echo.
echo ========================================
echo Running content generation cron job...
echo ========================================
python content_generation_cron.py

REM Check exit code
if errorlevel 1 (
    echo [-] ERROR: Cron job exited with error code %errorlevel%
    goto :error
) else (
    echo [+] SUCCESS: Cron job completed successfully
)

echo.
echo ========================================
echo Content Generation Cron Job completed.
echo Time: %DATE% %TIME%
echo ========================================
goto :end

:error
echo.
echo ========================================
echo CRON JOB FAILED!
echo Check the error messages above.
echo ========================================
pause
exit /b 1

:end
echo Press any key to close this window...
pause >nul