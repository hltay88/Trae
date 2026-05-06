@echo off
setlocal enabledelayedexpansion

title Bursa Malaysia Breakout Analyzer

echo ===================================================
echo   Bursa Malaysia Breakout Analyzer Launcher
echo ===================================================
echo.
echo Starting analyzer...
echo.

:: Set current directory to where the script is located
cd /d "%~dp0"

:: Ensure cache directory exists (fixed in bursa_core.py, but good to ensure)
if not exist ".yfinance_cache" (
    mkdir ".yfinance_cache"
)

:: Run the desktop wrapper (full feature set)
:: It launches the Streamlit app in a desktop window (or browser fallback)
"C:\Users\lawre\AppData\Local\Python\pythoncore-3.14-64\python.exe" "bursa_desktop_app.py"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The program crashed or failed to start.
    echo.
    echo Troubleshooting tips:
    echo 1. Ensure you have an active internet connection for live data.
    echo 2. Verify that the Python environment is still valid.
    echo 3. Check if the '.yfinance_cache' folder is accessible.
    echo.
    pause
)
