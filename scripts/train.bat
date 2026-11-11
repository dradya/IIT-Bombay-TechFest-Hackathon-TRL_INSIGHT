@echo off
REM =====================================================================
REM  TRL INSIGHT - train the model (Windows)
REM  1) prepare_data : loads/validates data, writes stratified splits
REM  2) train_model  : trains + selects the classifier, saves the bundle
REM  3) evaluate     : computes REAL test metrics -> models/metrics.json
REM
REM  Default: SYNTHETIC demonstration dataset (local functional testing).
REM  For the OFFICIAL dataset see docs/DATASET_GUIDE.md, e.g.:
REM    train.bat --source data\raw\official.csv
REM =====================================================================
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] Run scripts\setup.bat first.
  exit /b 1
)
call ".venv\Scripts\activate.bat"
cd backend

set EXTRA_ARGS=%*
if "%EXTRA_ARGS%"=="" set EXTRA_ARGS=--synthetic --samples 60

echo ============================================================
echo  [1/3] prepare_data  %EXTRA_ARGS%
echo ============================================================
python training\prepare_data.py %EXTRA_ARGS%
if errorlevel 1 ( echo [ERROR] prepare_data failed. & exit /b 1 )

echo.
echo ============================================================
echo  [2/3] train_model
echo ============================================================
python training\train_model.py
if errorlevel 1 ( echo [ERROR] train_model failed. & exit /b 1 )

echo.
echo ============================================================
echo  [3/3] evaluate_model
echo ============================================================
python training\evaluate_model.py
if errorlevel 1 ( echo [ERROR] evaluate_model failed. & exit /b 1 )

echo.
echo DONE. Metrics: backend\models\metrics.json (visible in the UI at
echo "Model Performance"). Restart the backend to load the new model.
exit /b 0
