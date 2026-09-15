@echo off
title Telegram Auto-Reply - Running (keep this window open)
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto :nosetup
if not exist ".env" goto :nosetup

echo ==============================================================
echo    TELEGRAM AUTO-REPLY IS STARTING
echo ==============================================================
echo.
echo  KEEP THIS WINDOW OPEN. The bot only works while it is open.
echo  To stop the bot, close this window (or press Ctrl+C).
echo.

".venv\Scripts\python.exe" bot.py

echo.
echo --------------------------------------------------------------
echo  The bot has stopped. If that was not on purpose, look for a
echo  line that says ERROR above and check the EASY-GUIDE.
echo --------------------------------------------------------------
pause
exit /b 0

:nosetup
echo.
echo Setup is not finished yet.
echo Please double-click  1-SETUP.bat  first.
echo.
pause
exit /b 1
