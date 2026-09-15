# Telegram Auto-Reply Bot

> **New to this? On a phone?** Read **[EASY-GUIDE.md](EASY-GUIDE.md)** instead of this
> file — it explains everything in plain words for Android/Termux, with one command
> (`bash install-termux.sh`) that sets everything up for you. This README is the
> technical reference.
>
> **Want it to run without your phone being on?** Read
> **[CLOUD-GUIDE-GITHUB.md](CLOUD-GUIDE-GITHUB.md)** — GitHub Actions runs
> `poll.py` every 30 minutes, so nothing runs on your device at all.

Replies automatically to people who message you, and sends a welcome when someone
in your contacts **joins Telegram**.

| # | Trigger | What happens | Default |
|---|---------|--------------|---------|
| 1 | **A person's first private message to you** | One friendly reply, personalised with their name. Each person is replied to **once** (remembered in a database, survives restarts). | ON |
| 2 | **"«Name» joined Telegram"** service message | A welcome message is sent to that person — it lands in the same chat, so it looks like you messaged them. | ON |
| 3 | Someone is added to / joins your group | Optional greeting (off by default). | off |

---

## ⚠️ Read this first: why it's not a normal bot

You asked for something that replies to **everyone who messages you** and to
people **joining Telegram**. Two hard facts about Telegram:

1. A normal bot (BotFather token) can only see messages sent to *the bot itself*.
   It cannot read messages people send to your personal account, and it cannot
   write to arbitrary users — Telegram blocks that on purpose (`PEER_ID_INVALID`).
2. There is no bot API event for "a contact joined Telegram" — that arrives as a
   *service message inside your own account's chat*, so only a client logged in
   **as you** can see it.

So this project is a **userbot**: a small program that logs into **your own
account** with Telegram's MTProto API (via [Telethon](https://docs.telethon.dev))
and behaves like your phone being online and online-only-for-auto-replies.
It is the only way to do exactly what you asked.

Consequences you should know before running it:

* The login session file (`data/autoreply.session`) is a **full login to your account**.
  Never share it, never commit it. Use a VPS you control.
* Auto-messaging from a user account is a grey area in Telegram's ToS. Sending to
  people who messaged you first, and to your own contacts, is normal usage — but
  bulk/unsolicited messaging can get the account limited or banned. The built-in
  pacing (random 3–12 s delay, max 60 messages/hour) exists to protect you.
* Only run **one instance** with the same session file at a time.

---

## Quick start (5 steps, ~5 minutes)

### 1. Get your API credentials
Go to **https://my.telegram.org** → log in with your phone number → **API development
tools** → create an app (any name, platform "Desktop"); you get an `api_id` and `api_hash`.
Use the same phone number as the account you want to automate.

### 2. Install
```bash
cd telegram-autoreply
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
nano .env        # fill in API_ID, API_HASH, PHONE
```

### 4. Test safely (nothing is sent)
```bash
python bot.py --selftest      # offline checks of config/templates/database
python tests/test_sim.py      # 23 simulated scenarios, no Telegram login
python bot.py --dry-run       # logs in, prints what it WOULD send
```
`--dry-run` writes to the log instead of sending and **does not** mark anyone as
replied, so you can safely run it on your real account.

### 5. Go live
```bash
python bot.py --prime         # first run only: mark existing chats as "already handled"
python bot.py                 # start auto-replying
```
On the very first start Telegram asks for the login code (and your 2FA password if
enabled) — it's saved to `data/autoreply.session` and never asked again.

> `--prime` stops the bot from greeting your whole contact list on day one. Only
> people who message you (or join Telegram) **after** that point get auto-replies.

Prefer one command? `./run.sh` still does setup + start (Linux/macOS), `run.bat` on Windows.

---

## Two ways to run it

| | Live mode (`bot.py`) | Cloud mode (`poll.py`) |
|---|---|---|
| Runs on | your phone/PC/VPS, always on | GitHub Actions, once every 30 min |
| Reply speed | seconds | up to ~30 minutes |
| Needs | session file | `SESSION_STRING` secret |
| State | `data/state.db` (SQLite) | `data/state.json`, committed to a `state` branch |
| Best for | instant replies | zero maintenance, no device left on |

Cloud mode reuses the same `config.py`, `engine.py`, `templates.json` and reply
rules — only the trigger differs. It also never double-answers: if you replied to
someone yourself after their message, that chat is skipped.

## Commands

```bash
python bot.py                  # run forever
python bot.py --dry-run        # simulate, send nothing
python bot.py --selftest       # offline sanity checks
python bot.py --stats          # how many people replied to / greeted
python bot.py --prime          # mark all existing chats as handled
python bot.py --reset 123456   # forget one user -> they count as new again
python bot.py --reset-all      # forget everyone
python bot.py --env other.env  # use a different config file
python bot.py --help
```

Live log (also rotated in `logs/autoreply.log`):
```
2026-09-15 10:04:11 | INFO | FIRST MESSAGE from Ravi Kumar (@ravi, id=123456789) — replying
2026-09-15 10:09:02 | INFO | JOINED TELEGRAM: Neha (id=987654321) — sending welcome
```

---

## Message templates — `templates.json`

```json
"first_message": {
  "enabled": true,
  "templates": [
    "Hi {first_name}! 👋 Thanks for messaging. I'll reply properly as soon as I'm free.",
    "Hey {first_name}, thanks for reaching out! 🙌 I'll get back to you shortly."
  ]
}
```
* Several templates → one is picked **at random** per person, so replies feel human.
* Set `"enabled": false` for a **hard off switch** (wins over `.env`).
* Hinglish version ready to use: set `TEMPLATES_FILE=templates.hinglish.json` in `.env`.

### Placeholders
| Placeholder | Gives | Example |
|---|---|---|
| `{first_name}` `{last_name}` `{full_name}` | name, **auto-escaped** for the parse mode | `Ravi\_Kumar` |
| `{username}` | `@handle`, empty if they have none | `@ravi` |
| `{mention}` | clickable mention (works even without a username) | `[Ravi](tg://user?id=…)` |
| `{user_id}` | numeric Telegram id | `123456789` |
| `{me_name}` `{chat_name}` | your first name / the group title | `Owner`, `Rohtak Friends` |
| `{date}` `{time}` `{day}` | current date/time of your machine | `15 Sep 2026`, `10:04 AM`, `Tuesday` |

Names are escaped automatically, so `Hi {first_name}!` will never break because
someone put `*` or `_` in their name. Don't wrap `{first_name}` in `*...*` yourself
unless you want bold — use `**{first_name}**` for bold text.

---

## Settings — `.env`

| Variable | Default | Meaning |
|---|---|---|
| `API_ID`, `API_HASH` | — | **required**, from my.telegram.org |
| `PHONE` | — | optional, avoids typing your number at first login |
| `SESSION_FILE` | `data/autoreply` | login session (keep secret) |
| `SESSION_STRING` | — | alternative to a session file, for headless hosts |
| `FIRST_REPLY_ENABLED` | `true` | feature 1 |
| `FIRST_REPLY_COOLDOWN_DAYS` | `0` | `0` = reply once ever; `30` = they count as new again after 30 quiet days |
| `CONTACT_SIGNUP_ENABLED` | `true` | feature 2 |
| `GROUP_JOIN_ENABLED` | `false` | feature 3 |
| `GROUP_JOIN_IGNORE_IDS` | — | user ids to never greet in groups |
| `SKIP_EXISTING_CONTACTS` | `false` | don't greet people you already have saved |
| `PRIME_ON_START` | `false` | `true` = on the next start, mark existing chats as handled and switch itself off (same as `--prime`, for non-technical users) |
| `IGNORE_BOTS` | `true` | never auto-reply to bots |
| `IGNORE_USER_IDS` | — | extra ids to ignore (777000 = Telegram itself is always ignored) |
| `REPLY_DELAY_MIN_SECONDS` / `MAX` | `3` / `12` | random wait before sending — makes it look human, avoids flood limits |
| `MAX_MESSAGES_PER_HOUR` | `60` | hard cap; further replies are skipped until the hour rolls over |
| `SEND_TYPING_ACTION` | `true` | shows "typing…" briefly before the reply |
| `MARK_AS_READ` | `false` | also mark incoming messages as read |
| `PARSE_MODE` | `md` | `md`, `html` or `none` |
| `TEMPLATES_FILE` | `templates.json` | which template file to use |
| `DB_PATH` | `data/state.db` | who was already replied to / greeted |
| `LOG_FILE`, `LOG_LEVEL` | `logs/autoreply.log`, `INFO` | logging |
| `DRY_RUN` | `false` | same as `--dry-run` |

**First-private-message replies only happen in 1-to-1 chats** — messages in groups
are ignored, so the bot never spams a group.

---

## About the "joined Telegram" feature — how it really behaves

Telegram sends *you* a service message `«Name» joined Telegram` when somebody
**in your phone contacts** creates a Telegram account. The bot listens for exactly
that message and replies in that chat — so the person receives a normal message
from you, which is what you asked for. Real-world caveats:

* It fires **only for people who already had your number saved in their contacts**
  (Telegram delivers it because you're the one who invited them via your contacts).
* If the person already had a Telegram account, **no event is sent** — there is
  nothing to detect. Their first *message* to you is then handled by feature 1.
* If you import contacts later, Telegram may emit these events in bulk — the bot
  respects `MAX_MESSAGES_PER_HOUR`, and `SKIP_EXISTING_CONTACTS=true` is a good
  safety net in that situation.

Feature 1 (first message) therefore covers everyone: friends, strangers,
people who just joined Telegram, and existing accounts.

---

## Run it 24×7

**Linux VPS (recommended)** — the bot only needs ~40 MB RAM:
```bash
sudo apt install python3-venv git -y
# copy the folder to the server, then follow Quick start
sudo cp deploy/autoreply.service /etc/systemd/system/     # edit User= and paths first
sudo systemctl daemon-reload && sudo systemctl enable --now autoreply
journalctl -u autoreply -f          # live log
```

**Quick & dirty keep-alive** (survives closing the terminal):
```bash
sudo apt install screen -y
screen -S autoreply
python bot.py            # Ctrl+A then D to detach;  screen -r autoreply to return
```

**Windows:** run `run.bat`, or `pythonw bot.py` for a windowless start; add it to
Task Scheduler with "At log on" if you want it automatic.

**Android (Termux)** — no PC needed, see [EASY-GUIDE.md](EASY-GUIDE.md):
```bash
pkg install python git tmux && bash install-termux.sh   # one command does everything
bash start.sh        # runs in the background (tmux) and survives closing Termux
bash status.sh       # is it running? how many people replied to?
bash watch.sh        # live activity     bash stop.sh  -> stop
```
`start.sh` holds a wake-lock so Android doesn't freeze it, `install-termux.sh` is
also the repair tool, and `termux-boot-autoreply.sh` brings the bot back
automatically after a phone reboot (copy it into `~/.termux/boot/`, see
[EASY-GUIDE.md](EASY-GUIDE.md)). For reliability, keep battery optimisation off for Termux,
and note that a phone that is off/offline cannot receive updates — a VPS is more
reliable for a 24×7 setup.

Your phone should stay online for Telegram to deliver events instantly — but
Telegram keeps ~24 h of offline updates, and this bot also receives service
messages it missed while offline is not guaranteed, so a VPS is the reliable option.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `API_ID / API_HASH are missing` | fill `.env` (copy from `.env.example`); `API_ID` must be digits, `API_HASH` the 32-char hex |
| `database is locked` | another instance is running — only run one at a time |
| Nothing happens at all | run `python bot.py --dry-run` and check the log lines; make sure `.env` has `FIRST_REPLY_ENABLED=true` |
| Someone got no reply | they're already in `state.db` (`python bot.py --stats`, `--reset <id>` to retry) or a message limit was hit |
| `FloodWaitError` | Telegram throttling — the bot sleeps automatically; lower `MAX_MESSAGES_PER_HOUR` |
| Sends but no "typing…" | some clients don't show it in the first seconds; harmless |
| Emoji/`{first_name}` shows as `*` | your `PARSE_MODE` is `md` and the name contains characters besides `*`. Names are escaped automatically — don't add your own `*…*` around them |
| Session expired / "AuthKeyUnregistered" | Telegram revoked it — delete `data/autoreply.session`, run again, re-enter the code |
| Forgot who was already messaged | `python bot.py --reset-all` |
| `ApiIdInvalidError` | api_id/api_hash wrong — the bot prints plain-English recovery steps instead of a traceback |
| Wizard says a settings file exists | it's re-runnable; answer `y` to change answers, `n` to keep them |

## Files

```
bot.py                  main program (live handlers, commands, CLI)
poll.py                 cloud mode: one check, reply, save, exit
make-session-string.py  prints the SESSION_STRING for cloud mode
.github/workflows/autoreply.yml   the every-30-minutes GitHub job
config.py               .env parsing + validation
engine.py               templates, placeholder rendering, rate limiting
storage.py              SQLite state (who was replied to / greeted)
templates.json          reply texts (English)
templates.hinglish.json reply texts (Hinglish)
templates.custom.json   written by the wizard if you type your own text
setup_wizard.py         the 6 plain-English questions (run by the installers)
install-termux.sh       one-command setup for Android/Termux
start.sh stop.sh watch.sh status.sh    phone-friendly controls (Termux/Linux/macOS)
termux-boot-autoreply.sh               auto-start after phone reboot (Termux:Boot)
PUSH-TO-GITHUB.sh                      upload to GitHub with a secret-file guard
1-SETUP.bat 2-START.bat 3-TEST-SAFE.bat 4-STATUS.bat 5-FIX-EVERYTHING.bat   Windows
1-SETUP-Mac.command 2-START-Mac.command                                    macOS
.env.example            all settings, documented
tests/test_sim.py       23 offline scenarios — real handlers, fake Telegram
deploy/autoreply.service systemd unit for a VPS
run.sh / run.bat        one-command launchers
data/, logs/            created at runtime (session file, database, logs)
```

## Safety checklist

- [ ] `.env`, `data/` and `logs/` are git-ignored and never shared.
- [ ] You ran `--dry-run` at least once.
- [ ] You ran `--prime` before the first live start.
- [ ] `MAX_MESSAGES_PER_HOUR` is a number you'd be comfortable sending manually.
- [ ] You're not using it to mass-message strangers — that's what gets accounts banned.
