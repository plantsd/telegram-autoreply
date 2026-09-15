# ☁️ CLOUD GUIDE — run it on GitHub, nothing on your phone

**Your goal:** replies happen even when your phone is off, and nothing keeps
running in Termux.

**How this works, in one line:** your GitHub repository does a "check" every
30 minutes on GitHub's own computers, answers any new message, and remembers who
it already answered.

```
GitHub's computer wakes up (every 30 min)
        │
        ├─ takes back the saved state  ("who did I already answer?")
        ├─ looks at your recent Telegram chats
        ├─ replies to anything new — once per person, as you
        └─ saves the state back into the repository
```

**What you'll do:** one last visit to Termux (2 commands), then some taps in your
phone's browser. After that you never touch Termux again.

**What it costs:** ₹0. GitHub Free gives 2,000 automation minutes/month for
private repositories; 30-minute checks use roughly 1,400.

---

## Before you start — 2 things

1. **Stop the phone bot.** Two copies would both answer the same message.
   In Termux: `bash stop.sh` (do this now; the phone copy has done its job).
2. **Make the repository private** (recommended). The saved state lists who you
   talk to. GitHub → your repo → **Settings** → scroll to **Danger Zone** →
   **Change visibility** → *Make private*.
   *(Your Telegram key is stored as an encrypted GitHub secret either way, so a
   public repo does not leak it — but private is tidier for chat data.)*

---

## Step 1 — Make your Telegram key (last time you touch Termux)

In Termux, paste these two lines:

```bash
cd ~/projects/telegram-autoreply
bash stop.sh && ./.venv/bin/python make-session-string.py
```

It prints a long line between two `----8<----` markers. **Long-press it → Copy.**
That line is the key GitHub will use to act as you.

> ⚠️ Treat it exactly like your Telegram password. Only paste it into GitHub's
> secret box (Step 3). If it ever leaks: Telegram → **Settings → Devices** →
> terminate that session, then make a new key.

If it instead asks for your phone number and a code, that's fine too — it just
means the login wasn't saved. Type them.

---

## Step 2 — Upload the updated project (also in Termux, one command)

The new cloud files (`.github/workflows/autoreply.yml`, `poll.py`,
`make-session-string.py`) must be in your repository.

**If you re-downloaded `telegram-autoreply.zip` from the chat:**

```bash
termux-setup-storage          # skip if you already did this; answer y if asked
cd ~/projects
unzip -o /sdcard/Download/telegram-autoreply.zip
cd ~/projects/telegram-autoreply
bash PUSH-TO-GITHUB.sh
```

**If you are keeping the copy already on your phone**, tell me and I'll give you
just the new files to add — otherwise the unzip above simply overwrites with the
newest version. (Your settings in `.env` are *not* inside the zip, so nothing you
already answered is lost.)

When it asks for a password, use a **token**, and **tick both `repo` and
`workflow`** — GitHub refuses to accept automation files otherwise. The script
tells you exactly what to do if you forget, including the direct link:
`https://github.com/settings/tokens` → *Generate new token (classic)*.

When it finishes you should see **DONE — your project is on GitHub ✔**.

---

## Step 3 — Give GitHub your 3 secrets

In your phone's browser, open your repository, then:

**Settings → Secrets and variables → Actions → New repository secret**

Add these three, one at a time (name exact, letters in capitals):

| Name | Secret (the value) |
|---|---|
| `API_ID` | the number from my.telegram.org (same as in your `.env`) |
| `API_HASH` | the long code from my.telegram.org |
| `SESSION_STRING` | the long line you copied in Step 1 |

You can check the first two by opening `~/projects/telegram-autoreply/.env` in
Termux — or just copy them from my.telegram.org again.

---

## Step 4 — Switch it on

1. Open the **Actions** tab of your repository.
2. If you see a button saying *"I understand my workflows, go ahead and enable
   them"* — tap it.
3. On the left, tap **Telegram auto-reply**.
4. Tap **Run workflow** → tick **dry_run** (so nothing is sent) → **Run workflow**.
5. Wait ~1 minute, tap the run, tap the step **Check for new messages**, and read
   the log. You should see something like:

```
Cloud check starting (dry_run=True)
First cloud run: noting where every chat stands, sending nothing.
Done — checked=37, new=0, primed=37, ...
This was the first run, so nothing was sent.
```

That first run is normal and important: it records where every chat stands, so it
never blasts your old conversations.

6. Now run it again — this time **leave dry_run unticked**. From here on it runs
   by itself every 30 minutes.

---

## Step 5 — Prove it works

Ask a friend (or your second account) to send you a **new** message. Within about
30 minutes:

* their message gets a reply from you (they'll see it as a normal message),
* in your repository, the `state` branch gets a fresh commit,
* the **Actions** tab shows a green ✓ for that run.

Impatient? Tap **Actions → Telegram auto-reply → Run workflow** to check right now.

---

## How it behaves (good to know)

| Situation | What the cloud bot does |
|---|---|
| Someone messages you for the first time | Replies once, from your rotating templates |
| The same person messages again later | Stays quiet — one reply per person, forever |
| **You** already answered manually | Stays quiet (it checks whether you replied after them) |
| Someone's Telegram says *"joined Telegram"* | Sends the welcome message to that chat |
| Message arrives at 10:02 | Answered at the next check (~10:30) |
| More than 30 messages in an hour | Pauses and continues next run (protects your account) |
| Anything is already answered | Nothing happens — silence |

**Delays are the one real trade-off:** replies arrive at the next check, not in
seconds. If you want it faster, see below.

---

## Making it faster (optional)

Free private repositories allow 2,000 automation minutes/month, which is why the
default is every 30 minutes. Two options if you want quicker replies:

* **Every 5–10 minutes, free:** make the repository **public** (Actions minutes are
  unlimited for public repos), then edit `.github/workflows/autoreply.yml` and
  change `cron: "*/30 * * * *"` to `cron: "*/5 * * * *"` — a 3-tap edit in the
  GitHub app. Trade-off: the `state` branch (chat ids, names, reply texts) becomes
  publicly visible. Your Telegram key stays secret.
* **Instant replies, free:** a small always-free cloud server (Oracle Cloud has an
  always-free tier). Ask me and I'll write that version — it uses exactly the same
  files, just stays awake.

---

## Everyday management

| I want to… | Do this |
|---|---|
| Check it's alive | Repo → **Actions** → is there a recent green ✓? |
| See what it answered | **Actions** → latest run → **Check for new messages** → log shows *FIRST MESSAGE from …* |
| Run it right now | **Actions** → **Telegram auto-reply** → **Run workflow** |
| Change the reply text | Edit `templates.json` in the repo (🖉 pencil icon) → commit. Next run uses it. |
| Turn it off completely | **Actions** → **Telegram auto-reply** → **⋯** → *Disable workflow* |
| Pause for a day | Same as above, then *Enable workflow* when back |
| Reset who's been answered | Repo → switch to the **state** branch → delete `data/state.json` → next run re-primes (nobody gets replied to again until they message) |
| Cancel access completely | Telegram → **Settings → Devices** → terminate the session, then delete the `SESSION_STRING` secret |

---

## Something is broken?

**Red ✗ on the run:**
Open the failed run → **Check for new messages** → read the last lines. The bot
prints plain-English advice, e.g.:

| Log says | Fix |
|---|---|
| *The api_id / api_hash do not match* | Re-check `API_ID` and `API_HASH` secrets |
| *The SESSION_STRING is not valid any more* | Make a new key (Step 1), then update the `SESSION_STRING` secret |
| *This mode needs a SESSION_STRING* | The `SESSION_STRING` secret is missing or misspelled |
| *Hourly cap reached* | Normal — it continues next run |
| *refusing to allow a Personal Access Token to create or update workflow* | Token needs the `workflow` tick (Step 2) |

**It runs but nobody gets replies:**

1. Did the person message you **after** you switched this on? (Old chats are
   deliberately ignored — `state.json` remembers them.)
2. Had you already auto-replied to them once? One reply per person, forever.
3. Did you reply to them yourself from your phone? Then the bot stays quiet —
   by design.
4. Try **Run workflow** with `dry_run` ticked: the log will say what it *would* do.

**I want it snappier** → see "Making it faster" above, or ask me for the free
cloud-server version (~5 seconds).

**Warning signs about your account:** if Telegram ever restricts you, stop the
workflow immediately (Actions → Disable workflow) and lower
`MAX_MESSAGES_PER_HOUR` in the workflow file. Auto-replying to people who message
you first is normal usage — mass-messaging strangers is what gets accounts limited.
