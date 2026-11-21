@echo off
setlocal
title Endo EMR Launcher
cd /d "%~dp0"

set "BACKEND_DIR=%~dp0backend"
set "FRONTEND_DIR=%~dp0frontend"
set "API_URL=http://127.0.0.1:8000"
set "APP_URL=http://127.0.0.1:5173"

echo.
echo  ========================================
echo    Endo EMR
echo  ========================================
echo.
echo  Starting backend and frontend...
echo  Leave the Backend and Frontend windows open while using the app.
echo.

set "PY=python"
if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
if exist "%BACKEND_DIR%\venv\Scripts\python.exe" set "PY=%BACKEND_DIR%\venv\Scripts\python.exe"

"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo  Python was not found. Install Python 3.10+ and check "Add Python to PATH".
  pause
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo  npm was not found. Install Node.js from https://nodejs.org/
  pause
  exit /b 1
)

if exist "%BACKEND_DIR%\Stop_Backend.bat" (
  pushd "%BACKEND_DIR%"
  call Stop_Backend.bat >nul 2>&1
  popd
)

start "Endo EMR Backend" /D "%BACKEND_DIR%" cmd /k "set PYTHONPATH=.&& if not defined DATABASE_URL set DATABASE_URL=sqlite:///./emr.db&& if not defined SEED_ON_STARTUP set SEED_ON_STARTUP=true&& echo Backend: %API_URL%&& echo Docs: %API_URL%/docs&& "%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

if not exist "%FRONTEND_DIR%\node_modules\" (
  echo  Installing frontend packages ^(first run^)...
  pushd "%FRONTEND_DIR%"
  call npm install
  if errorlevel 1 (
    echo  npm install failed.
    pause
    exit /b 1
  )
  popd
)

start "Endo EMR Frontend" /D "%FRONTEND_DIR%" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"

echo  Waiting for the app...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 60;$i++){ try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:5173/; if($r.StatusCode -ge 200){ $ok=$true; break } } catch {} ; Start-Sleep -Seconds 1 }; if($ok){ Start-Process 'http://127.0.0.1:5173/' } else { Write-Host 'Timed out — open http://127.0.0.1:5173 manually when Vite is ready.' }"

echo.
echo  Opened %APP_URL%
echo  Close Backend + Frontend windows to stop the app.
echo.
timeout /t 3 >nul
endlocal
