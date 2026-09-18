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

REMOTE_URL="${1:-https://github.com/plantsd/telegram-autoreply.git}"
BRANCH="main"
LINE="=============================================================="
say() { printf '%s\n' "$*"; }

say "$LINE"
say "   UPLOADING THE PROJECT TO GITHUB"
say "$LINE"
say ""

# ------------------------------------------------------------- right branch ---
# If someone created the repository by hand (git init), it may sit on "master"
# with no commits — then "git push main" fails. Make sure the branch exists.
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
case "$CURRENT_BRANCH" in
  "$BRANCH") : ;;
  '')
    git symbolic-ref HEAD "refs/heads/$BRANCH" 2>/dev/null || true ;;
  *)
    if git rev-parse --verify -q "$BRANCH" >/dev/null 2>&1; then
      git checkout -q "$BRANCH" || true
    else
      git checkout -q -b "$BRANCH" || git branch -M "$BRANCH" || true
    fi ;;
esac

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

# /tmp does not exist on Android, so find somewhere we can really write
ERR_FILE=""
mkdir -p logs 2>/dev/null || true
for candidate in "logs/gitpush-last.err" "$HOME/.gitpush-last.err"; do
  if ( : > "$candidate" ) 2>/dev/null; then ERR_FILE="$candidate"; break; fi
done
[ -n "$ERR_FILE" ] || ERR_FILE="/dev/null"

# is the cloud automation actually present?
CLOUD_OK=1
if [ ! -f ".github/workflows/autoreply.yml" ]; then
  CLOUD_OK=0
  say ""
  say "NOTE: .github/workflows/autoreply.yml is missing from this folder, so the"
  say "     'check every 30 minutes on GitHub' part would NOT be uploaded."
  say "     Easiest fix: download telegram-autoreply.zip again from the chat, then"
  say "         cd ~/projects && unzip -o /sdcard/Download/telegram-autoreply.zip"
  say "     and run this script once more."
  say ""
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
say "HEADS-UP: your token needs TWO ticks - 'repo' and 'workflow'."
say "Without 'workflow', GitHub refuses .github/workflows/autoreply.yml."
say ""
say "Uploading to GitHub now..."
say "(GitHub will now ask for a username and password: dekuc + your token)"
say ""
if git push -u origin "$BRANCH" 2>"$ERR_FILE"; then
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
  if [ "$CLOUD_OK" = "0" ]; then
    say ""
    say "  REMINDER: the every-30-minutes file was missing from this folder, so"
    say "  the cloud part did NOT upload. Re-download the zip and push again."
  fi
  say "$LINE"
  exit 0
fi

# ------------------------------------------------------- explain what failed ---
ERR="$(cat "$ERR_FILE" 2>/dev/null || true)"
if [ -n "$ERR" ]; then
  say "git said:"
  printf '%s\n' "$ERR" | sed 's/^/   /'
  say ""
fi

if printf '%s' "$ERR" | grep -qiE "authentication|invalid username or password|403|password authentication|terminal prompts disabled"; then
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
  say "Your repository already has something in it. Checking what..."
  git fetch origin "$BRANCH" >/dev/null 2>&1 || true
  REMOTE_FILES="$(git ls-tree -r --name-only FETCH_HEAD 2>/dev/null | head -20 || true)"
  REMOTE_COUNT="$(printf '%s\n' "$REMOTE_FILES" | grep -c . || true)"
  case "$REMOTE_COUNT" in ''|*[!0-9]*) REMOTE_COUNT=0 ;; esac

  if [ "$REMOTE_COUNT" -gt 0 ] && [ "$REMOTE_COUNT" -le 5 ]; then
    say ""
    say "$LINE"
    say "  YOUR REPOSITORY ALREADY CONTAINS $REMOTE_COUNT FILE(S):"
    say "$LINE"
    printf '    %s\n' $REMOTE_FILES
    say ""
    say "  These look like leftovers (for example a zip you uploaded from the"
    say "  GitHub website), not your project folder."
    say ""
    say "  Replace them with your project?"
    say "  Your files on the phone are NOT touched, and only this one"
    say "  repository is affected."
    say "$LINE"
    printf "Type y to replace, or n to stop: "
    read -r answer || answer="n"
    case "$answer" in
      y|Y|yes|YES)
        if git push -f -u origin "$BRANCH" 2>"$ERR_FILE"; then
          say ""
          say "  Replaced. Your project is now on GitHub:"
          say "     ${REMOTE_URL%.git}"
          if [ "$CLOUD_OK" = "0" ]; then
            say "  (But the cloud file was missing from this folder - see the note above.)"
          fi
          exit 0
        fi
        say "! Could not replace it. GitHub said:"
        cat "$ERR_FILE" 2>/dev/null | sed 's/^/   /'
        say "  Send me these lines and I will sort it out."
        exit 1
        ;;
      *)
        say ""
        say "  Stopped - nothing on GitHub was changed."
        say "  To put your project there, run this again and answer y."
        exit 0
        ;;
    esac
  fi

  say "  The repository already has $REMOTE_COUNT file(s), so this is not a simple"
  say "  leftover upload. Two options:"
  say "    1. On GitHub: Settings -> scroll down -> 'Delete this repository',"
  say "       then create it again with the same name (leave it empty) and run"
  say "       this script once more."
  say "    2. Copy the lines above and send them to me."
  exit 1
fi

say "! Upload did not finish."
say ""
if printf '%s' "$ERR" | grep -qiE "could not read Username|terminal prompts disabled"; then
  say "  GitHub could not ask you for a password here (this happens when the"
  say "  terminal cannot show a prompt). Set a token once, then push again:"
  say ""
  say "      git config --global credential.helper store"
  say "      bash PUSH-TO-GITHUB.sh"
  say ""
  say "  username: dekuc     password: your ghp_... token"
  say "  (No token yet? Open https://github.com/settings/tokens -> Generate new"
  say "   token (classic) -> tick 'repo' AND 'workflow' -> copy the ghp_ code.)"
elif printf '%s' "$ERR" | grep -qiE "src refspec|does not match any"; then
  say "  The local copy has no saved version on the '$BRANCH' branch yet."
  say "  Run this once and then push again:"
  say ""
  say "      git add -A && git commit -m first && bash PUSH-TO-GITHUB.sh"
elif printf '%s' "$ERR" | grep -qiE "could not resolve|unable to access|network|timed out"; then
  say "  No internet connection to GitHub. Check data/Wi-Fi, then:  bash PUSH-TO-GITHUB.sh"
else
  say "  Just run it once more - the first attempt often stops at the"
  say "  username/password question:"
  say "      bash PUSH-TO-GITHUB.sh"
fi
say ""
say "  If it keeps failing, copy the lines above and send them to me."
exit 1
