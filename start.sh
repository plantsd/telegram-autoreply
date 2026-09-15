#!/usr/bin/env bash
# Starts the bot. Works in Termux (Android), Linux and macOS.
#   bash start.sh              -> runs in the background, keeps running after
#                                 you close Termux (needs tmux, installed for you)
#   bash start.sh --foreground -> runs in this window; Ctrl+C stops it
set -u
cd "$(dirname "$0")" || exit 1
LINE="=============================================================="

if [ -f .env ]; then
  PYTHON="./.venv/bin/python"
  [ -x "$PYTHON" ] || PYTHON="python3"
else
  echo "Setup is not finished yet. Run:  bash install-termux.sh  first."
  exit 1
fi

# stop Android from freezing the process
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock 2>/dev/null || true
fi

BACKGROUND=1
[ "${1:-}" = "--foreground" ] && BACKGROUND=0

if [ "$BACKGROUND" = "1" ] && command -v tmux >/dev/null 2>&1 && [ -z "${TMUX:-}" ]; then
  # inside tmux the bot survives closing the Termux window
  if tmux has-session -t autoreply 2>/dev/null; then
    echo "$LINE"
    echo "  The bot is ALREADY RUNNING (in the background)."
    echo "  To watch it:      bash watch.sh"
    echo "  To stop it:       bash stop.sh"
    echo "  (If it is not replying, stop it and start again.)"
    echo "$LINE"
    exit 0
  fi
  echo "$LINE"
  echo "  STARTING THE BOT IN THE BACKGROUND"
  echo "$LINE"
  tmux new-session -d -s autoreply "cd '$(pwd)' && bash start.sh --foreground"
  sleep 3
  if tmux has-session -t autoreply 2>/dev/null; then
    echo "  Started. Showing you the bot now..."
    echo ""
    echo "  WHAT YOU MAY SEE NEXT: it can ask for your phone number and the login"
    echo "  code Telegram sends to your Telegram app. Type the answer, press Enter."
    echo ""
    echo "  TO LEAVE THIS SCREEN (bot keeps running):"
    echo "      press Ctrl and B together, let go, then press D"
    echo "      do NOT press Ctrl+C - that STOPS the bot"
    echo ""
    tmux attach -t autoreply
    echo ""
    echo "  You left the screen. The bot is STILL RUNNING in the background."
    echo "      stop it:  bash stop.sh      watch:  bash watch.sh"
    echo "      status:   bash status.sh"
  else
    echo "  ! It did not stay running. Run  bash start.sh --foreground  to see why."
  fi
  echo "$LINE"
  exit 0
fi

# ---- foreground mode ------------------------------------------------------
echo "$LINE"
echo "  KEEP THIS WINDOW OPEN - the bot works only while this text runs."
echo "  Stop with Ctrl+C."
echo "$LINE"
echo
echo "  First start asks for the login code Telegram sends you (only once):"
echo "    1) your phone number like +919812345678"
echo "    2) the code from your Telegram app"
echo
exec "$PYTHON" bot.py
