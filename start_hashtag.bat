@echo off
title HASHTAG V2 — LAUNCH
color 0A
cls

echo =====================================================
echo   HASHTAG V2 BORDER SURVEILLANCE SYSTEM
echo   Starting Backend + Frontend...
echo =====================================================
echo.

:: Check Python is available
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found on PATH. Please install Python 3.10+.
    pause
    exit /b 1
)

:: Check Node is available
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js not found on PATH. Please install Node.js 18+.
    pause
    exit /b 1
)

echo [1/4] Checking Backend Dependencies...
cd /d "%~dp0src"
if not exist "venv\Scripts\activate.bat" (
    echo Creating Python virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    echo Installing Python packages...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)

echo.
echo [2/4] Checking Frontend Dependencies...
cd /d "%~dp0frontend"
if not exist "node_modules\" (
    echo Installing Node packages...
    call npm install
)

echo.
echo [3/4] Starting Backend (Flask API on port 5000)...
start "HASHTAG BACKEND" cmd /k "cd /d "%~dp0src" && call venv\Scripts\activate && python api_server.py"

echo Waiting for backend to initialize (5s)...
timeout /t 5 /nobreak > nul

echo.
echo [4/4] Starting Frontend (Vite on port 5173)...
start "HASHTAG FRONTEND" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Waiting for frontend to compile (6s)...
timeout /t 6 /nobreak > nul

echo Opening browser...
start "" "http://localhost:5211"

echo.
echo =====================================================
echo   System Running.
echo   Admin Panel: http://localhost:5211  (Admin tab)
echo   API Server:  http://localhost:5000/api/status
echo   nodes.json:  %~dp0src\nodes.json
echo =====================================================
echo.
echo   To stop: close the BACKEND and FRONTEND windows.
echo.
pause
