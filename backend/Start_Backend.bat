@echo off
cd /d "%~dp0"
call Stop_Backend.bat
set PYTHONPATH=.
if not defined DATABASE_URL set DATABASE_URL=sqlite:///./emr.db
if not defined SEED_ON_STARTUP set SEED_ON_STARTUP=true
echo Using database: %DATABASE_URL%
echo Starting Endo EMR API on http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
