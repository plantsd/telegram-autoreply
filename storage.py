"""Persistent state: who has already been auto-replied to / greeted.

SQLite is used so that restarting the script does NOT re-send replies to
people who already got one.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS replied (
    user_id       INTEGER PRIMARY KEY,
    chat_id       INTEGER,
    first_seen_at TEXT NOT NULL,
    last_reply_at TEXT NOT NULL,
    reply_count   INTEGER NOT NULL DEFAULT 1,
    last_text     TEXT
);

CREATE TABLE IF NOT EXISTS greeted (
    user_id    INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL,
    greeted_at TEXT NOT NULL
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


class Store:
    """Tiny wrapper around sqlite3 with the handful of queries we need."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # first-message auto reply
    # ------------------------------------------------------------------ #
    def needs_first_reply(self, user_id: int, cooldown_days: int = 0) -> bool:
        """True if this person has never been replied to (or the cooldown lapsed)."""
        row = self.conn.execute(
            "SELECT last_reply_at FROM replied WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return True
        if cooldown_days <= 0:
            return False
        try:
            last = datetime.fromisoformat(row[0])
        except ValueError:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return _now() - last >= timedelta(days=cooldown_days)

    def record_reply(self, user_id: int, chat_id: int | None, text: str = "") -> None:
        now = _iso(_now())
        self.conn.execute(
            """
            INSERT INTO replied (user_id, chat_id, first_seen_at, last_reply_at, reply_count, last_text)
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id       = excluded.chat_id,
                last_reply_at = excluded.last_reply_at,
                reply_count   = replied.reply_count + 1,
                last_text     = excluded.last_text
            """,
            (user_id, chat_id, now, now, (text or "")[:500]),
        )
        self.conn.commit()

    def forget(self, user_id: int) -> None:
        self.conn.execute("DELETE FROM replied WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM greeted WHERE user_id = ?", (user_id,))
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # "joined Telegram" / group-join greetings
    # ------------------------------------------------------------------ #
    def needs_greeting(self, user_id: int, kind: str) -> bool:
        row = self.conn.execute(
            "SELECT kind FROM greeted WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row is None or row[0] != kind

    def record_greeting(self, user_id: int, kind: str) -> None:
        self.conn.execute(
            """
            INSERT INTO greeted (user_id, kind, greeted_at) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                kind = excluded.kind, greeted_at = excluded.greeted_at
            """,
            (user_id, kind, _iso(_now())),
        )
        self.conn.commit()

    def already_greeted(self, user_id: int) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM greeted WHERE user_id = ?", (user_id,)
            ).fetchone()
            is not None
        )

    # ------------------------------------------------------------------ #
    # housekeeping
    # ------------------------------------------------------------------ #
    def prime(self, user_ids: list[int], chat_id: int | None = None) -> int:
        """Mark users as 'already handled' without sending anything."""
        now = _iso(_now())
        for uid in user_ids:
            self.conn.execute(
                """
                INSERT INTO replied (user_id, chat_id, first_seen_at, last_reply_at, reply_count, last_text)
                VALUES (?, ?, ?, ?, 0, '')
                ON CONFLICT(user_id) DO NOTHING
                """,
                (uid, chat_id, now, now),
            )
        self.conn.commit()
        return len(user_ids)

    def stats(self) -> dict[str, object]:
        replied_total, replied_last24h = self.conn.execute(
            "SELECT COUNT(*), SUM(last_reply_at >= ?) FROM replied WHERE reply_count > 0",
            (_iso(_now() - timedelta(hours=24)),),
        ).fetchone()
        greeted_total = self.conn.execute("SELECT COUNT(*) FROM greeted").fetchone()[0]
        by_kind = dict(
            self.conn.execute("SELECT kind, COUNT(*) FROM greeted GROUP BY kind").fetchall()
        )
        return {
            "people_replied_total": replied_total or 0,
            "people_replied_last_24h": replied_last24h or 0,
            "greetings_sent": greeted_total or 0,
            "greetings_by_kind": by_kind,
        }

    def close(self) -> None:
        self.conn.close()


class JsonStore:
    """File-backed twin of :class:`Store`, for the cloud (GitHub Actions) mode.

    Runs there are short-lived, so all memory is a single JSON file that the
    workflow commits back to the repository between runs.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.data: dict = {"peers": {}, "replied": {}, "greeted": {}, "sends": []}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass  # a corrupt file must never stop the bot from running

    # ---- persistence ---------------------------------------------------- #
    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @property
    def is_first_run(self) -> bool:
        return not self.data["peers"]

    # ---- "how far have we read this chat" ------------------------------- #
    def last_seen(self, peer_id: int) -> int:
        return int(self.data["peers"].get(str(peer_id), 0) or 0)

    def set_last_seen(self, peer_id: int, message_id: int) -> None:
        self.data["peers"][str(peer_id)] = int(message_id)

    # ---- first-message replies ------------------------------------------ #
    def needs_first_reply(self, user_id: int, cooldown_days: int = 0) -> bool:
        row = self.data["replied"].get(str(user_id))
        if row is None:
            return True
        if cooldown_days <= 0:
            return False
        try:
            last = datetime.fromisoformat(row.get("at", ""))
        except ValueError:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return _now() - last >= timedelta(days=cooldown_days)

    def record_reply(self, user_id: int, chat_id: int | None, text: str = "") -> None:
        key = str(user_id)
        row = self.data["replied"].get(key, {"count": 0})
        row["at"] = _iso(_now())
        row["count"] = int(row.get("count", 0)) + 1
        row["chat_id"] = chat_id
        row["last_text"] = (text or "")[:500]
        self.data["replied"][key] = row

    # ---- greetings ------------------------------------------------------- #
    def needs_greeting(self, user_id: int, kind: str) -> bool:
        return self.data["greeted"].get(str(user_id)) != kind

    def record_greeting(self, user_id: int, kind: str) -> None:
        self.data["greeted"][str(user_id)] = kind

    def already_greeted(self, user_id: int) -> bool:
        return str(user_id) in self.data["greeted"]

    # ---- shared rate limiting across cloud runs -------------------------- #
    def recent_sends(self) -> list[float]:
        cut = (_now() - timedelta(hours=1)).timestamp()
        kept = []
        for ts in self.data.get("sends", []):
            try:
                value = float(ts)
            except (TypeError, ValueError):
                continue
            if value >= cut:
                kept.append(value)
        self.data["sends"] = kept
        return kept

    def note_send(self, when: float | None = None) -> None:
        self.data.setdefault("sends", []).append(float(when if when is not None else _now().timestamp()))

    def forget(self, user_id: int) -> None:
        self.data["replied"].pop(str(user_id), None)
        self.data["greeted"].pop(str(user_id), None)

    def stats(self) -> dict[str, object]:
        cut = _now() - timedelta(hours=24)
        recent = 0
        for row in self.data["replied"].values():
            try:
                if datetime.fromisoformat(row.get("at", "")).replace(tzinfo=timezone.utc) >= cut:
                    recent += 1
            except ValueError:
                continue
        by_kind: dict[str, int] = {}
        for kind in self.data["greeted"].values():
            by_kind[kind] = by_kind.get(kind, 0) + 1
        return {
            "people_replied_total": len(self.data["replied"]),
            "people_replied_last_24h": recent,
            "greetings_sent": len(self.data["greeted"]),
            "greetings_by_kind": by_kind,
        }

    def close(self) -> None:
        self.save()
