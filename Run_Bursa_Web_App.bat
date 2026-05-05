@echo off
setlocal enabledelayedexpansion

title Bursa Malaysia Web App Launcher

echo ===================================================
echo   Bursa Malaysia Web App Launcher (Streamlit)
echo ===================================================
echo.
echo Starting web server...
echo.

:: Set current directory to where the script is located
cd /d "%~dp0"

:: Ensure cache directory exists
if not exist ".yfinance_cache" (
    mkdir ".yfinance_cache"
)

:: Run the Streamlit web app
:: Using the specific python path and running streamlit as a module
"C:\Users\lawre\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m streamlit run ..\bursa_web_app.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The web server failed to start.
    echo.
    echo Troubleshooting tips:
    echo 1. Ensure you have an active internet connection.
    echo 2. Verify that 'streamlit' is installed: pip install streamlit
    echo 3. Check if the port 8501 is already in use.
    echo.
    pause
)
