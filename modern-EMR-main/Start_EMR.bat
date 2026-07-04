@echo off
title Endocrinology EMR
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Python was not found.
    echo  Install Python 3.10+ from https://www.python.org/downloads/
    echo  During install, check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo.
echo  ========================================
echo    Endocrinology EMR
echo  ========================================
echo.
echo  Starting server...
echo  Your browser will open automatically.
echo  Keep this window open while using the app.
echo  Press Ctrl+C or close this window to stop.
echo.

"%PY%" launcher.py

if errorlevel 1 (
    echo.
    echo  The app stopped with an error.
    pause
)
