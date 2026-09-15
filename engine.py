"""Message templates, placeholder rendering and rate limiting."""

from __future__ import annotations

import html
import json
import logging
import random
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

log = logging.getLogger("autoreply.engine")

# markdown-v1 special characters used by Telegram
_MD_SPECIAL = re.compile(r"([_*\[\]`\\])")


def escape_markdown(text: str) -> str:
    return _MD_SPECIAL.sub(r"\\\1", text or "")


def escape_html(text: str) -> str:
    return html.escape(text or "", quote=False)


class _SafeDict(dict):
    """Leaves unknown {placeholders} untouched instead of raising."""

    def __missing__(self, key):  # noqa: D105
        return "{" + key + "}"


# --------------------------------------------------------------------------- #
# templates
# --------------------------------------------------------------------------- #
KINDS = ("first_message", "contact_signup", "group_join")

DEFAULT_TEMPLATES: dict[str, Any] = {
    "first_message": {
        "enabled": True,
        "templates": ["Hi {first_name}! Thanks for the message — I'll get back to you soon. 🙂"],
    },
    "contact_signup": {
        "enabled": True,
        "templates": ["Welcome to Telegram, {first_name}! 🎉 Happy to see you here."],
    },
    "group_join": {
        "enabled": False,
        "templates": ["Welcome {mention}! 👋"],
    },
}


@dataclass
class TemplateSet:
    kind: str
    enabled: bool
    templates: list[str]

    def pick(self) -> str | None:
        if not self.enabled or not self.templates:
            return None
        return random.choice(self.templates)


def load_templates(path: Path | str) -> dict[str, TemplateSet]:
    """Load templates.json. Missing file / malformed entries fall back to defaults."""
    path = Path(path)
    raw: dict[str, Any] = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            log.error("templates file %s is not valid JSON (%s) — using defaults", path, exc)
            raw = {}
    else:
        log.warning("templates file %s not found — using built-in defaults", path)

    out: dict[str, TemplateSet] = {}
    for kind in KINDS:
        merged = dict(DEFAULT_TEMPLATES[kind])
        node = raw.get(kind)
        if isinstance(node, list):  # short form: "kind": ["text", ...]
            merged.update(enabled=True, templates=node)
        elif isinstance(node, dict):
            merged.update(node)
        templates = [t for t in merged.get("templates", []) if isinstance(t, str) and t.strip()]
        out[kind] = TemplateSet(
            kind=kind,
            enabled=bool(merged.get("enabled", True)),
            templates=templates or list(DEFAULT_TEMPLATES[kind]["templates"]),
        )
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def build_context(
    user: Any,
    *,
    me_name: str = "",
    parse_mode: str = "md",
    chat_name: str = "",
    now: datetime | None = None,
) -> dict[str, str]:
    """Build the {placeholder} values for one incoming sender."""
    now = now or datetime.now()
    esc = escape_markdown if parse_mode == "md" else (escape_html if parse_mode == "html" else (lambda s: s or ""))

    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    full = (first + " " + last).strip()
    uname = getattr(user, "username", "") or ""
    uid = getattr(user, "id", 0) or 0

    if parse_mode == "md":
        mention = f"[{esc(first or full or 'there')}](tg://user?id={uid})"
    elif parse_mode == "html":
        mention = f'<a href="tg://user?id={uid}">{esc(first or full or "there")}</a>'
    else:
        mention = first or full or "there"

    return {
        "first_name": esc(first) or "there",
        "first_name_raw": first,
        "last_name": esc(last),
        "full_name": esc(full) or "there",
        "username": esc("@" + uname) if uname else "",
        "username_raw": uname,
        "user_id": str(uid),
        "mention": mention,
        "me_name": esc(me_name),
        "chat_name": esc(chat_name),
        "date": now.strftime("%d %b %Y"),
        "time": now.strftime("%I:%M %p"),
        "day": now.strftime("%A"),
    }


def render(template: str, context: Mapping[str, str]) -> str:
    """Fill in a template, tolerating stray braces and unknown placeholders."""
    try:
        return template.format_map(_SafeDict(context))
    except (IndexError, ValueError):
        log.debug("template failed to render: %r", template)
        return template


# --------------------------------------------------------------------------- #
# rate limiting
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Sliding-window limiter: at most `max_per_hour` messages in any 60 minutes."""

    def __init__(self, max_per_hour: int = 60):
        self.max_per_hour = max(1, int(max_per_hour))
        self._sent: deque[float] = deque()

    def _trim(self, now: float) -> None:
        while self._sent and now - self._sent[0] > 3600:
            self._sent.popleft()

    def available(self) -> int:
        now = time.time()
        self._trim(now)
        return max(0, self.max_per_hour - len(self._sent))

    def allow(self) -> bool:
        return self.available() > 0

    def note(self) -> None:
        self._sent.append(time.time())

    def seed(self, timestamps: Iterable[float]) -> None:
        """Load sends from an earlier run (cloud mode works in short bursts)."""
        for ts in timestamps:
            try:
                self._sent.append(float(ts))
            except (TypeError, ValueError):
                continue
        self._sent = deque(sorted(self._sent))
        self._trim(time.time())

    def used_last_hour(self) -> int:
        now = time.time()
        self._trim(now)
        return len(self._sent)


class MessageEngine:
    """Ties templates + rendering + pacing limits together (no network here)."""

    def __init__(self, config, templates: dict[str, TemplateSet], limiter: RateLimiter | None = None):
        self.config = config
        self.templates = templates
        self.limiter = limiter or RateLimiter(config.max_messages_per_hour)

    def env_flag(self, kind: str) -> bool:
        """The .env switch for a section."""
        return bool({
            "first_message": self.config.first_reply_enabled,
            "contact_signup": self.config.contact_signup_enabled,
            "group_join": self.config.group_join_enabled,
        }.get(kind, False))

    def kill_switched(self, kind: str) -> bool:
        """True when templates.json forces this section off regardless of .env."""
        tset = self.templates.get(kind)
        return tset is not None and (not tset.enabled or not tset.templates)

    def enabled(self, kind: str) -> bool:
        """A section runs only if the .env flag is on AND templates.json allows it."""
        tset = self.templates.get(kind)
        if tset is None or not tset.enabled or not tset.templates:
            return False
        return self.env_flag(kind)

    def compose(self, kind: str, context: Mapping[str, str]) -> str | None:
        """Return the ready-to-send text, or None if disabled/not allowed right now."""
        if not self.enabled(kind):
            return None
        template = self.templates[kind].pick()
        if template is None:
            return None
        return render(template, context)

    def next_delay(self) -> float:
        lo = max(0.0, float(self.config.delay_min_seconds))
        hi = max(lo, float(self.config.delay_max_seconds))
        return random.uniform(lo, hi) if hi > 0 else 0.0
