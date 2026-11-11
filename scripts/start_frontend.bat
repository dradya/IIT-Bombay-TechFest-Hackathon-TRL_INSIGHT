@echo off
REM TRL INSIGHT - frontend only (Vite dev server on http://localhost:5173)
setlocal
cd /d "%~dp0"
if not exist "frontend\node_modules" (
  echo [ERROR] Run scripts\setup.bat first.
  exit /b 1
)
cd frontend
echo TRL INSIGHT UI -> http://localhost:5173  (proxies /api to :8000)
npm run dev
exit /b %errorlevel%
