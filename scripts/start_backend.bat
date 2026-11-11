@echo off
REM TRL INSIGHT - backend only (FastAPI on http://localhost:8000)
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] Run scripts\setup.bat first.
  exit /b 1
)
call ".venv\Scripts\activate.bat"
cd backend
if not defined TRL_PORT set "TRL_PORT=8000"
echo TRL INSIGHT API -> http://localhost:%TRL_PORT%/api/docs
python -m uvicorn app.main:app --reload --port %TRL_PORT%
exit /b %errorlevel%
