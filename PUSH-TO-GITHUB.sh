#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Uploads this folder to your GitHub repository.
#
#      bash PUSH-TO-GITHUB.sh
#
#  It will:
#    1. check that your private files (.env, login session, history) are NOT
#       included — it stops instead of uploading them
#    2. save your project as a git version and push it to GitHub
#
#  The first time, GitHub asks for a username and password.
#     username ->  dekuc
#     password ->  a "token" you create once (instructions are printed
#                  automatically if you don't have one yet)
# ---------------------------------------------------------------------------
set -u

cd "$(dirname "$0")" || exit 1

REMOTE_URL="${1:-https://github.com/dekuc/telegram-autoreply.git}"
BRANCH="main"
LINE="=============================================================="
say() { printf '%s\n' "$*"; }

say "$LINE"
say "   UPLOADING THE PROJECT TO GITHUB"
say "$LINE"
say ""

# ---------------------------------------------------------------- git ready ---
if ! command -v git >/dev/null 2>&1; then
  say "! git is not installed."
  case "${PREFIX:-}" in
    *com.termux*) say "  In Termux type:  pkg install git   then run this again." ;;
    *)            say "  Install git, then run this again." ;;
  esac
  exit 1
fi

# name + email are only used to label the save; harmless values are fine
git config --global user.name  >/dev/null 2>&1 || git config --global user.name  "dekuc"
git config --global user.email >/dev/null 2>&1 || git config --global user.email "dekuc@users.noreply.github.com"

# ------------------------------------------------------------- start repo -----
if [ ! -d .git ]; then
  say "Preparing the folder (first time only)..."
  git init -q || exit 1
  git branch -M "$BRANCH" >/dev/null 2>&1 || git checkout -q -b "$BRANCH"
fi

# ------------------------------------------------------ SECRET SAFETY CHECK ---
# These files must never leave your phone: they are a full login to Telegram.
if git rev-parse --verify -q HEAD >/dev/null 2>&1; then
  CHECK_LIST="$(git ls-files)"
else
  CHECK_LIST="$(git status --porcelain --untracked-files=all | sed 's/^...//')"
fi

DANGER="$(printf '%s\n' "$CHECK_LIST" | grep -Ev '^$|\.env\.example$|\.env\.selftest$' \
          | grep -E '(^|/)\.env$|\.session|(^|/)\.env\.[a-z]+$|(^|/)data/|(^|/)logs/' || true)"

if [ -n "$DANGER" ]; then
  say "STOPPED — these private files would be uploaded:"
  printf '   %s\n' $DANGER
  say ""
  say "These contain your Telegram login or your settings. If they ever reach"
  say "GitHub, someone could use your Telegram account."
  say ""
  say "Normally this does not happen because .gitignore blocks them. To fix it:"
  say "  1. run:   bash 5-FIX-EVERYTHING.bat   (Windows)   or   bash install-termux.sh"
  say "  2. if you already uploaded one by accident, CHANGE YOUR TELEGRAM"
  say "     PASSWORD and go to Telegram > Settings > Devices > terminate sessions"
  say "$LINE"
  exit 1
fi
say "Safety check passed — no private files will be uploaded. ✔"

# ------------------------------------------------------------------- commit ---
git add -A

if git rev-parse --verify -q HEAD >/dev/null 2>&1 && git diff --cached --quiet; then
  say "Nothing changed since the last upload."
else
  git commit -q -m "Telegram auto-reply bot ($(date '+%d %b %Y %H:%M'))" || {
    say "! Could not save the version. Try:  bash PUSH-TO-GITHUB.sh"
    exit 1
  }
  say "Saved a new version of the project."
fi

# ------------------------------------------------------------------- remote ---
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi
say "Repository: $REMOTE_URL"
say ""

# --------------------------------------------------------------------- push ---
say "Uploading to GitHub now..."
if git push -u origin "$BRANCH" 2>/tmp/gitpush.err; then
  say ""
  say "$LINE"
  say "  DONE — your project is on GitHub ✔"
  say "$LINE"
  say "  Open it in your browser:"
  say "     ${REMOTE_URL%.git}"
  say ""
  say "  What this gives you:"
  say "   • your code is saved safely, even if the phone is lost"
  say "   • you can edit templates.json right in the browser, then type"
  say "     'git pull' in Termux to use the new text"
  say "   • your Telegram login and settings stay ONLY on your phone"
  say "$LINE"
  exit 0
fi

# ------------------------------------------------------- explain what failed ---
ERR="$(cat /tmp/gitpush.err 2>/dev/null || true)"

if printf '%s' "$ERR" | grep -qiE "authentication|invalid username or password|403|password authentication"; then
  say ""
  say "$LINE"
  say "  GITHUB ASKED FOR A PASSWORD — HERE IS THE TRICK"
  say "$LINE"
  say "  GitHub does not accept your normal password here. You need a 'token',"
  say "  which is a long one-time password. It takes 1 minute:"
  say ""
  say "  1. In your browser open:  https://github.com/settings/tokens"
  say "  2. Tap 'Generate new token' -> 'Generate new token (classic)'"
  say "  3. 'Note' box: type  termux"
  say "     Tick the checkbox named  repo"
  say "     ALSO tick the second checkbox named  workflow   (important!)"
  say "  4. Scroll down, tap 'Generate token', then COPY the code shown"
  say "     (it starts with ghp_...). You won't see it again."
  say "  5. Run this again:   bash PUSH-TO-GITHUB.sh"
  say "     username -> dekuc        password -> paste that code"
  say ""
  say "  Optional: to avoid typing it every time:"
  say "     git config --global credential.helper store"
  say "$LINE"
  exit 1
fi

if printf '%s' "$ERR" | grep -qiE "refusing to allow|workflow.*(not permitted|scope)"; then
  say ""
  say "$LINE"
  say "  ALMOST DONE - ONE MORE TICK NEEDED"
  say "$LINE"
  say "  GitHub blocked the upload because your token is not allowed to add"
  say "  the automation file (.github/workflows/autoreply.yml)."
  say ""
  say "  1. Open:  https://github.com/settings/tokens"
  say "  2. Tap your existing token (or make a new one)"
  say "  3. Tick the checkbox named  repo  AND the one named  workflow"
  say "  4. Save / regenerate, copy the new ghp_... code"
  say "  5. Run again:   bash PUSH-TO-GITHUB.sh"
  say "$LINE"
  exit 1
fi

if printf '%s' "$ERR" | grep -qiE "non-fast-forward|rejected|fetch first"; then
  say "The repository already has files. Combining yours with it..."
  if git pull --rebase origin "$BRANCH" && git push -u origin "$BRANCH"; then
    say "Uploaded ✔  Check it at ${REMOTE_URL%.git}"
    exit 0
  fi
  say "! Could not combine automatically. Someone else may have edited the repo."
  say "  Easiest fix: on GitHub, delete the repository and create it again empty,"
  say "  then run:  bash PUSH-TO-GITHUB.sh"
  exit 1
fi

say ""
say "! Upload failed. GitHub said:"
printf '%s\n' "$ERR" | tail -5
say ""
say "  Most common cause: no internet. Check your connection and run again."
say "  Still stuck? See the 'Something is broken?' section in EASY-GUIDE.md"
exit 1
