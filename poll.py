#!/usr/bin/env python3
"""Cloud mode: check once for new messages, reply, save state, exit.

This is what GitHub Actions runs every 30 minutes — no phone, no Termux, no
computer of yours involved. Instead of staying online and reacting instantly,
it wakes up, looks at what arrived since the last time it ran, answers the same
way the live bot would, and goes back to sleep.

    python poll.py              # one check (what the workflow runs)
    python poll.py --dry-run    # show what it WOULD do, send nothing
    python poll.py --prime      # forget every watermark: next run re-primes

Unlike the live bot, this needs SESSION_STRING in the environment (see
make-session-string.py) because there is no session file to reuse in the cloud.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl import types

from bot import display, friendly_failure, setup_logging
from config import load_config
from engine import MessageEngine, RateLimiter, build_context, load_templates
from storage import JsonStore

log = logging.getLogger("autoreply.poll")

MAX_DIALOGS = 200   # how many recent chats to look at per run
FETCH_LIMIT = 20    # how many recent messages to read per chat
TELEGRAM_SERVICE_ID = 777000


def parse_mode_value(config):
    return {"md": "md", "html": "html"}.get(config.parse_mode)


def build_client(config) -> TelegramClient:
    return TelegramClient(StringSession(config.session_string), config.api_id, config.api_hash,
                          device_model="AutoReply Cloud", app_version="1.0")


async def poll_once(config, store: JsonStore, engine: MessageEngine, client: TelegramClient,
                    *, dry_run: bool = False, prime: bool | None = None) -> dict:
    """One pass over recent chats. Returns a summary dictionary."""
    me = await client.get_me()
    me_name = getattr(me, "first_name", "") or "me"
    first_run = store.is_first_run
    if prime is None:
        prime = first_run       # first ever run only marks, never blasts old chats

    summary = {"checked": 0, "new": 0, "replied": 0, "welcomed": 0,
               "already_answered_by_you": 0, "primed": 0, "skipped": 0, "dry_run": dry_run,
               "first_run": first_run}

    if prime:
        log.info("First cloud run: noting where every chat stands, sending nothing.")

    async for dialog in client.iter_dialogs(limit=MAX_DIALOGS):
        if not dialog.is_user:
            continue
        entity = dialog.entity
        if entity is None or getattr(entity, "is_self", False):
            continue
        if entity.id == TELEGRAM_SERVICE_ID or entity.id in set(config.ignore_ids):
            continue
        if config.ignore_bots and getattr(entity, "bot", False):
            continue

        summary["checked"] += 1
        last_seen = store.last_seen(entity.id)

        # cheap check first: nothing newer than what we already handled
        last_msg = getattr(dialog, "message", None)
        if last_msg is not None and last_seen and last_msg.id <= last_seen:
            continue

        messages = await client.get_messages(entity, limit=FETCH_LIMIT)
        incoming = [m for m in messages if not m.out and m.id > last_seen]
        if not incoming:
            continue

        newest = max(incoming, key=lambda m: m.id)
        summary["new"] += len(incoming)

        # If YOU already answered from your phone, stay out of the conversation.
        if any(m.out and m.id > newest.id for m in messages):
            store.set_last_seen(entity.id, newest.id)
            summary["already_answered_by_you"] += 1
            log.info("%s — you already replied yourself, skipping", display(entity))
            continue

        if prime:
            store.set_last_seen(entity.id, newest.id)
            summary["primed"] += 1
            continue

        # Which kind of reply is this?
        kind = None
        is_signup = (isinstance(newest, types.MessageService)
                     and isinstance(newest.action, types.MessageActionContactSignUp))
        if is_signup:
            if config.contact_signup_enabled and store.needs_greeting(entity.id, "contact_signup"):
                kind = "contact_signup"
        elif config.first_reply_enabled and store.needs_first_reply(entity.id,
                                                                    config.first_reply_cooldown_days):
            kind = "first_message"

        if kind is None:
            store.set_last_seen(entity.id, newest.id)
            summary["skipped"] += 1
            continue

        context = build_context(entity, me_name=me_name, parse_mode=config.parse_mode)
        text = engine.compose(kind, context)
        if not text:
            store.set_last_seen(entity.id, newest.id)
            summary["skipped"] += 1
            continue

        if not engine.limiter.allow():
            log.warning("Hourly cap of %s messages reached — leaving %s for the next run.",
                        engine.limiter.max_per_hour, display(entity))
            break  # do NOT move the watermark: this person is handled next run

        label = "WELCOME (joined Telegram)" if kind == "contact_signup" else "FREE? FIRST MESSAGE"
        log.info("%s from %s", label, display(entity))
        if dry_run:
            log.info("[DRY-RUN] would send: %s", text.replace("\n", " ⏎ ")[:200])
        else:
            await client.send_message(entity, text, parse_mode=parse_mode_value(config),
                                      link_preview=False)
            engine.limiter.note()
            store.note_send()

        if not dry_run:
            if kind == "contact_signup":
                store.record_greeting(entity.id, "contact_signup")
                summary["welcomed"] += 1
            else:
                store.record_reply(entity.id, entity.id, text)
                summary["replied"] += 1
        store.set_last_seen(entity.id, newest.id)

    if not dry_run:
        store.save()
    return summary


async def run(args) -> int:
    config = load_config(args.env)
    if args.dry_run:
        config.dry_run = True
    if not config.session_string:
        print(friendly_failure(RuntimeError("no session string")), file=sys.stderr)
        print("\n  This mode needs a SESSION_STRING. Generate it once with:")
        print("      python make-session-string.py")
        print("  then add it to GitHub: Settings -> Secrets and variables -> Actions.\n")
        return 2
    if not config.api_id or not config.api_hash:
        for problem in config.validate():
            print(f"! {problem}", file=sys.stderr)
        return 2

    setup_logging(config)
    log.info("Cloud check starting (dry_run=%s)", config.dry_run)

    if args.prime and config.db_path.exists():
        config.db_path.unlink()          # forget every read position; next run re-primes
        log.info("State cleared — this run will re-prime all chats.")

    store = JsonStore(config.db_path)
    engine = MessageEngine(config, load_templates(config.templates_file),
                           limiter=RateLimiter(config.max_messages_per_hour))
    engine.limiter.seed(store.recent_sends())     # honour the cap across runs

    client = build_client(config)
    await client.connect()
    if not await client.is_user_authorized():
        print(friendly_failure(RuntimeError("session not authorized")), file=sys.stderr)
        print("\n  The SESSION_STRING is not valid any more. Make a new one with:")
        print("      python make-session-string.py\n")
        await client.disconnect()
        return 2

    try:
        summary = await poll_once(config, store, engine, client, dry_run=config.dry_run,
                                  prime=args.prime or None)
    finally:
        await client.disconnect()

    log.info("Done — %s", ", ".join(f"{k}={v}" for k, v in summary.items() if k != "dry_run"))
    if summary["first_run"] and summary["primed"]:
        log.info("This was the first run, so nothing was sent. The next run answers real new messages.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="One cloud check for new Telegram messages")
    parser.add_argument("--dry-run", action="store_true", help="show what would be sent")
    parser.add_argument("--prime", action="store_true", help="re-prime: forget all read positions")
    parser.add_argument("--env", help="path to an alternative .env file")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # noqa: BLE001
        print(friendly_failure(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
