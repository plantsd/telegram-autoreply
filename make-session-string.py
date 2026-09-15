#!/usr/bin/env python3
"""Prints a SESSION_STRING — the one-time key that lets GitHub log in as you.

The cloud version cannot use a session *file* (GitHub's machines are wiped after
every run), so it uses a long string instead, which you paste into GitHub as a
secret.  This script produces that string from your existing login.

    python make-session-string.py

If you already logged in on this device (Termux/PC), it converts that login —
no code needed.  If there is no saved login yet, it asks for your phone number
and the code Telegram sends, exactly like the normal start.

⚠️  Treat the printed string like your password: anyone who has it can use your
    Telegram. Only paste it into GitHub's "Secrets" box, never into a chat,
    a file you share, or a public place.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import load_config

BANNER = "=" * 62


def looks_valid(string: str) -> bool:
    """A real session string is a few hundred characters; empty means not logged in."""
    return bool(string) and len(string.strip()) > 60


async def make() -> int:
    config = load_config()

    problems = [p for p in config.validate() if "API_ID" in p]
    if problems:
        for problem in problems:
            print(f"! {problem}", file=sys.stderr)
        print("\n  Fill in API_ID / API_HASH first (run install-termux.sh, or edit .env).")
        return 2

    session_file = Path(f"{config.session_file}.session")
    existing = session_file.exists()

    print(BANNER)
    print("   MAKING YOUR SESSION STRING (one time only)")
    print(BANNER)
    if existing:
        print(" Found your existing login — converting it, no code needed.\n")
    else:
        print(" No saved login found on this device, so Telegram will ask for")
        print(" your phone number and the code it sends to your Telegram app.\n")

    client = TelegramClient(str(config.session_file), config.api_id, config.api_hash,
                            device_model="AutoReply Cloud", app_version="1.0")
    try:
        await client.start(phone=config.phone or None)
        authorized = await client.is_user_authorized()
        me = await client.get_me() if authorized else None
        string = StringSession.save(client.session) if authorized else ""

        if not looks_valid(string):
            print(BANNER, file=sys.stderr)
            print("! There is no finished login on this device yet, so there is no", file=sys.stderr)
            print("  key to copy. Do the login first (2 minutes), then run this again:", file=sys.stderr)
            print("", file=sys.stderr)
            print("      bash start.sh --foreground", file=sys.stderr)
            print("", file=sys.stderr)
            print("  Type the code Telegram sends you, wait for 'Ready. Leave this',", file=sys.stderr)
            print("  press Ctrl+C, then run this script again.", file=sys.stderr)
            print(BANNER, file=sys.stderr)
            return 1
    finally:
        await client.disconnect()

    print(BANNER)
    print(f" Logged in as: {getattr(me, 'first_name', '?')} (id={me.id})")
    print(BANNER)
    print()
    print(" COPY EVERYTHING BETWEEN THE LINES BELOW (long-press -> Copy):")
    print()
    print("-----------------------------8<-----------------------------")
    print(string)
    print("-----------------------------8<-----------------------------")
    print()
    print(" Then, in your phone's browser, on your GitHub repository:")
    print("   Settings -> Secrets and variables -> Actions -> New repository secret")
    print()
    print("   Name:  SESSION_STRING        Secret: (paste the line above)")
    print()
    print(" You also need two more secrets with the same names as in your .env:")
    print(f"   Name:  API_ID                Secret: {config.api_id}")
    print(f"   Name:  API_HASH              Secret: {config.api_hash}")
    print()
    print(" ⚠️  Keep this string private. If it ever leaks, go to Telegram ->")
    print("     Settings -> Devices -> terminate the session, and make a new one.")
    print(BANNER)

    if existing:
        print(" IMPORTANT: stop the phone bot before GitHub starts replying, or both")
        print(" will answer the same message. On the phone run:  bash stop.sh")
        print(BANNER)
    return 0


def main() -> int:
    try:
        return asyncio.run(make())
    except KeyboardInterrupt:
        print("\nCancelled — nothing was changed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
