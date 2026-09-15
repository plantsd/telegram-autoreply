"""Configuration for the Telegram auto-reply userbot.

Everything is driven by environment variables; a `.env` file next to this
script is loaded automatically.  See `.env.example` for the full list.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional dependency, but strongly recommended
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover

    def load_dotenv(*_args, **_kwargs):  # type: ignore[misc]
        return False


BASE_DIR = Path(__file__).resolve().parent

# Telegram's own service account. Never reply to it.
TELEGRAM_SERVICE_ID = 777000


# --------------------------------------------------------------------------- #
# small typed env helpers
# --------------------------------------------------------------------------- #
def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _int_list(name: str) -> list[int]:
    raw = os.getenv(name, "")
    out: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except ValueError:
            continue
    return out


def _path(name: str, default: str) -> Path:
    raw = os.getenv(name, "").strip() or default
    p = Path(raw).expanduser()
    return p if p.is_absolute() else (BASE_DIR / p)


def _str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return default if raw is None or not raw.strip() else raw.strip()


# --------------------------------------------------------------------------- #
# config object
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    # --- credentials (from https://my.telegram.org -> API development tools) --
    api_id: int = 0
    api_hash: str = ""
    phone: str = ""  # optional, makes the first login non-interactive
    session_file: Path = BASE_DIR / "data" / "autoreply"
    session_string: str = ""  # alternative to a session file (headless hosts)

    # --- behaviour ------------------------------------------------------------
    dry_run: bool = False
    first_reply_enabled: bool = True
    # 0 = reply to a person only once, ever. N = they count as "new" again
    # after N days of silence.
    first_reply_cooldown_days: int = 0
    contact_signup_enabled: bool = True  # "X joined Telegram" service message
    group_join_enabled: bool = False  # greet people added to your groups
    group_join_ignore_ids: list[int] = field(default_factory=list)

    skip_existing_contacts: bool = False  # don't greet people you already saved
    prime_on_start: bool = False  # first run(s): mark existing chats as handled
    ignore_bots: bool = True
    ignore_ids: list[int] = field(default_factory=list)

    # --- pacing / anti-flood ---------------------------------------------------
    delay_min_seconds: float = 3.0
    delay_max_seconds: float = 12.0
    max_messages_per_hour: int = 60
    send_typing_action: bool = True
    mark_as_read: bool = False
    parse_mode: str = "md"  # md | html | none

    # --- files / logging -------------------------------------------------------
    templates_file: Path = BASE_DIR / "templates.json"
    db_path: Path = BASE_DIR / "data" / "state.db"
    log_file: Path = BASE_DIR / "logs" / "autoreply.log"
    log_level: str = "INFO"

    def validate(self) -> list[str]:
        """Return a list of human readable problems (empty = all good)."""
        problems: list[str] = []
        if not self.api_id or not self.api_hash:
            problems.append(
                "API_ID / API_HASH are missing. Get them from "
                "https://my.telegram.org -> API development tools."
            )
        if self.delay_min_seconds < 0 or self.delay_max_seconds < 0:
            problems.append("Delay values cannot be negative.")
        if self.delay_max_seconds < self.delay_min_seconds:
            problems.append("REPLY_DELAY_MAX_SECONDS must be >= REPLY_DELAY_MIN_SECONDS.")
        if self.parse_mode not in {"md", "html", "none", ""}:
            problems.append("PARSE_MODE must be one of: md, html, none.")
        if self.max_messages_per_hour < 1:
            problems.append("MAX_MESSAGES_PER_HOUR must be at least 1.")
        return problems


def load_config(env_file: str | os.PathLike[str] | None = None) -> Config:
    """Load config from .env + environment variables."""
    if env_file:
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(BASE_DIR / ".env", override=False)

    cfg = Config(
        api_id=_int("API_ID", 0),
        api_hash=_str("API_HASH", ""),
        phone=_str("PHONE", ""),
        session_file=_path("SESSION_FILE", "data/autoreply"),
        session_string=_str("SESSION_STRING", ""),
        dry_run=_bool("DRY_RUN", False),
        first_reply_enabled=_bool("FIRST_REPLY_ENABLED", True),
        first_reply_cooldown_days=_int("FIRST_REPLY_COOLDOWN_DAYS", 0),
        contact_signup_enabled=_bool("CONTACT_SIGNUP_ENABLED", True),
        group_join_enabled=_bool("GROUP_JOIN_ENABLED", False),
        group_join_ignore_ids=_int_list("GROUP_JOIN_IGNORE_IDS"),
        skip_existing_contacts=_bool("SKIP_EXISTING_CONTACTS", False),
        prime_on_start=_bool("PRIME_ON_START", False),
        ignore_bots=_bool("IGNORE_BOTS", True),
        ignore_ids=_int_list("IGNORE_USER_IDS") + [TELEGRAM_SERVICE_ID],
        delay_min_seconds=_float("REPLY_DELAY_MIN_SECONDS", 3.0),
        delay_max_seconds=_float("REPLY_DELAY_MAX_SECONDS", 12.0),
        max_messages_per_hour=_int("MAX_MESSAGES_PER_HOUR", 60),
        send_typing_action=_bool("SEND_TYPING_ACTION", True),
        mark_as_read=_bool("MARK_AS_READ", False),
        parse_mode=_str("PARSE_MODE", "md").lower(),
        templates_file=_path("TEMPLATES_FILE", "templates.json"),
        db_path=_path("DB_PATH", "data/state.db"),
        log_file=_path("LOG_FILE", "logs/autoreply.log"),
        log_level=_str("LOG_LEVEL", "INFO").upper(),
    )
    return cfg


def update_env_file(path: Path | str, key: str, value: str) -> bool:
    """Change one line in a .env file (used to switch PRIME_ON_START off again)."""
    path = Path(path)
    if not path.exists():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    replaced = False
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False
