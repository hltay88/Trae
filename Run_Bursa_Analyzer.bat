@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Bursa Malaysia Breakout Analyzer Launcher
echo ===================================================
echo.
echo Starting analyzer...
echo.

:: Set current directory to where the script is located
cd /d "%~dp0"

:: Run the analyzer using the fixed Python path
"C:\Users\lawre\AppData\Local\Python\pythoncore-3.14-64\python.exe" "bursa_analyzer_gui.py"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The program crashed or failed to start.
    echo.
    echo Troubleshooting tips:
    echo 1. Ensure you have internet connection for live data.
    echo 2. Check if all Python libraries are installed correctly.
    echo.
    pause
)
