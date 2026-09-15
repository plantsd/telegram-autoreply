#!/usr/bin/env python3
"""Plain-English setup wizard — no technical knowledge required.

Double-click "1-SETUP.bat" (Windows) instead of running this by hand.
It asks a few simple questions, then writes the settings file (.env) for you.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

# make sure emoji never crash an old Windows console
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

LINE = "=" * 62
THIN = "-" * 62


def say(text: str = "") -> None:
    print(text, flush=True)


def header(step: str, total: str, title: str) -> None:
    say()
    say(LINE)
    say(f"  STEP {step} of {total}: {title}")
    say(LINE)


def ask(question: str, default: str = "", optional: bool = False) -> str:
    """Ask for a value. Enter keeps the default; optional questions accept blank."""
    if optional:
        suffix = "  [press Enter to skip]"
    else:
        suffix = f"  [press Enter for: {default}]" if default else ""
    while True:
        try:
            answer = input(f"{question}{suffix}\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            say("\nSetup cancelled. Nothing was changed.")
            sys.exit(1)
        if answer:
            return answer
        if default or optional:
            return default
        say("  (This one can't be left blank — please type something.)")


def ask_choice(question: str, options: list[tuple[str, str]], default: str) -> str:
    """options = [(key, description)] — returns the chosen key."""
    while True:
        say()
        say(question)
        for key, desc in options:
            mark = " (recommended)" if key == default else ""
            say(f"   {key}) {desc}{mark}")
        try:
            answer = input(f"Type {('/'.join(k for k, _ in options))} and press Enter: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            say("\nSetup cancelled. Nothing was changed.")
            sys.exit(1)
        if not answer:
            return default
        if answer in [k for k, _ in options]:
            return answer
        say("  Please type one of the letters shown above.")


def ask_yes_no(question: str, default: bool) -> bool:
    d = "yes" if default else "no"
    ans = ask_choice(question, [("y", "Yes"), ("n", "No")], d).lower()
    return ans == "y"


def main() -> int:
    say(LINE)
    say("   TELEGRAM AUTO-REPLY  -  EASY SETUP")
    say(LINE)
    say()
    say("This takes about 5 minutes and asks 6 short questions.")
    say("There are no wrong answers. Press Enter to accept a suggested answer.")

    env_path = BASE / ".env"
    if env_path.exists():
        say()
        say("NOTE: a settings file already exists (.env).")
        if not ask_yes_no("Do you want to change your settings?", False):
            say()
            say("Keeping your current settings. Nothing changed.")
            say("To start the bot, double-click:  2-START.bat")
            return 0

    # ---------------------------------------------------------------- 1 -----
    header(1, 6, "Your two Telegram access numbers (api_id and api_hash)")
    say()
    say("These are free and are how the program is allowed to log in as you.")
    say()
    say("  1. On this computer or your phone, open:  https://my.telegram.org")
    say("  2. Log in with your phone number (the account you want to automate).")
    say("     Telegram will send you a login code inside the Telegram app.")
    say("  3. Click the link:  API development tools")
    say("  4. Fill the form:")
    say('        App title    ->  my auto reply')
    say('        Short name   ->  autoreply')
    say("        (leave everything else empty)")
    say("  5. Click  Create application  at the bottom.")
    say("  6. You will now see  api_id  (a number)  and  api_hash  (a long code).")
    say()

    while True:
        api_id = ask("Paste your api_id here (numbers only, e.g. 1234567):")
        if api_id.isdigit() and len(api_id) >= 4:
            break
        say("  That is not a number. Example: 1234567   Please try again.")

    while True:
        api_hash = ask("Paste your api_hash here (a long mix of letters and numbers):")
        if re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
            break
        if len(api_hash) >= 30:
            say("  Hmm, that looks unusual but let's use it anyway.")
            break
        say("  That looks too short. It should be 32 characters. Please try again.")

    # ---------------------------------------------------------------- 2 -----
    header(2, 6, "Your phone number")
    say()
    say("Write your number with the country code at the front, no spaces.")
    say("India example: +919812345678     (91 = country code, then the 10 digits)")
    say("If you press Enter, Telegram will simply ask for it later.")
    phone = ask("Your phone number (or press Enter to skip):", default="", optional=True)

    # ---------------------------------------------------------------- 3 -----
    header(3, 6, "What should the automatic reply say?")
    say()
    say("This is the message people get when they message you for the first time.")
    lang = ask_choice(
        "Choose your language:",
        [("1", "Simple friendly English"), ("2", "Hinglish (Hindi in English letters)"),
         ("3", "I want to type my own message")],
        "1",
    )

    custom_first = custom_welcome = ""
    if lang == "3":
        say()
        say("Type your reply and press Enter when done.")
        say("Tip: write {first_name} anywhere to insert the person's name automatically.")
        say('Example:  "Hi {first_name}! I will reply to you shortly."')
        while True:
            custom_first = ask("Your auto-reply message:")
            if custom_first.strip():
                break
            say("  The message can't be empty.")
        say()
        custom_welcome = ask(
            "If you also want a different message for people who JOIN Telegram,\n"
            "type it now (or press Enter to use the same message):",
            default="", optional=True)

    # ---------------------------------------------------------------- 4 -----
    header(4, 6, "Welcome people who join Telegram")
    say()
    say("When someone in your contacts joins Telegram, Telegram tells you:")
    say('   "<Name> joined Telegram"')
    say("The bot can reply to that with a welcome message (in that same chat).")
    welcome = ask_yes_no("Send a welcome message when someone joins Telegram?", True)

    # ---------------------------------------------------------------- 5 -----
    header(5, 6, "People added to your groups (optional)")
    say()
    say("You can also greet people who join your Telegram groups.")
    say("If you don't run big groups, leave this off.")
    groups = ask_yes_no("Greet people who join your groups?", False)

    # ---------------------------------------------------------------- 6 -----
    header(6, 6, "Old messages")
    say()
    say("If you pick 'only new', the bot will NOT reply to people who already")
    say("messaged you before today. That is usually what you want, so your old")
    say("chats don't suddenly get a reply from you.")
    old = ask_choice(
        "Who should get the automatic reply?",
        [("1", "Only NEW messages from now on"), ("2", "Everyone, including old chats")],
        "1",
    )

    # ---------------------------------------------------------------- write --
    templates_file = "templates.json"
    if lang == "2":
        templates_file = "templates.hinglish.json"
    elif lang == "3":
        templates_file = "templates.custom.json"
        base = json.loads((BASE / "templates.json").read_text(encoding="utf-8"))
        base["_readme"] = "Written by the setup wizard. Edit the texts below, then restart the bot."
        # "press Enter to use the same message" - keep that promise
        welcome_text = custom_welcome.strip() or custom_first.strip()
        base["first_message"] = {"enabled": True, "templates": [custom_first.strip()]}
        base["contact_signup"] = {"enabled": True, "templates": [welcome_text]}
        (BASE / templates_file).write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")

    safe_phone = phone if phone.startswith("+") else (("+" + phone) if phone else "")
    env_text = f"""# Settings created automatically by the setup wizard.
# If you want to change something later, just run 1-SETUP.bat again.

# --- your Telegram access (from https://my.telegram.org) --------------------
API_ID={api_id}
API_HASH={api_hash}
PHONE={safe_phone}

# where the login session is saved - keep this file private
SESSION_FILE=data/autoreply

# --- what the bot does ------------------------------------------------------
FIRST_REPLY_ENABLED=true
FIRST_REPLY_COOLDOWN_DAYS=0
CONTACT_SIGNUP_ENABLED={"true" if welcome else "false"}
GROUP_JOIN_ENABLED={"true" if groups else "false"}
GROUP_JOIN_IGNORE_IDS=
SKIP_EXISTING_CONTACTS=false
IGNORE_BOTS=true
IGNORE_USER_IDS=

# reply to people who already messaged you before today? (set by step 6)
PRIME_ON_START={"true" if old == "1" else "false"}

# --- speed limits (these keep your account safe - leave as they are) --------
REPLY_DELAY_MIN_SECONDS=3
REPLY_DELAY_MAX_SECONDS=12
MAX_MESSAGES_PER_HOUR=60
SEND_TYPING_ACTION=true
MARK_AS_READ=false

# --- texts and files -------------------------------------------------------
PARSE_MODE=md
TEMPLATES_FILE={templates_file}
DB_PATH=data/state.db
LOG_FILE=logs/autoreply.log
LOG_LEVEL=INFO

# set to true if you ever want to test without sending anything
DRY_RUN=false
"""
    env_path.write_text(env_text, encoding="utf-8")

    say()
    say(LINE)
    say("   ALL DONE - HERE IS WHAT YOU CHOSE")
    say(LINE)
    say(f"   Account phone .......... {safe_phone or 'you will be asked at login'}")
    say(f"   Auto-reply language .... { {'1': 'English', '2': 'Hinglish', '3': 'Your own text'}[lang] }")
    say(f"   Welcome on joining ..... {'Yes' if welcome else 'No'}")
    say(f"   Greet group joins ...... {'Yes' if groups else 'No'}")
    say(f"   Reply to old chats ..... {'Yes, everyone' if old == '2' else 'No, only new messages'}")
    say()
    say(THIN)
    say("   NEXT: start the bot")
    say(THIN)
    say("   On your phone (Termux):   bash start.sh")
    say("   On Windows:               double-click  2-START.bat")
    say("   On a Mac:                 double-click  2-START-Mac.command")
    say()
    say("   The first start asks for the login code Telegram sends you —")
    say("   this happens only once, ever.")
    say()

    return 0


if __name__ == "__main__":
    sys.exit(main())
