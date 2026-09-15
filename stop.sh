#!/usr/bin/env bash
# Stops the bot started with start.sh
cd "$(dirname "$0")" || exit 1
STOPPED=0

if command -v tmux >/dev/null 2>&1 && tmux has-session -t autoreply 2>/dev/null; then
  tmux kill-session -t autoreply && echo "Bot stopped."
  STOPPED=1
fi

if [ -f data/autoreply.pid ]; then
  PID="$(cat data/autoreply.pid 2>/dev/null || true)"
  if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" && echo "Bot stopped (pid $PID)."
    STOPPED=1
  fi
  rm -f data/autoreply.pid
fi

if command -v termux-wake-unlock >/dev/null 2>&1; then
  termux-wake-unlock 2>/dev/null || true
fi

[ "$STOPPED" = "0" ] && echo "The bot was not running."
exit 0
