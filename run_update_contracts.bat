@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ============================================
echo PredictionMarket contract updater
echo ============================================

set "PREV_CSV="
for /f "delims=" %%F in ('dir /b /a:-d "pairs_*.csv" ^| sort /r') do (
    set "PREV_CSV=%%F"
    goto :found_csv
)

:found_csv
if "%PREV_CSV%"=="" (
    echo [ERROR] Could not find any pairs_*.csv file in:
    echo %CD%
    pause
    exit /b 1
)

echo [INFO] Using previous CSV: %PREV_CSV%

set "PYTHON_BIN=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_BIN=.venv\Scripts\python.exe"
)

set "BASE_URL=http://127.0.0.1:8000"
set "MAIN_XLSX=prediction_market_symbols_from_pairs.xlsx"
set "DOWNLOADS_DIR=downloads"

echo [INFO] Base URL: %BASE_URL%
echo [INFO] Main Excel: %MAIN_XLSX%
echo [INFO] Running update...

"%PYTHON_BIN%" "update_forecastex_contracts.py" ^
  --previous-csv "%PREV_CSV%" ^
  --main-xlsx "%MAIN_XLSX%" ^
  --base-url "%BASE_URL%" ^
  --downloads-dir "%DOWNLOADS_DIR%" ^
  --exchange "FORECASTX" ^
  --print-new-symbols ^
  --replace-previous-csv ^
  --cleanup-download

if errorlevel 1 (
    echo [ERROR] Update failed.
    pause
    exit /b 1
)

echo [OK] Update completed successfully.
pause
exit /b 0
