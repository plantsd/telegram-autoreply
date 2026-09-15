#!/usr/bin/env bash
# Plain-English summary of what the bot has done.
cd "$(dirname "$0")" || exit 1
PY="./.venv/bin/python"; [ -x "$PY" ] || PY="python3"

RUNNING="no"
if command -v tmux >/dev/null 2>&1 && tmux has-session -t autoreply 2>/dev/null; then
  RUNNING="yes (in the background)"
else
  if command -v pgrep >/dev/null 2>&1 && pgrep -f "bot[.]py" >/dev/null 2>&1; then
    RUNNING="yes (in this or another window)"
  fi
fi

# how many copies of the bot are alive? two copies can both answer the same
# message, so this is worth knowing at a glance.
COPIES=0
if command -v pgrep >/dev/null 2>&1; then
  COPIES="$(pgrep -f "bot[.]py" 2>/dev/null | wc -l | tr -d ' ')"
elif command -v ps >/dev/null 2>&1; then
  COPIES="$(ps -ef 2>/dev/null | grep -c "[b]ot[.]py")"
fi
case "$COPIES" in ''|*[!0-9]*) COPIES=0 ;; esac

SESSION_FILE=""
if [ -f .env ]; then
  SESSION_FILE="$(grep -E '^SESSION_FILE=' .env | cut -d= -f2)"
fi
SESSION_FILE="${SESSION_FILE:-data/autoreply}"

if [ -s "${SESSION_FILE}.session" ]; then
  LOGGED_IN="yes (login saved - no code needed again)"
elif [ "$RUNNING" != "no" ]; then
  LOGGED_IN="NOT YET - it is waiting for your login code inside the window"
else
  LOGGED_IN="no - it has never logged in yet"
fi

echo "=============================================================="
echo "   BOT STATUS"
echo "=============================================================="
echo "  Running right now ......... $RUNNING"
echo "  Bot copies running ........ $COPIES   (should be 1)"
echo "  Logged in to Telegram ..... $LOGGED_IN"
echo "  Auto-reply switched on .... $(grep -E '^FIRST_REPLY_ENABLED=' .env 2>/dev/null | cut -d= -f2 || echo unknown)"
echo "  Welcome on joining ........ $(grep -E '^CONTACT_SIGNUP_ENABLED=' .env 2>/dev/null | cut -d= -f2 || echo unknown)"
echo "  Greet group joins ......... $(grep -E '^GROUP_JOIN_ENABLED=' .env 2>/dev/null | cut -d= -f2 || echo unknown)"
echo "--------------------------------------------------------------"
echo "  People replied to ......... "
"$PY" bot.py --stats 2>/dev/null | sed 's/^/  /'
echo "--------------------------------------------------------------"
echo "  Last activity:"
if [ -f logs/autoreply.log ]; then
  grep -E "Logged in as|Ready\. Leave|FIRST MESSAGE|JOINED TELEGRAM|GROUP JOIN|ERROR|FloodWait" \
    logs/autoreply.log | tail -4 | sed 's/^/    /'
  if ! grep -qE "Logged in as" logs/autoreply.log 2>/dev/null; then
    echo "    (no login yet - see the steps below)"
  fi
else
  echo "    (nothing yet)"
fi
if [ "$COPIES" -gt 1 ]; then
  echo "  ! $COPIES copies are running at the same time."
  echo "    Two copies can send the same reply twice and upset Telegram."
  echo "    Fix it with these two commands:"
  echo "        bash stop.sh"
  echo "        bash start.sh"
  echo "=============================================================="
fi

if [ -s "${SESSION_FILE}.session" ]; then
  : # all good
else
  echo "  TO FINISH THE LOGIN:"
  echo "     bash start.sh --foreground     then type the code Telegram sends"
  echo "     (leave with Ctrl+C, then  bash start.sh  for background mode)"
  echo "=============================================================="
fi
echo "  Change answers any time:   bash install-termux.sh"
echo "  Watch live activity:       bash watch.sh"
