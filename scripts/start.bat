@echo off
REM =====================================================================
REM  TRL INSIGHT - start backend AND frontend (Windows)
REM  Backend : http://localhost:8000   (API + Swagger at /api/docs)
REM  Frontend: http://localhost:5173   (proxies /api to the backend)
REM =====================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] Virtual environment not found. Run scripts\setup.bat first.
  exit /b 1
)
call ".venv\Scripts\activate.bat"

if not exist "frontend\node_modules" (
  echo [ERROR] frontend\node_modules not found. Run scripts\setup.bat first.
  exit /b 1
)

if not defined TRL_PORT set "TRL_PORT=8000"
echo Starting TRL INSIGHT backend on http://localhost:%TRL_PORT% ...
start "TRL INSIGHT - Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --reload --port %TRL_PORT%"

timeout /t 3 /nobreak >nul

echo Starting TRL INSIGHT frontend on http://localhost:5173 ...
start "TRL INSIGHT - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ============================================================
echo  Both services are starting in separate windows.
echo    Frontend : http://localhost:5173
echo    API      : http://localhost:%TRL_PORT%/api/docs
echo  Close the two windows to stop the services.
echo ============================================================
exit /b 0
