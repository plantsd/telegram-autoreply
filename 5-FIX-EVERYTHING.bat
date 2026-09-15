@echo off
title Telegram Auto-Reply - Repair
setlocal
cd /d "%~dp0"
echo ==============================================================
echo    REPAIR  (use this if the bot stopped working)
echo ==============================================================
echo.

set "PY="
py -3 -c "print(1)" >nul 2>nul && set "PY=py -3"
if defined PY goto :ready
python -c "print(1)" >nul 2>nul && set "PY=python"
if defined PY goto :ready
python3 -c "print(1)" >nul 2>nul && set "PY=python3"
if defined PY goto :ready
goto :nopython

:ready
if exist ".venv" rmdir /s /q ".venv"
echo Re-downloading the helper programs...
%PY% -m venv .venv
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :fail
echo.
echo Checking your settings...
".venv\Scripts\python.exe" bot.py --selftest
echo.
echo Repair finished. Start the bot with 2-START.bat
echo (Your settings, login and history were NOT deleted.)
echo.
pause
exit /b 0

:nopython
echo Python is not installed. See the instructions in 1-SETUP.bat
echo (or: https://www.python.org/downloads/ - tick "Add Python to PATH").
pause
exit /b 1

:fail
echo Download failed. Check your internet connection and run this again.
pause
exit /b 1
