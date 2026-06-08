@echo off
title Hashtag V2 Launcher

echo =========================================
echo      HASHTAG V2 SYSTEM LAUNCHER
echo =========================================
echo.

:: Get the directory of the current script
cd /d "%~dp0"

echo [0/3] Cleaning up old background processes...
taskkill /F /IM node.exe >nul 2>&1

echo [1/3] Starting Backend API Server...
start "Hashtag V2 Backend" cmd /c "cd src && title Hashtag Backend && python api_server.py || pause"

echo [2/3] Building and Starting Frontend Web GUI (Production Server)...
start "Hashtag V2 Frontend" cmd /c "cd frontend && title Hashtag Frontend && npm run build && npm run preview -- --port 5220 --open || pause"

echo.
echo System launched successfully!
echo You can close this launcher window (the backend and frontend will stay open).
timeout /t 3 >nul
