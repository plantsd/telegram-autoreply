#!/data/data/com.termux/files/usr/bin/bash
# ---------------------------------------------------------------------------
#  ONE-COMMAND SETUP FOR ANDROID (Termux)
#
#  In Termux, inside this folder, type:      bash install-termux.sh
#
#  It installs everything, asks the 6 easy questions, and can start the bot.
#  Safe to run again at any time (it repairs rather than breaks).
# ---------------------------------------------------------------------------
set -u

cd "$(dirname "$0")" || exit 1

LINE="=============================================================="
say() { printf '%s\n' "$*"; }

say "$LINE"
say "    TELEGRAM AUTO-REPLY - SETUP FOR ANDROID / TERMUX"
say "$LINE"
say ""

# ---------------------------------------------------------------- termux? ---
IS_TERMUX=0
case "${PREFIX:-}" in
  *com.termux*) IS_TERMUX=1 ;;
esac

if [ "$IS_TERMUX" = "1" ]; then
  say "Checking the helper programs (this is quick)..."
  if ! command -v pkg >/dev/null 2>&1; then
    say "  ! 'pkg' is missing. This does not look like a normal Termux install."
    say "    Install Termux from F-Droid or GitHub (NOT the Play Store version),"
    say "    then run this again."
    exit 1
  fi
  pkg update -y >/dev/null 2>&1 || true
  # python + git are needed; tmux lets the bot keep running after you close Termux
  for package in python git tmux unzip; do
    if ! command -v "$package" >/dev/null 2>&1; then
      say "  installing $package ..."
      pkg install -y "$package" >/dev/null 2>&1 || {
        say "  ! Could not install $package. Check your internet and run this again."
        exit 1
      }
    fi
  done
  say "  helpers ready."

  # keep Android from freezing Termux in the background
  if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock 2>/dev/null && say "  wake-lock on (Android will not freeze the bot)."
  fi
fi

PY=""
for candidate in python python3; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  say "! Python is missing. In Termux run:  pkg install python"
  exit 1
fi

# ------------------------------------------------------- python environment ---
if [ ! -x .venv/bin/python ]; then
  say ""
  say "Setting up the program folder (1-3 minutes the first time)..."
  "$PY" -m venv .venv || {
    say "! Could not create the program folder."
    say "  In Termux, try:  pkg install python && rm -rf .venv && bash install-termux.sh"
    exit 1
  }
fi

if ! ./.venv/bin/python -c "import telethon" >/dev/null 2>&1; then
  say "Downloading the Telegram helper library..."
  ./.venv/bin/pip install --quiet --upgrade pip >/dev/null 2>&1 || true
  ./.venv/bin/pip install --quiet -r requirements.txt || {
    say "! Download failed. Check your internet connection and run this again."
    exit 1
  }
  say "  done."
fi

# ------------------------------------------------------------ the questions ---
say ""
./.venv/bin/python setup_wizard.py || {
  say "! The setup questions stopped early. Run  bash install-termux.sh  again."
  exit 1
}

# ----------------------------------------------------------------- checks -----
say ""
say "Checking everything before we start..."
OUT="$(./.venv/bin/python bot.py --selftest 2>&1)"
if printf '%s' "$OUT" | grep -q "Selftest: PASSED"; then
  say "  everything looks good ✔"
else
  say "  ! Something is not right. Here is the detail:"
  printf '%s\n' "$OUT" | tail -20
  say "  Run  bash install-termux.sh  again, or see EASY-GUIDE.md"
  exit 1
fi

# --------------------------------------------------------------- start now? ---
say ""
if [ -t 0 ]; then
  printf 'Do you want to start the bot now? Type y and press Enter (or n to start later): '
  read -r answer || answer="n"
else
  answer="y"
fi

if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
  say ""
  bash start.sh
else
  say ""
  say "$LINE"
  say "  SETUP DONE"
  say "$LINE"
  say "  To start the bot later, open Termux and type:"
  say ""
  say "      cd $(pwd) && bash start.sh"
  say ""
  say "  To see how many people were auto-replied to:"
  say ""
  say "      cd $(pwd) && bash status.sh"
  say "$LINE"
fi
