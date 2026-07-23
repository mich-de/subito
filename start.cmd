@echo off
set PORT=5000

:: Try to parse port from config/config.yaml
if exist config\config.yaml (
    for /f "tokens=2 delims=: " %%p in ('findstr /i "port:" config\config.yaml') do (
        set PORT=%%p
    )
)

echo Checking for active processes on port %PORT%...

netstat -aon | findstr LISTENING | findstr :%PORT% >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Terminating processes occupying port %PORT%...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr LISTENING ^| findstr :%PORT%') do (
        echo Killing PID %%a...
        taskkill /f /pid %%a
    )
    timeout /t 1 /nobreak >nul
) else (
    echo Port %PORT% is free.
)

echo Launching Offerte Monitor application...
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe main.py
) else (
    echo Error: .venv\Scripts\python.exe not found. Run setup steps first.
    pause
)
