@echo off
title Telegram Auto-Reply - Safe Test (sends nothing)
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto :nosetup
if not exist ".env" goto :nosetup

echo ==============================================================
echo    SAFE TEST - NOTHING WILL BE SENT
echo ==============================================================
echo.
echo  The bot logs in and prints what it WOULD send.
echo  Ask a friend to message you, or message yourself from another
echo  account, and watch the lines that appear below.
echo.
echo  Press Ctrl+C to stop.
echo.
pause

".venv\Scripts\python.exe" bot.py --dry-run
pause
exit /b 0

:nosetup
echo.
echo Setup is not finished yet. Double-click  1-SETUP.bat  first.
echo.
pause
exit /b 1
