@echo off
title Telegram Auto-Reply - Status
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto :nosetup

echo ==============================================================
echo    HOW MANY PEOPLE HAVE BEEN AUTO-REPLIED TO
echo ==============================================================
echo.
".venv\Scripts\python.exe" bot.py --stats
echo.
echo  people_replied_total ....... everyone the bot has replied to
echo  people_replied_last_24h .... in the last 24 hours
echo  greetings_sent ............. people welcomed when they joined
echo.
pause
exit /b 0

:nosetup
echo.
echo Setup is not finished yet. Double-click  1-SETUP.bat  first.
echo.
pause
exit /b 1
