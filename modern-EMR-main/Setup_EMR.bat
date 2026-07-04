@echo off
title Setup Endocrinology EMR
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install from https://www.python.org/downloads/
    pause
    exit /b 1
)

if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo Installing dependencies...
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Install failed.
    pause
    exit /b 1
)

echo.
echo Creating database and sample data...
"%PY%" populate_sample_data.py

echo.
echo Setup complete.
echo Double-click "Start_EMR.bat" or the desktop shortcut to run the app.
echo.
pause
