@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%PY%" (
  echo [setup] Creating virtual environment ...
  set "PYCMD="
  py -3 --version >nul 2>&1
  if not errorlevel 1 set "PYCMD=py -3"
  if not defined PYCMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
  )
  if not defined PYCMD (
    echo.
    echo [ERROR] Python not found. Install Python 3.10+ from https://www.python.org
    echo         During install, check "Add Python to PATH", then run this again.
    echo.
    pause
    exit /b 1
  )
  !PYCMD! -m venv "%VENV%"
  if errorlevel 1 (
    echo.
    echo [ERROR] Python not found. Install Python 3.10+ from https://www.python.org
    echo         During install, check "Add Python to PATH", then run this again.
    echo.
    pause
    exit /b 1
  )
)

if not exist "%VENV%\.installed" (
  echo [setup] First run - installing dependencies ^(may take a few minutes^) ...
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo [ERROR] Dependency install failed. Check your internet connection and run again.
    echo.
    pause
    exit /b 1
  )
  echo installed> "%VENV%\.installed"
)

echo [run] Starting AI_stockScope - your browser will open at http://127.0.0.1:8000
echo       To stop, close this window or press Ctrl+C.
"%PY%" -m backend.server

pause
