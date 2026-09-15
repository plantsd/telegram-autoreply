#!/usr/bin/env python3
"""Offline simulation of real Telegram updates — no login, no network.

Runs the *actual* event handlers from bot.py against fake clients/updates and
asserts what would have been sent.  Run it before going live:

    python tests/test_sim.py
"""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient, events  # noqa: E402
from telethon.sessions import StringSession  # noqa: E402
from telethon.tl.types import (  # noqa: E402
    Channel,
    Chat,
    Message,
    MessageActionChatAddUser,
    MessageActionContactSignUp,
    MessageService,
    PeerChannel,
    PeerChat,
    PeerUser,
    User,
)
from telethon.errors import FloodWaitError  # noqa: E402
from telethon import utils  # noqa: E402

from bot import Sender, register_handlers  # noqa: E402
from config import Config  # noqa: E402
from engine import MessageEngine, load_templates  # noqa: E402
from storage import Store  # noqa: E402

MY_ID = 42
BASE = Path(__file__).resolve().parent.parent

USERS = {
    501: User(id=501, is_self=False, access_hash=1, first_name="Ravi", last_name="Kumar", username="ravi"),
    502: User(id=502, is_self=False, access_hash=1, first_name="Neha", bot=True),
    503: User(id=503, is_self=False, access_hash=1, first_name="BlockedGuy"),
    504: User(id=504, is_self=False, access_hash=1, first_name="Gaurav"),
}
ME = User(id=MY_ID, is_self=True, access_hash=1, first_name="Owner")
CHAT = Chat(id=900, title="Rohtak Friends", participants_count=12, date=datetime.now(timezone.utc),
            photo=None, creator=False, left=False, deactivated=False, migrated_to=None, version=1)

CHANNEL = Channel(id=901, title="My Channel", photo=None, date=None, creator=False, left=False,
                  broadcast=True, megagroup=False, verified=False, restricted=False, signatures=False,
                  min=False, scam=False, has_link=False, has_geo=False, slowmode_enabled=False,
                  access_hash=1, username=None, restriction_reason=None)


class FakeClient:
    def __init__(self, *, flood_on: int | None = None):
        self.sent: list[tuple[object, str]] = []
        self.typing = 0
        self.read_acks = 0
        self.flood_on = flood_on
        self.me_calls = 0

    async def get_me(self):
        self.me_calls += 1
        return ME

    async def get_entity(self, entity):
        peer_id = entity if isinstance(entity, int) else utils.get_peer_id(entity)
        if peer_id in USERS:
            return USERS[peer_id]
        if peer_id == -900:      # PeerChat is marked negative by get_peer_id
            return CHAT
        if peer_id == -901:      # PeerChannel too
            return CHANNEL
        raise ValueError(f"unknown entity {entity!r}")

    async def get_input_entity(self, entity):
        return await self.get_entity(entity)

    async def action(self, *_a, **_kw):
        self.typing += 1

    async def send_read_acknowledge(self, *_a, **_kw):
        self.read_acks += 1

    async def send_message(self, target, text, **_kw):
        if isinstance(target, User) and target.id == self.flood_on:
            raise FloodWaitError(request=None)  # type: ignore[arg-type]
        self.sent.append((target, text))
        return Message(id=1, peer_id=PeerUser(user_id=MY_ID), date=datetime.now(timezone.utc), message=text)


def make_config(**over) -> Config:
    base = Config(
        api_id=1, api_hash="0" * 32, session_file=BASE / "data" / "sim",
        first_reply_enabled=True, contact_signup_enabled=True, group_join_enabled=False,
        delay_min_seconds=0, delay_max_seconds=0, send_typing_action=False,
        max_messages_per_hour=1000, parse_mode="md",
        templates_file=BASE / "templates.json", db_path=":memory:",
    )
    return replace(base, **over)


BUILD_CTX: dict[str, str] = {}


def build(config: Config):
    """Return (callbacks, client, store, engine) with handlers registered."""
    store = Store(":memory:")
    engine = MessageEngine(config, load_templates(config.templates_file))
    client = TelegramClient(StringSession(), 1, "0" * 32)
    fake = FakeClient()
    # patch the network-touching methods with offline doubles
    client.get_me = fake.get_me            # type: ignore[assignment]
    client.get_entity = fake.get_entity    # type: ignore[assignment]
    client.get_input_entity = fake.get_input_entity  # type: ignore[assignment]
    client.action = fake.action            # type: ignore[assignment]
    client.send_read_acknowledge = fake.send_read_acknowledge  # type: ignore[assignment]
    client.send_message = fake.send_message  # type: ignore[assignment]
    register_handlers(client, config, store, engine, Sender(client, config, engine))
    handlers = {}
    for callback, builder in client.list_event_handlers():
        handlers[type(builder).__name__] = callback
    return handlers, fake, store, engine, client


def private_message(client, from_id: int, text: str = "hello") -> events.NewMessage.Event:
    msg = Message(id=10, peer_id=PeerUser(user_id=from_id), date=datetime.now(timezone.utc),
                  message=text, from_id=PeerUser(user_id=from_id), out=False)
    # real Telethon pre-populates the sender from its entity cache, so do the same
    msg._client = client
    msg._sender = USERS.get(from_id)
    msg._input_sender = None
    event = events.NewMessage.Event(msg)
    event._sender = USERS.get(from_id)   # event-level cache used by get_sender()
    return event


def service_message(peer, action) -> MessageService:
    return MessageService(id=11, peer_id=peer, date=datetime.now(timezone.utc), action=action,
                          from_id=PeerUser(user_id=peer.user_id) if isinstance(peer, PeerUser) else None)


logging.basicConfig(level=logging.DEBUG, format="      %(levelname)s %(name)s: %(message)s")

# Templates are chosen at random in real use, so pin the pick for the checks
# below — otherwise an assertion can fail depending on which text was chosen.
_ORIGINAL_CHOICE = random.choice
random.choice = lambda seq: seq[0]

RESULTS: list[tuple[bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((bool(condition), name))
    print(("  PASS  " if condition else "  FAIL  ") + name + (f"  [{detail}]" if detail and not condition else ""))


async def main() -> int:
    print("\n— 1. first message from a new person ——————————————————")
    cfg = make_config()
    handlers, fake, store, _, CLIENT = build(cfg)
    from engine import build_context as _bc
    BUILD_CTX.update(_bc(USERS[501], me_name="Owner", parse_mode="md", chat_name="Rohtak Friends"))
    on_msg = handlers["NewMessage"]
    await on_msg(private_message(CLIENT, 501))
    check("one reply sent", len(fake.sent) == 1, str(fake.sent))
    check("reply is personalised", "Ravi" in fake.sent[0][1], fake.sent[0][1] if fake.sent else "")
    check("sent to the sender", getattr(fake.sent[0][0], "id", None) == 501)
    check("state recorded", not store.needs_first_reply(501))

    print("\n— 2. same person messages again ————————————————————————")
    await on_msg(private_message(CLIENT, 501, "second message"))
    check("no second auto-reply", len(fake.sent) == 1, str(len(fake.sent)))

    print("\n— 3. bots / ignored ids are skipped ————————————————————")
    fake.sent.clear()
    await on_msg(private_message(CLIENT, 502))  # bot
    check("bot ignored", len(fake.sent) == 0)
    cfg2 = make_config(ignore_ids=[503, 777000])
    handlers2, fake2, _, _, CLIENT2 = build(cfg2)
    await handlers2["NewMessage"](private_message(CLIENT2, 503))
    check("ignore list respected", len(fake2.sent) == 0)

    print("\n— 4. 'joined Telegram' service message ——————————————————")
    cfg3 = make_config()
    handlers3, fake3, store3, _, CLIENT3 = build(cfg3)
    raw = handlers3["Raw"]
    join_update_cls = __import__("telethon.tl.types", fromlist=["UpdateNewMessage"]).UpdateNewMessage
    await raw(join_update_cls(message=service_message(PeerUser(user_id=501), MessageActionContactSignUp()),
                              pts=1, pts_count=1))
    check("welcome sent on signup", len(fake3.sent) == 1, str(fake3.sent))
    check("welcome mentions the person", "Ravi" in fake3.sent[0][1])
    check("greeting remembered", not store3.needs_greeting(501, "contact_signup"))
    await raw(join_update_cls(message=service_message(PeerUser(user_id=501), MessageActionContactSignUp()),
                              pts=2, pts_count=1))
    check("not greeted twice", len(fake3.sent) == 1)

    print("\n— 5. group joins (disabled by default) ——————————————————")
    add_user = MessageActionChatAddUser(users=[504, MY_ID])
    then = datetime.now(timezone.utc)
    upd = service_message(PeerChat(chat_id=900), add_user)
    await raw(join_update_cls(message=upd, pts=3, pts_count=1))
    check("no greeting while GROUP_JOIN_ENABLED=false", len(fake3.sent) == 1)

    cfg4 = make_config(group_join_enabled=True)
    handlers4, fake4, store4, _, CLIENT4 = build(cfg4)
    upd = service_message(PeerChat(chat_id=900), add_user)
    await handlers4["Raw"](join_update_cls(message=upd, pts=1, pts_count=1))
    check("group member greeted when enabled", len(fake4.sent) == 1, str(fake4.sent))
    check("group greeting has chat name", "Rohtak Friends" in fake4.sent[0][1], fake4.sent[0][1])
    check("self is not greeted", all(getattr(t, "id", None) == 900 for t, _ in fake4.sent))

    print("\n— 6. non-service updates are ignored by the raw handler ————")
    plain = Message(id=12, peer_id=PeerUser(user_id=501), date=then, message="hi", from_id=PeerUser(user_id=501))
    await raw(join_update_cls(message=plain, pts=4, pts_count=1))
    check("raw handler ignores normal messages", True)

    print("\n— 7. hourly rate limit ——————————————————————————————————")
    cfg5 = make_config(max_messages_per_hour=1)
    handlers5, fake5, store5, engine5, CLIENT5 = build(cfg5)
    engine5.limiter.note()  # pretend one message already went out this hour
    await handlers5["NewMessage"](private_message(CLIENT5, 504))
    check("blocked by hourly cap", len(fake5.sent) == 0)
    check("not recorded when blocked", store5.needs_first_reply(504))

    print("\n— 8. dry run changes nothing ————————————————————————————")
    cfg6 = make_config(dry_run=True)
    handlers6, fake6, store6, _, CLIENT6 = build(cfg6)
    await handlers6["NewMessage"](private_message(CLIENT6, 504))
    await handlers6["Raw"](join_update_cls(message=service_message(PeerUser(user_id=504),
                                                                  MessageActionContactSignUp()),
                                           pts=5, pts_count=1))
    check("nothing actually sent", len(fake6.sent) == 0)
    check("state untouched in dry run", store6.needs_first_reply(504))

    print("\n— 9. cooldown mode (person counts as new after N days) ——")
    cfg7 = make_config(first_reply_cooldown_days=30)
    handlers7, fake7, store7, _, CLIENT7 = build(cfg7)
    await handlers7["NewMessage"](private_message(CLIENT7, 501))
    store7.conn.execute("UPDATE replied SET last_reply_at = ? WHERE user_id = 501",
                        ("2020-01-01T00:00:00+00:00",))
    store7.conn.commit()
    check("stale person is 'new' again", store7.needs_first_reply(501, 30))

    print("\n— 10. parse_mode=none and html render safely ————————————")
    cfg8 = make_config(parse_mode="none")
    handlers8, fake8, _, _, CLIENT8 = build(cfg8)
    await handlers8["NewMessage"](private_message(CLIENT8, 501))
    check("plain text has no escape marks", "\\_" not in fake8.sent[0][1], fake8.sent[0][1])
    cfg9 = make_config(parse_mode="html")
    handlers9, fake9, _, _, CLIENT9 = build(cfg9)
    await handlers9["NewMessage"](private_message(CLIENT9, 501))
    check("html mode still personalised", "Ravi" in fake9.sent[0][1])

    print("\n— 11. multiple templates rotate (real randomness) ————————")
    random.choice = _ORIGINAL_CHOICE          # put real randomness back
    cfg10 = make_config()
    handlers10, fake10, _, engine10, _client10 = build(cfg10)
    texts = set()
    for _ in range(60):
        composed = engine10.compose("first_message", dict(BUILD_CTX))
        if composed:
            texts.add(composed)
    available = len(engine10.templates["first_message"].templates)
    check("several templates in play", available >= 2, f"{available} defined")
    check("different messages are actually used", len(texts) >= 2, f"{len(texts)} distinct in 60 calls")
    check("every message is filled in", all("{" not in t for t in texts), " placeholder left over")

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
