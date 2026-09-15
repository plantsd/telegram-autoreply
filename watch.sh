#!/usr/bin/env bash
# Shows what the bot is doing right now. Ctrl+C leaves this screen only -
# the bot keeps running in the background.
cd "$(dirname "$0")" || exit 1
if command -v tmux >/dev/null 2>&1 && tmux has-session -t autoreply 2>/dev/null; then
  echo "To leave this screen WITHOUT stopping the bot: press Ctrl+B, then D."
  echo "(Ctrl+C would stop the bot.)"
  echo
  sleep 1
  exec tmux attach -t autoreply
fi
if [ -f logs/autoreply.log ]; then
  echo "To leave this screen WITHOUT stopping the bot: press Ctrl+B, then D."
  echo "(Ctrl+C would stop the bot.)"
  echo
  echo "Live view:"
  exec tail -f logs/autoreply.log
fi
echo "Nothing to watch yet. Start the bot first:  bash start.sh"
