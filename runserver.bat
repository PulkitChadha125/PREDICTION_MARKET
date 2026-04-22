@echo off
setlocal

REM Move to the script directory (project root).
cd /d "%~dp0"

echo ============================================
echo PredictionMarket server bootstrap
echo Project: %cd%
echo ============================================

REM Check whether .venv exists; create it if missing.
if exist ".venv\Scripts\python.exe" (
    echo [OK] .venv already exists.
) else (
    echo [INFO] .venv not found. Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment using "py -3".
        echo [INFO] Make sure Python 3 is installed and available.
        exit /b 1
    )
    echo [OK] .venv created successfully.
)

REM Activate venv.
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate .venv.
    exit /b 1
)

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    exit /b 1
)

echo [INFO] Installing requirements from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    exit /b 1
)

echo [INFO] Starting FastAPI server...
echo [INFO] Local URL:  http://127.0.0.1:8000
echo [INFO] Public URL: http://[SERVER_IP]:8000
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

endlocal
