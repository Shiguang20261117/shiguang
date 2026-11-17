@echo off
chcp 65001 >nul
title ShiGuang Frontend - vite dev

cd /d "%~dp0frontend"

if not exist "package.json" (
    echo [ERROR] package.json not found in %~dp0frontend
    pause
    exit /b 1
)

echo Starting frontend ...
call "D:\npm.cmd" run dev

echo.
echo Frontend stopped.
pause
