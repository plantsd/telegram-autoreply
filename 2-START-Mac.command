#!/bin/bash
# macOS double-click launcher for the bot itself.
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ] || [ ! -f .env ]; then
  echo "Setup is not finished yet. Double-click  1-SETUP-Mac.command  first."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "=============================================================="
echo "   TELEGRAM AUTO-REPLY IS STARTING"
echo "=============================================================="
echo
echo " KEEP THIS WINDOW OPEN. The bot works only while it is open."
echo " To stop the bot, close this window or press Ctrl+C."
echo
./.venv/bin/python bot.py
echo
echo "The bot has stopped. Check the EASY-GUIDE if that was not on purpose."
read -r -p "Press Enter to close..."
