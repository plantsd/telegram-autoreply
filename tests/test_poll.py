#!/usr/bin/env python3
"""Offline tests for the cloud (GitHub Actions) poller.

Simulates a fake Telegram: dialogs, message history, and the state file that
survives between runs.  Verifies the rules that really matter when nobody is
watching:

  * the first run never blasts your old chats
  * a genuinely new message gets exactly one reply
  * the same person never gets a second reply (even across runs)
  * if YOU already answered from your phone, the bot stays quiet
  * "joined Telegram" service messages get the welcome instead
  * state is saved and reloaded, so runs don't repeat themselves
  * the hourly cap is remembered across runs

    python tests/test_poll.py
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon.tl.types import (  # noqa: E402
    Message,
    MessageActionContactSignUp,
    MessageService,
    PeerUser,
    User,
)
from telethon.tl.types import UpdateNewMessage  # noqa: E402,F401

from config import Config  # noqa: E402
from engine import MessageEngine, load_templates  # noqa: E402
from poll import poll_once  # noqa: E402
from storage import JsonStore  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
random.choice = lambda seq: seq[0]      # deterministic template pick

ME = User(id=42, is_self=True, access_hash=1, first_name="HOB")
PEOPLE = {
    501: User(id=501, is_self=False, access_hash=1, first_name="Ravi", username="ravi"),
    502: User(id=502, is_self=False, access_hash=1, first_name="Neha"),
    503: User(id=503, is_self=False, access_hash=1, first_name="Sonu"),
}


class FakeDialog:
    def __init__(self, entity, message):
        self.entity = entity
        self.message = message
        self.is_user = True


class FakePeer:
    """One chat: a list of messages (incoming and outgoing)."""

    def __init__(self, entity, messages=None):
        self.entity = entity
        self.messages = list(messages or [])

    @property
    def last(self):
        return self.messages[-1] if self.messages else None

    def add_incoming(self, text="hello"):
        new_id = (self.last.id if self.last else 0) + 1
        msg = Message(id=new_id, peer_id=PeerUser(user_id=self.entity.id),
                      date=datetime.now(timezone.utc), message=text, out=False,
                      from_id=PeerUser(user_id=self.entity.id))
        self.messages.append(msg)
        return msg

    def add_outgoing(self, text="ok, talking soon"):
        new_id = (self.last.id if self.last else 0) + 1
        msg = Message(id=new_id, peer_id=PeerUser(user_id=self.entity.id),
                      date=datetime.now(timezone.utc), message=text, out=True)
        self.messages.append(msg)
        return msg

    def add_signup(self):
        new_id = (self.last.id if self.last else 0) + 1
        msg = MessageService(id=new_id, peer_id=PeerUser(user_id=self.entity.id),
                             date=datetime.now(timezone.utc),
                             action=MessageActionContactSignUp(),
                             from_id=PeerUser(user_id=self.entity.id))
        self.messages.append(msg)
        return msg


class FakeCloudClient:
    """Mimics the handful of Telethon calls poll.py uses."""

    def __init__(self, peers):
        self.peers = peers
        self.sent = []

    async def get_me(self):
        return ME

    async def iter_dialogs(self, limit=200):
        for peer in self.peers:
            yield FakeDialog(peer.entity, peer.last)

    async def get_messages(self, entity, limit=20):
        for peer in self.peers:
            if peer.entity.id == entity.id:
                return peer.messages[-limit:]
        return []

    async def send_message(self, entity, text, **_kw):
        self.sent.append((entity.id, text))
        for peer in self.peers:
            if peer.entity.id == entity.id:
                peer.add_outgoing(text)
        return True

    async def connect(self):
        return None

    async def disconnect(self):
        return None

    async def is_user_authorized(self):
        return True


def make_config(state_path: Path) -> Config:
    return Config(
        api_id=1, api_hash="0" * 32, session_string="fake",
        db_path=state_path, templates_file=BASE / "templates.json",
        delay_min_seconds=0, delay_max_seconds=0, send_typing_action=False,
        max_messages_per_hour=1000, parse_mode="md",
    )


RESULTS: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((bool(ok), name))
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"  [{detail}]" if detail and not ok else ""))


async def one_run(state_path: Path, peers, *, prime=None, dry_run=False):
    """Simulate a single GitHub Actions run (fresh process, saved state)."""
    config = make_config(state_path)
    store = JsonStore(state_path)
    engine = MessageEngine(config, load_templates(config.templates_file))
    engine.limiter.seed(store.recent_sends())
    client = FakeCloudClient(peers)
    summary = await poll_once(config, store, engine, client, dry_run=dry_run, prime=prime)
    return summary, client, store


async def main() -> int:
    state = Path("/tmp/poll_state_test.json")
    if state.exists():
        state.unlink()

    old_history = [FakePeer(PEOPLE[501]), FakePeer(PEOPLE[502])]
    old_history[0].add_incoming("purana message from last month")
    old_history[1].add_incoming("bhi purana")

    print("\n— run 1: first ever cloud run (must NOT reply to old chats) ————")
    summary, client, _ = await one_run(state, old_history)
    check("nothing sent on the first run", client.sent == [], str(client.sent))
    check("old chats were primed", summary["primed"] == 2, str(summary))
    check("state file written", state.exists())

    print("\n— run 2: Ravi sends a NEW message → one reply ————————————————")
    old_history[0].add_incoming("Hi, ye naya message hai")
    summary, client, _ = await one_run(state, old_history)
    check("exactly one reply sent", len(client.sent) == 1, str(client.sent))
    check("reply went to Ravi", client.sent and client.sent[0][0] == 501)
    check("reply uses his name", client.sent and "Ravi" in client.sent[0][1], client.sent[0][1] if client.sent else "")
    check("counted as replied", summary["replied"] == 1, str(summary))

    print("\n— run 3: nothing new → complete silence ——————————————————————")
    summary, client, _ = await one_run(state, old_history)
    check("no messages sent", client.sent == [])
    check("nothing counted", summary["replied"] == 0 and summary["welcomed"] == 0, str(summary))

    print("\n— run 4: the same person writes again → still only ONE reply ————")
    old_history[0].add_incoming("kya haal hai?")
    summary, client, _ = await one_run(state, old_history)
    check("no second auto-reply", client.sent == [], str(client.sent))
    check("watermark advanced anyway", summary["skipped"] == 1, str(summary))

    print("\n— run 5: you answered from your phone → bot stays quiet —————————")
    old_history[1].add_incoming("Neha ka naya message")
    old_history[1].add_outgoing("haan bolo, main hoon")   # you replied yourself
    summary, client, _ = await one_run(state, old_history)
    check("no bot reply when you already answered", client.sent == [], str(client.sent))
    check("counted as handled by you", summary["already_answered_by_you"] == 1, str(summary))

    print("\n— run 6: someone JOINS Telegram → welcome message ———————————————")
    peer3 = FakePeer(PEOPLE[503])
    peer3.add_signup()
    all_peers = old_history + [peer3]
    summary, client, _ = await one_run(state, all_peers)
    check("welcome sent on signup", len(client.sent) == 1, str(client.sent))
    check("welcome is for Sonu", client.sent and "Sonu" in client.sent[0][1], client.sent[0][1] if client.sent else "")
    check("counted as welcome", summary["welcomed"] == 1, str(summary))

    print("\n— run 7: state survives a fresh process (the real cloud case) ——")
    summary, client, _ = await one_run(state, all_peers)
    check("no duplicate welcome after restart", client.sent == [], str(client.sent))

    print("\n— run 8: dry run sends nothing and stores nothing —————————————")
    state2 = Path("/tmp/poll_state_dry.json")
    if state2.exists():
        state2.unlink()
    peers = [FakePeer(PEOPLE[501])]
    peers[0].add_incoming("pehla message")
    await one_run(state2, peers)                                    # primes
    peers[0].add_incoming("asli naya message")
    before = peers[0].messages[-1].id
    summary, client, store = await one_run(state2, peers, dry_run=True)
    check("dry run sent nothing", client.sent == [])
    check("dry run left the watermark alone", store.last_seen(501) == before)

    print("\n— run 9: hourly cap is remembered across runs —————————————————")
    state3 = Path("/tmp/poll_state_cap.json")
    if state3.exists():
        state3.unlink()
    peers = [FakePeer(PEOPLE[501])]
    peers[0].add_incoming("first")
    await one_run(state3, peers)                                  # prime
    peers[0].add_incoming("second")
    # pretend 60 messages already went out in the last hour
    cfg_cap = make_config(state3)
    cfg_cap = replace(cfg_cap, max_messages_per_hour=60)
    store = JsonStore(state3)
    for _ in range(60):
        store.note_send()
    store.save()
    engine = MessageEngine(cfg_cap, load_templates(cfg_cap.templates_file))
    engine.limiter.seed(store.recent_sends())
    client = FakeCloudClient(peers)
    summary = await poll_once(cfg_cap, store, engine, client)
    check("cap enforced across runs", client.sent == [], str(client.sent))
    check("person left for the next run", store.last_seen(501) < peers[0].messages[-1].id)

    print("\n— run 10: bots and Telegram itself are ignored ————————————————")
    state4 = Path("/tmp/poll_state_bots.json")
    if state4.exists():
        state4.unlink()
    bot = User(id=601, is_self=False, access_hash=1, first_name="SomeBot", bot=True)
    telegram = User(id=777000, is_self=False, access_hash=1, first_name="Telegram")
    peers = [FakePeer(bot), FakePeer(telegram)]
    peers[0].add_incoming("/start")
    peers[1].add_incoming("Your login code")
    summary, client, _ = await one_run(state4, peers)
    check("no replies to bot/Telegram", client.sent == [], str(client.sent))

    failed = [n for ok, n in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
