@echo off
REM =====================================================================
REM  TRL INSIGHT - one-time setup for Windows
REM  Creates a virtual environment, installs Python + frontend deps.
REM  Requires: Python 3.10+ and Node.js 18+ on PATH.
REM =====================================================================
setlocal
cd /d "%~dp0"

echo ============================================================
echo  TRL INSIGHT - SETUP
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH. Install Python 3.10+ from https://python.org
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js/npm was not found on PATH. Install Node.js 18+ from https://nodejs.org
  exit /b 1
)

python --version
npm --version

echo.
echo [1/4] Creating virtual environment (.venv) ...
if not exist ".venv" (
  python -m venv .venv
  if errorlevel 1 ( echo [ERROR] Could not create the virtual environment. & exit /b 1 )
) else (
  echo        .venv already exists - reusing it.
)

echo [2/4] Installing Python dependencies ...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] pip install failed. & exit /b 1 )

echo [3/4] Installing frontend dependencies (this can take a few minutes) ...
pushd frontend
call npm install
if errorlevel 1 ( popd & echo [ERROR] npm install failed. & exit /b 1 )
popd

echo [4/4] Training the demonstration model (optional but recommended) ...
if exist ".venv\Scripts\python.exe" (
  pushd backend
  "..\.venv\Scripts\python.exe" training\prepare_data.py --synthetic --samples 60
  "..\.venv\Scripts\python.exe" training\train_model.py
  "..\.venv\Scripts\python.exe" training\evaluate_model.py
  popd
)

echo.
echo ============================================================
echo  SETUP COMPLETE
echo  Next steps:
echo    start.bat          - start backend + frontend together
echo    start_backend.bat  - backend only  (http://localhost:8000)
echo    start_frontend.bat - frontend only (http://localhost:5173)
echo    train.bat          - retrain the model
echo ============================================================
exit /b 0
