#!/usr/bin/env python3
"""Telegram auto-reply userbot.

What it does
------------
1. ``first_message``  – replies ONCE to every person who messages you in private
                        (state is remembered in SQLite, so restarts don't re-send).
2. ``contact_signup`` – greets people the moment Telegram tells you
                        "<name> joined Telegram" (a service message that lands in
                        your private chat with that contact).
3. ``group_join``     – optional: greets people who are added to / join your groups.

It runs on YOUR account (MTProto userbot), because Telegram bots cannot read
messages sent to a human account nor write to arbitrary users.

Usage
-----
    python bot.py                # run forever
    python bot.py --selftest     # offline check of config/templates/storage
    python bot.py --stats        # show how many people were handled
    python bot.py --prime        # mark existing chats as "already handled"
    python bot.py --reset 12345  # forget one user (they count as new again)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telethon import TelegramClient, events, types
from telethon.errors import (
    ApiIdInvalidError,
    AuthKeyUnregisteredError,
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
    UserDeactivatedBanError,
)
from telethon.sessions import StringSession

from config import Config, load_config, update_env_file
from engine import MessageEngine, build_context, load_templates
from storage import Store

log = logging.getLogger("autoreply")


# --------------------------------------------------------------------------- #
# logging / helpers
# --------------------------------------------------------------------------- #
def setup_logging(config: Config) -> None:
    # old Windows consoles use a limited character set; never let a name or emoji
    # crash the program while printing
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    file_handler = RotatingFileHandler(config.log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, config.log_level, logging.INFO))
    root.addHandler(console)
    root.addHandler(file_handler)
    logging.getLogger("telethon").setLevel(logging.WARNING)


def parse_mode_value(config: Config):
    return {"md": "md", "html": "html"}.get(config.parse_mode)


def is_ignored(user_id: int, config: Config) -> bool:
    return user_id in set(config.ignore_ids)


def target_label(target: object) -> str:
    """Short, readable name for a chat/user target."""
    if isinstance(target, types.User):
        return display(target)
    title = getattr(target, "title", None) or getattr(target, "first_name", None)
    tid = getattr(target, "id", target)
    return f"{title or 'chat'} (id={tid})"


def display(user: object) -> str:
    """Readable name for logs."""
    name = getattr(user, "first_name", "") or ""
    if getattr(user, "last_name", ""):
        name += " " + user.last_name  # type: ignore[attr-defined]
    uname = getattr(user, "username", "")
    uid = getattr(user, "id", "?")
    return f"{name.strip() or 'Unknown'} (@{uname}, id={uid})" if uname else f"{name.strip() or 'Unknown'} (id={uid})"


class Sender:
    """Sends texts with pacing, dry-run and flood-wait handling."""

    def __init__(self, client: TelegramClient, config: Config, engine: MessageEngine):
        self.client = client
        self.config = config
        self.engine = engine

    async def _send(self, target, text: str) -> bool:
        if self.config.dry_run:
            log.info("[DRY-RUN] would send to %s: %s", target_label(target),
                     text.replace("\n", " ⏎ ")[:200])
            return True
        for attempt in (1, 2):
            try:
                await self.client.send_message(target, text, parse_mode=parse_mode_value(self.config),
                                               link_preview=False)
                return True
            except FloodWaitError as exc:
                if attempt == 2 or exc.seconds > 900:
                    log.error("FloodWait %ss — giving up on this message.", exc.seconds)
                    return False
                log.warning("Telegram asked to wait %ss (flood limit) — sleeping.", exc.seconds)
                await asyncio.sleep(exc.seconds + 3)
            except Exception as exc:  # noqa: BLE001 - keep the bot alive, just log
                log.error("send_message failed (%s: %s)", type(exc).__name__, exc)
                return False
        return False

    async def send(self, target, text: str, *, show_typing: bool = True) -> bool:
        """Apply pacing + typing indicator, then send. Returns True on success."""
        if not self.engine.limiter.allow():
            log.warning("Hourly limit of %s messages reached — skipping this reply.",
                        self.engine.limiter.max_per_hour)
            return False

        delay = self.engine.next_delay()
        if delay:
            await asyncio.sleep(delay)

        if show_typing and self.config.send_typing_action and not self.config.dry_run:
            try:
                await self.client.action(target, "typing")
                await asyncio.sleep(min(2.5, max(0.8, len(text) / 40)))
            except Exception:  # typing is cosmetic; never block the reply
                pass

        ok = await self._send(target, text)
        if ok:
            self.engine.limiter.note()
        return ok


# --------------------------------------------------------------------------- #
# handlers
# --------------------------------------------------------------------------- #
def register_handlers(client: TelegramClient, config: Config, store: Store,
                      engine: MessageEngine, sender: Sender) -> None:
    me_cache: dict[str, object] = {"id": None, "name": "me"}

    async def whoami() -> dict[str, object]:
        """Fetch (once) and cache our own id + first name."""
        if me_cache["id"] is None:
            try:
                me = await client.get_me()
                me_cache["id"] = me.id
                me_cache["name"] = getattr(me, "first_name", "") or "me"
            except Exception as exc:  # noqa: BLE001
                log.debug("get_me failed: %s", exc)
                me_cache["id"] = 0
        return me_cache

    async def my_name() -> str:
        return str((await whoami())["name"])

    # ------------------------------------------------------------------ #
    # 1) first message from a person
    # ------------------------------------------------------------------ #
    @client.on(events.NewMessage(incoming=True))
    async def on_incoming(event: events.NewMessage.Event) -> None:
        message = event.message
        # service messages ("X joined Telegram", pins, …) are handled below
        if isinstance(message, types.MessageService):
            return
        if not event.is_private:
            return
        if not engine.enabled("first_message"):
            return

        try:
            user = await event.get_sender()
        except Exception as exc:  # noqa: BLE001
            log.debug("could not resolve sender: %s", exc)
            return
        if not isinstance(user, types.User) or user.is_self:
            return

        if config.ignore_bots and user.bot:
            log.debug("skipping bot %s", display(user))
            return
        if is_ignored(user.id, config):
            log.debug("skipping ignored id %s", user.id)
            return
        if config.skip_existing_contacts and getattr(user, "contact", False):
            log.debug("skipping saved contact %s", display(user))
            return

        if not store.needs_first_reply(user.id, config.first_reply_cooldown_days):
            log.debug("already replied to %s — ignoring", display(user))
            return

        context = build_context(user, me_name=await my_name(), parse_mode=config.parse_mode)
        text = engine.compose("first_message", context)
        if not text:
            return

        log.info("FIRST MESSAGE from %s — replying", display(user))
        if config.mark_as_read and not config.dry_run:
            try:
                await client.send_read_acknowledge(event.chat_id)
            except Exception:  # noqa: BLE001
                pass

        if await sender.send(user, text) and not config.dry_run:
            store.record_reply(user.id, event.chat_id, text)

    # ------------------------------------------------------------------ #
    # 2) + 3) service messages: "joined Telegram", group joins
    # ------------------------------------------------------------------ #
    @client.on(events.Raw(types=(types.UpdateNewMessage, types.UpdateNewChannelMessage)))
    async def on_service(update) -> None:  # noqa: ANN001
        message = getattr(update, "message", None)
        if not isinstance(message, types.MessageService):
            return
        action = message.action
        peer = message.peer_id
        my_id = int((await whoami())["id"] or 0)

        # --- "X joined Telegram" (private service message in your chat) ---
        if isinstance(action, types.MessageActionContactSignUp) and isinstance(peer, types.PeerUser):
            if not engine.enabled("contact_signup"):
                return
            uid = peer.user_id
            if is_ignored(uid, config) or not store.needs_greeting(uid, "contact_signup"):
                return
            try:
                user = await client.get_entity(uid)
            except Exception as exc:  # noqa: BLE001
                log.debug("cannot resolve user %s: %s", uid, exc)
                return
            if config.ignore_bots and getattr(user, "bot", False):
                return
            context = build_context(user, me_name=await my_name(), parse_mode=config.parse_mode)
            text = engine.compose("contact_signup", context)
            if not text:
                return
            log.info("JOINED TELEGRAM: %s — sending welcome", display(user))
            if await sender.send(user, text, show_typing=False) and not config.dry_run:
                store.record_greeting(uid, "contact_signup")
            return

        # --- group joins (only if enabled) ---
        if not engine.enabled("group_join"):
            return
        if isinstance(peer, types.PeerUser):
            return

        joiners: list[int] = []
        if isinstance(action, types.MessageActionChatAddUser):
            joiners = [uid for uid in action.users if uid != my_id]
        elif isinstance(action, (types.MessageActionChatJoinedByLink, types.MessageActionChatJoinedByRequest)):
            from_id = getattr(message, "from_id", None)
            if isinstance(from_id, types.PeerUser) and from_id.user_id != my_id:
                joiners = [from_id.user_id]
        else:
            return

        try:
            chat = await client.get_entity(peer)
            chat_name = getattr(chat, "title", "") or ""
        except Exception as exc:  # noqa: BLE001
            log.debug("cannot resolve chat %s: %s", peer, exc)
            return

        for uid in joiners:
            if uid in config.group_join_ignore_ids or is_ignored(uid, config):
                continue
            if not store.needs_greeting(uid, "group_join"):
                continue
            try:
                user = await client.get_entity(uid)
            except Exception as exc:  # noqa: BLE001
                log.debug("cannot resolve group member %s: %s", uid, exc)
                continue
            if config.ignore_bots and getattr(user, "bot", False):
                continue
            context = build_context(user, me_name=await my_name(), parse_mode=config.parse_mode,
                                    chat_name=chat_name)
            text = engine.compose("group_join", context)
            if not text:
                continue
            log.info("GROUP JOIN in %r: %s — welcoming", chat_name, display(user))
            if await sender.send(chat, text, show_typing=False) and not config.dry_run:
                store.record_greeting(uid, "group_join")


# --------------------------------------------------------------------------- #
# client + commands
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent


def friendly_failure(exc: Exception) -> str:
    """Turn a technical Telegram error into instructions a person can follow."""
    steps = [
        "",
        "=" * 62,
        "  THE BOT COULD NOT START - HERE IS WHAT TO DO",
        "=" * 62,
    ]
    tail = "  Your settings are saved, so you do NOT need to answer the questions again."

    if isinstance(exc, ApiIdInvalidError):
        body = [
            "  The api_id / api_hash do not match your Telegram account.",
            "",
            "  1. Open https://my.telegram.org and log in",
            "  2. Click 'API development tools'",
            "  3. Copy the api_id (number) and api_hash (long code)",
            "  4. Run the setup again:   bash install-termux.sh",
        ]
    elif isinstance(exc, PhoneNumberInvalidError):
        body = [
            "  The phone number is not valid.",
            "",
            "  Use it in this form: +919812345678   (country code first, no spaces)",
            "  Then run the setup again:   bash install-termux.sh",
        ]
    elif isinstance(exc, PhoneCodeInvalidError):
        body = [
            "  The login code was wrong.",
            "",
            "  Run this and type the new code carefully:   bash start.sh",
        ]
    elif isinstance(exc, PhoneCodeExpiredError):
        body = [
            "  The login code expired before it was used.",
            "",
            "  Run this and enter the fresh code quickly:   bash start.sh",
        ]
    elif isinstance(exc, SessionPasswordNeededError):
        body = [
            "  Your account has a 'two-step verification' password.",
            "",
            "  Run the bot again and type that password when it asks:",
            "      bash start.sh",
        ]
    elif isinstance(exc, AuthKeyUnregisteredError):
        body = [
            "  Telegram cancelled this login (this happens if you ended the",
            "  'Active sessions' from another device, or the login expired).",
            "",
            "  1. Delete the saved login:   rm -f data/autoreply.session",
            "  2. Start again:              bash start.sh   (it will ask for a code)",
        ]
    elif isinstance(exc, UserDeactivatedBanError):
        body = [
            "  THIS TELEGRAM ACCOUNT IS BLOCKED by Telegram.",
            "",
            "  A blocked account cannot send messages at all. If you were",
            "  messages-spamming many people, that is usually the reason.",
            "  Telegram support is the only way to restore it.",
        ]
        tail = "  Nothing you change in the settings will help until the account works again."
    elif isinstance(exc, FloodWaitError):
        body = [
            f"  Telegram is asking you to wait {exc.seconds} seconds.",
            "",
            "  This is Telegram's own speed limit, not an error in the bot.",
            "  Wait a few minutes, then run:   bash start.sh",
        ]
        tail = "  To avoid this, lower MAX_MESSAGES_PER_HOUR in .env (e.g. 20)."
    elif isinstance(exc, RuntimeError) and "sign-in attempts failed" in str(exc):
        body = [
            "  The login code was entered incorrectly too many times.",
            "",
            "  No problem - just start again and type the fresh code carefully:",
            "      bash start.sh --foreground",
        ]
    elif isinstance(exc, ValueError) and "Two-step verification" in str(exc):
        body = [
            "  Your account has two-step verification enabled.",
            "",
            "  Start the bot again and type your two-step password when asked:",
            "      bash start.sh --foreground",
            "",
            "  (Did not know you had one? Check Telegram > Settings >",
            "   Privacy and Security > Two-Step Verification.)",
        ]
    elif isinstance(exc, (ConnectionError, OSError, asyncio.TimeoutError)):
        body = [
            "  No internet connection to Telegram.",
            "",
            "  Check your mobile data / Wi-Fi and run again:   bash start.sh",
        ]
    else:
        body = [
            f"  Technical details (for a friend who knows computers):",
            f"      {type(exc).__name__}: {exc}",
            "",
            "  Common fixes: run  bash install-termux.sh  again,",
            "  or see the 'Something is broken' section in EASY-GUIDE.md",
        ]

    steps.extend(body)
    steps.append("")
    steps.append(tail)
    steps.append("  Full log file: logs/autoreply.log")
    steps.append("=" * 62)
    return "\n".join(steps)


def ask_two_step_password() -> str:
    """Asked only when the account really has two-step verification turned on."""
    print("", flush=True)
    print("-" * 62)
    print(" Your account has 'two-step verification' (an extra password you")
    print(" set in Telegram). Type it now.")
    print(" Forgot it? In Telegram: Settings > Privacy and Security >")
    print(" Two-Step Verification. (You can also just press Enter and fix it later.)")
    print("-" * 62, flush=True)
    try:
        import getpass

        return getpass.getpass("Two-step password: ").strip()
    except Exception:  # noqa: BLE001 - some terminals cannot hide typing
        return input("Two-step password: ").strip()


def build_client(config: Config) -> TelegramClient:
    session = StringSession(config.session_string) if config.session_string else str(config.session_file)
    if not config.session_string:
        config.session_file.parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(session, config.api_id, config.api_hash, device_model="AutoReply Bot",
                          app_version="1.0")


async def prime_existing(client: TelegramClient, store: Store, config: Config) -> None:
    """Mark everyone you already have a chat with as 'already handled'."""
    count = 0
    async for dialog in client.iter_dialogs():
        if dialog.is_user and dialog.entity and not getattr(dialog.entity, "bot", False):
            if dialog.entity.id == 777000 or getattr(dialog.entity, "is_self", False):
                continue
            store.prime([dialog.entity.id], dialog.entity.id)
            count += 1
    log.info("Primed %s existing chats — only brand-new people will get a reply now.", count)


async def run(config: Config) -> None:
    store = Store(config.db_path)
    templates = load_templates(config.templates_file)
    engine = MessageEngine(config, templates)
    client = build_client(config)

    log.info("Starting auto-reply bot (dry_run=%s, account=%s)", config.dry_run, config.session_file.name)
    for kind in ("first_message", "contact_signup", "group_join"):
        log.info("  • %-16s %s", kind, "ON" if engine.enabled(kind) else "off")
        if engine.env_flag(kind) and engine.kill_switched(kind):
            log.warning("    ↳ %s is enabled in .env but switched off in %s "
                        "(enabled:false / empty templates) — nothing will be sent.",
                        kind, config.templates_file.name)
        elif not engine.env_flag(kind) and not engine.kill_switched(kind):
            log.info("    ↳ turned off in .env; set %s=true to activate.", kind.upper())
    if config.dry_run:
        log.warning("DRY_RUN is on — nothing will actually be sent.")

    print("\n" + "-" * 62)
    print(" Logging in to Telegram. Two quick questions may appear below:")
    print("   1) your phone number, like +919812345678")
    print("   2) the login code Telegram sends to your Telegram app")
    print('      (if you set a "two-step password", it asks for that once too)')
    print(" Type the answer and press Enter. This happens only once.")
    print("-" * 62 + "\n", flush=True)

    await client.start(phone=config.phone or None)
    me = await client.get_me()
    log.info("Logged in as %s (id=%s)", getattr(me, "first_name", "?"), me.id)

    if config.prime_on_start:
        log.info("First start: marking your existing chats as already handled…")
        await prime_existing(client, store, config)
        if update_env_file(BASE_DIR / ".env", "PRIME_ON_START", "false"):
            log.info("Done. This will not run again on the next start.")
        else:
            log.warning("Done for this run. (Set PRIME_ON_START=false in .env to stop repeating it.)")

    sender = Sender(client, config, engine)
    register_handlers(client, config, store, engine, sender)
    log.info("Ready. Leave this window open — it must stay running.")
    log.info("Listening for new messages… (press Ctrl+C in this window to stop)")
    await client.run_until_disconnected()


def selftest(env_file: str | None = None) -> int:
    """Offline sanity check — no Telegram connection needed."""
    ok = True
    config = load_config(env_file)
    problems = config.validate()
    print("config problems:", problems or "none")
    # missing API credentials are fine for an offline test — anything else is not
    if [p for p in problems if "API_ID" not in p]:
        ok = False

    templates = load_templates(config.templates_file)
    store = Store(":memory:")

    fake_user = types.User(id=5551, is_self=False, access_hash=1, first_name="Ravi_Kumar",
                           username="ravi", bot=False)
    ctx = build_context(fake_user, me_name="Me", parse_mode="md", chat_name="Test Group")

    for kind in ("first_message", "contact_signup", "group_join"):
        text = MessageEngine(config, templates).compose(kind, ctx)
        print(f"{kind:16s} -> {text!r}")

    engine = MessageEngine(config, templates)
    print("rate limiter allows:", engine.limiter.allow(), "| delay range:",
          config.delay_min_seconds, "-", config.delay_max_seconds)

    print("needs_first_reply (fresh):", store.needs_first_reply(5551))
    store.record_reply(5551, 5551, "hi")
    print("needs_first_reply (after reply):", store.needs_first_reply(5551))
    print("needs_greeting (fresh):", store.needs_greeting(7777, "contact_signup"))
    store.record_greeting(7777, "contact_signup")
    print("needs_greeting (after):", store.needs_greeting(7777, "contact_signup"))
    print("stats:", store.stats())

    # handler registration smoke test (no network): decorators must accept our types
    try:
        from telethon.sessions import StringSession as _SS

        probe = TelegramClient(_SS(), 123456, "0" * 32)
        from storage import Store as _Store

        register_handlers(probe, config, _Store(":memory:"), MessageEngine(config, templates),
                          Sender(probe, config, MessageEngine(config, templates)))
        handlers = probe.list_event_handlers()
        handlers_ok = len(handlers) >= 2
        print(f"registered {len(handlers)} handlers: {[type(builder).__name__ for _cb, builder in handlers]}")
    except Exception as exc:  # noqa: BLE001
        handlers_ok = False
        print("handler registration FAILED:", exc)

    checks = {
        "handlers registered": handlers_ok,
        "reply flagged as new": store.needs_first_reply(9999),
        "reply not flagged twice": not store.needs_first_reply(5551),
        "greeting deduplicated": not store.needs_greeting(7777, "contact_signup"),
        "markdown escaped": "Ravi\\_Kumar" in ctx["first_name"],
        "rendering works": bool(engine.compose("first_message", ctx)),
    }
    for name, passed in checks.items():
        print(("  PASS  " if passed else "  FAIL  ") + name)
        ok = ok and passed

    print("\nSelftest:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram first-message / joined-Telegram auto reply")
    parser.add_argument("--dry-run", action="store_true", help="log instead of sending")
    parser.add_argument("--selftest", action="store_true", help="offline checks, no Telegram login")
    parser.add_argument("--stats", action="store_true", help="print stored counters and exit")
    parser.add_argument("--prime", action="store_true",
                        help="mark all existing chats as already handled (run once when starting)")
    parser.add_argument("--reset", type=int, metavar="USER_ID", help="forget one user")
    parser.add_argument("--reset-all", action="store_true", help="forget everyone")
    parser.add_argument("--env", help="path to an alternative .env file")
    args = parser.parse_args()

    if args.selftest:
        return selftest(args.env)

    config = load_config(args.env)
    setup_logging(config)
    if args.dry_run:
        config.dry_run = True

    if args.stats or args.reset is not None or args.reset_all:
        store = Store(config.db_path)
        if args.reset_all:
            store.conn.execute("DELETE FROM replied")
            store.conn.execute("DELETE FROM greeted")
            store.conn.commit()
            print("All stored state cleared.")
        if args.reset is not None:
            store.forget(args.reset)
            print(f"Forgot user {args.reset}.")
        if args.stats:
            print(f"Database: {config.db_path}")
            for key, value in store.stats().items():
                print(f"  {key}: {value}")
        return 0

    problems = config.validate()
    if problems:
        for p in problems:
            print(f"✗ {p}", file=sys.stderr)
        print("\nCopy .env.example to .env and fill in API_ID / API_HASH.", file=sys.stderr)
        return 2

    if args.prime:
        async def _prime() -> None:
            client = build_client(config)
            store = Store(config.db_path)
            await client.start(phone=config.phone or None)
            await prime_existing(client, store, config)
            await client.disconnect()

        asyncio.run(_prime())
        return 0

    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        print("\nBot stopped. (Start it again with: bash start.sh)")
    except Exception as exc:  # noqa: BLE001 - always explain, never dump a traceback
        message = friendly_failure(exc)
        print(message, file=sys.stderr)
        logging.getLogger("autoreply").error("%s: %s", type(exc).__name__, exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
