@echo off
chcp 65001 >nul
title ShiGuang Backend - uvicorn :8000

cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] .venv\Scripts\python.exe not found.
    echo Create the virtual environment first.
    pause
    exit /b 1
)

echo Starting backend on http://127.0.0.1:8000 ...
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

echo.
echo Backend stopped.
pause
