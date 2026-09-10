@echo off
title AI Smart Exam Proctoring System
color 0A

echo ================================================================
echo      AI-ASSISTED SMART EXAM PROCTORING SYSTEM (B.Tech CSE)
echo ================================================================
echo.

:: Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [!] Python is not currently detected in your system PATH.
        echo.
        echo [*] To install Python automatically on Windows, you can run:
        echo     winget install Python.Python.3.11
        echo.
        echo [*] Or download Python 3.10+ from: https://www.python.org/downloads/
        echo     (Be sure to check "Add Python to PATH" during installation!)
        echo.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

echo [*] Detected Python environment: %PYTHON_CMD%
echo [*] Installing / Verifying dependencies from requirements.txt...
%PYTHON_CMD% -m pip install -r requirements.txt

echo.
echo [*] Launching AI Proctoring Server...
echo [*] Student Portal:      http://127.0.0.1:5000
echo [*] Faculty Dashboard:   http://127.0.0.1:5000/dashboard
echo.
%PYTHON_CMD% app.py

pause
