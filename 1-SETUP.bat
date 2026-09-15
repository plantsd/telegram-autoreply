@echo off
title Telegram Auto-Reply - Setup
setlocal
cd /d "%~dp0"

echo ==============================================================
echo    TELEGRAM AUTO-REPLY - SETUP
echo ==============================================================
echo.
echo This window will:
echo   1. install the small helper programs needed  (first time only)
echo   2. ask you 6 easy questions
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
if not exist ".venv\Scripts\python.exe" (
  echo Installing helper programs, please wait 1-3 minutes...
  %PY% -m venv .venv
  if errorlevel 1 goto :venvfail
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  if errorlevel 1 goto :installfail
  echo Done installing.
  echo.
)

".venv\Scripts\python.exe" setup_wizard.py
if errorlevel 1 goto :wizardfail

echo.
echo Next step: double-click  2-START.bat
echo.
pause
exit /b 0

:nopython
echo.
echo --------------------------------------------------------------
echo  Python is not installed on this computer yet.
echo.
echo  1. Go to:  https://www.python.org/downloads/
echo  2. Click the big yellow "Download Python" button.
echo  3. Open the downloaded file.
echo  4. IMPORTANT: tick the box "Add Python to PATH" at the bottom,
echo     then click "Install Now".
echo  5. When it finishes, double-click 1-SETUP.bat again.
echo --------------------------------------------------------------
echo.
pause
exit /b 1

:venvfail
echo Something went wrong while creating the setup folder.
pause
exit /b 1

:installfail
echo.
echo The helper programs could not be downloaded.
echo Are you connected to the internet? Then run this file again.
pause
exit /b 1

:wizardfail
echo.
echo The setup wizard stopped. Run 1-SETUP.bat again to retry.
pause
exit /b 1
