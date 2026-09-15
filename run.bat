@echo off
REM Windows launcher: creates a venv on first run, then starts the bot.
cd /d "%~dp0"

if not exist .venv (
  echo - creating virtual environment
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
  .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
)

if not exist .env (
  echo X .env not found. Run:  copy .env.example .env  and fill in API_ID / API_HASH
  pause
  exit /b 1
)

.venv\Scripts\python.exe bot.py %*
pause
