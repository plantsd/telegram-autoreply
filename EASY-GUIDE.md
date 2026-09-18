# 📱 EASY GUIDE — Telegram auto-reply on your Android phone

**Made for your setup:** Termux workspace `~/projects` · GitHub repo
`https://github.com/plantsd/telegram-autoreply`

> **Want the bot to run without your phone?** Use
> **[CLOUD-GUIDE-GITHUB.md](CLOUD-GUIDE-GITHUB.md)** instead — your GitHub runs the
> checks every 30 minutes and Termux is only needed twice, one time.

Everything happens on your phone, in an app called **Termux**. You will copy-paste
**one line** and answer **6 easy questions**. Total time: about 15 minutes.

What you get, on **your own Telegram account**:

* Anyone who messages you for the **first time** → gets one friendly reply from you.
* Anyone who **joins Telegram** (you get the *"‹name› joined Telegram"* message) → gets a welcome message.
* Every person is replied to **only once**, so nobody gets spammed.

---

## Step 0 — Install Termux (5 minutes)

⚠️ **Do not** install Termux from the Play Store — that version is old and broken.

1. Open your browser and go to **https://f-droid.org/packages/com.termux/**
2. Tap **Download APK**, open it, allow "install unknown apps" if Android asks.
3. Open **Termux**. You'll see a black screen with text. That's normal.

---

## Step 1 — Get the bot files onto your phone

Pick **one** of these two ways.

### Way A — Straight from your own GitHub repo (recommended)

Your repository: **https://github.com/plantsd/telegram-autoreply**

In Termux, type these 3 lines:

```bash
pkg install -y git
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/plantsd/telegram-autoreply.git
cd ~/projects/telegram-autoreply
```

> Your repo is empty right now, so first you need the files in it. Either use
> **Way B** below (unzip on the phone, then upload with `bash PUSH-TO-GITHUB.sh`
> — one command), or upload them once from the GitHub website:
> in your repo tap **Add file → Upload files**, pick the files, then **Commit changes**.
>
> Your Telegram login and settings are **never** uploaded — the included
> `.gitignore` blocks them. You can keep the repo public.

### Way B — From the ZIP on your phone

1. Download **`telegram-autoreply.zip`** from this chat into your phone's **Download** folder.
2. In Termux, type these lines one by one:

```bash
termux-setup-storage
pkg install -y unzip
cd ~/projects
unzip -o /sdcard/Download/telegram-autoreply.zip
rm -f telegram-autoreply.zip
cd ~/projects/telegram-autoreply
ls
```

The `ls` should list files like `bot.py`, `install-termux.sh`, `EASY-GUIDE.md`.
(If it only shows `telegram-autoreply.zip`, you are one folder too high — run
`cd ~/projects/telegram-autoreply`.)

(After the first line, Android shows a popup asking for permission to access your
files — tap **Allow**. If the unzip line says "No such file", check that the ZIP is
really in your phone's **Download** folder.)

You now have the project in **`~/projects/telegram-autoreply`** — which is exactly
where your Termux workspace is (`~/projects`).

---

## Step 2 — One command does the rest

Make sure you are inside the `telegram-autoreply` folder (the line before your typing
should show it), then type:

```bash
bash install-termux.sh
```

It will install the needed programs (1–3 minutes), then start asking questions.

---

## Step 3 — The 6 questions

### Question 1 — "api_id and api_hash"
This is how the program is allowed to log in as you. It's free.

1. On your phone, open **https://my.telegram.org**
2. Log in with your phone number (the code arrives in your Telegram app).
3. Tap **API development tools**.
4. Fill in:
   * **App title** → `my auto reply`
   * **Short name** → `autoreply`
   * Leave the rest empty.
5. Tap **Create application**.
6. You'll now see **api_id** (a number) and **api_hash** (a long code).
7. Copy them into Termux one at a time (long-press → Paste), pressing Enter after each.

### Question 2 — your phone number
Type it as `+919812345678` (country code first, no spaces). Or just press Enter and
Telegram will ask later.

### Question 3 — what should the reply say?
Type `1` for simple English, `2` for Hinglish, or `3` to write your own message.
If you choose `3`, write your text. Tip: put `{first_name}` anywhere and the person's
name is filled in automatically. Example:

```
Hi {first_name}! Main abhi busy hoon, thodi der mein reply karta hoon.
```

### Question 4 — welcome people who join Telegram?
Type `y` (recommended).

### Question 5 — greet people who join your groups?
Type `n`, unless you run a group and want that.

### Question 6 — old chats
Type `1` = only **new** messages from now on (recommended — your old chats won't
suddenly get replies). Type `2` if you want everyone including old chats.

Then it checks everything and asks: **"Do you want to start the bot now?"** → type `y`.

---

## Step 4 — The login code (only once, ever)

> If the installer asked *"Do you want to start the bot now?"* and you typed `n`,
> do the login like this instead — it is easier to see what is happening:
>
> ```bash
> cd ~/projects/telegram-autoreply
> bash start.sh --foreground
> ```
> Answer the questions that appear, then press **Ctrl+C**, then `bash start.sh`
> to run it in the background.

The first start asks:

1. your phone number (if you skipped it earlier),
2. the **login code** that Telegram sends you **inside the Telegram app** (not SMS) —
   the same kind of code you see when logging into a new device,
3. your **two-step password**, only if you turned that on in Telegram.

Type them and press Enter. Telegram will also show a new "device" in Settings → Devices.
That's normal — it's this bot.

If you see the line **"Ready. Leave this window open"** — it's working! 🎉

To move it to the background so you can close Termux: press **Ctrl+C** once
(that stops it), then type `bash start.sh`. From then on the bot runs in the
background and survives closing Termux.

---

## Step 5 — Test it (30 seconds)

> **Who gets a reply, and who doesn't** (this confuses everyone at first):
> the bot replies to a person **only the first time they message you**, and it
> remembers forever. So for the test, ask a friend (or your second account) to
> send a **new** message *now*. Someone who messaged you before you installed
> this — or who was already replied to — will **not** get another reply.
> That's the design: nobody gets spammed.

1. In **another** window (or ask a friend), send yourself a message from a different
   account/browser — for example, message yourself using a second Telegram account.
2. In Termux run:

```bash
bash watch.sh
```

You should see a line like:
`FIRST MESSAGE from ... — replying`

To leave that screen **without** stopping the bot: press **Ctrl + B together,
let go, then press D**. (Pressing Ctrl+C would stop the bot!)

---

## Step 6 — Save it on your GitHub (one command)

Once the bot works, put a copy in your repository:

```bash
cd ~/projects/telegram-autoreply
bash PUSH-TO-GITHUB.sh
```

* It **checks first** that your private files (`.env`, the Telegram login session,
  history) are not included — if they are, it stops instead of uploading them.
* The first time, GitHub asks for a username and password:
  * username → `dekuc`
  * password → a **token**, not your normal password. The script prints exact
    steps to create one (`github.com/settings/tokens` → *Generate new token
    (classic)* → tick **repo** → copy the `ghp_...` code and paste it).
* Run it again any time to upload your latest version.

**Why this is handy:** your code is safe if the phone is lost, and you can edit
`templates.json` right in the GitHub website on your phone, then run `git pull`
in Termux to use the new text.

---

## Everyday use — only 4 commands

```bash
cd ~/projects/telegram-autoreply   # go into the folder (needed after opening Termux)
bash start.sh                      # start the bot (keeps working after you close Termux)
bash stop.sh                       # stop the bot
bash watch.sh                      # see what it is doing right now
bash status.sh                     # is it running? how many people got replies?
bash PUSH-TO-GITHUB.sh             # save your changes to your GitHub repo
git pull                           # download edits you made on the GitHub website
```

Tip: after `cd ~/projects`, you can just type `cd telegram-autoreply` next time —
Termux remembers where you are.

---

## Keep it working 24×7 on your phone

### Optional: come back automatically after a reboot

Termux can't start by itself — a small free app called **Termux:Boot** does it for you.

1. Install the **Termux:Boot** app from **F-Droid** (same place you got Termux).
2. Open Termux and paste these three lines:

```bash
mkdir -p ~/.termux/boot
cp ~/projects/telegram-autoreply/termux-boot-autoreply.sh ~/.termux/boot/
chmod +x ~/.termux/boot/termux-boot-autoreply.sh
```

3. Open the Termux:Boot app **once** (it needs one launch to register), then reboot
   your phone to test. After a restart, `bash status.sh` should say the bot is running.

> If you move the project somewhere else later, edit the `PROJECT=` line in
> `~/.termux/boot/termux-boot-autoreply.sh`.

* `bash start.sh` already holds a **wake-lock** so Android doesn't freeze it.
* You **can close Termux** after starting — it keeps running in the background.
* Turn off battery optimisation for Termux: Android **Settings → Apps → Termux →
  Battery → Unrestricted** (wording varies by phone). Also do the same for
  **Termux:Boot** if you installed it.
* Charge the phone / keep it plugged in — Android kills background apps on low battery.
* `bash status.sh` now also shows **how many copies are running: it must be 1**.
  If it ever shows 2, run `bash stop.sh` then `bash start.sh`.
* Your phone must have internet. If it's offline for a long time, some messages
  may be missed — a small cloud server (VPS) is the more reliable option later.
* Run it **only once**. Two copies at the same time will fight each other.

---

## Changing your auto-reply text later

Easiest way — just run the setup again:

```bash
cd ~/projects/telegram-autoreply && bash install-termux.sh
```

Answer `y` when it asks whether to change your settings.

Advanced (optional): the texts live in `templates.json` (or `templates.custom.json`
if you wrote your own). You can put **several** texts there and one is picked at
random each time, so your replies look natural.

---

## Something is broken?

The bot explains problems in plain English. Common ones:

| What you see | What to do |
|---|---|
| "The api_id / api_hash do not match" | Copy them again from my.telegram.org and run `bash install-termux.sh` |
| "The login code was wrong / expired" | Run `bash start.sh` again and type the fresh code quickly |
| "Your account has a two-step verification password" | Run `bash start.sh` and type that password when asked |
| "Telegram cancelled this login" | `rm -f data/autoreply.session` then `bash start.sh` |
| "No internet connection to Telegram" | Check your mobile data / Wi-Fi |
| "Telegram is asking you to wait N seconds" | That's Telegram's own speed limit — wait a few minutes |
| "THIS TELEGRAM ACCOUNT IS BLOCKED" | Telegram blocked the account. Only Telegram support can help. |
| Nothing happens at all | `bash install-termux.sh` again (it repairs), then `bash status.sh` |
| It stops when I close Termux | Start with `bash start.sh` (not `--foreground`) and set battery to Unrestricted |
| Command not found / it says "not finished yet" | You are in the wrong folder: `cd ~/projects/telegram-autoreply` first |
| `bash status.sh` shows 2 bot copies | Run `bash stop.sh`, then `bash start.sh` — only one copy may run |
| You want an old chat to get replies too | The bot replied-once-per-person and remembers. Find the person's id in `logs/autoreply.log`, then run `python bot.py --reset <id>` (or `python bot.py --reset-all` for everyone) |
| `PUSH-TO-GITHUB.sh` says "your repository already contains files" | A leftover upload (like a zip) is there. Type `y` to let it replace them with your project |
| `PUSH-TO-GITHUB.sh` says STOPPED | It found private files. Fix with `bash install-termux.sh`, then push again. If a session file ever did reach GitHub: Telegram → Settings → Devices → terminate that session, and change your password |
| `git push` asks for a password | Use a token, not your password — the script prints the steps |

Nothing else? Run this and send me the last lines:

```bash
cd ~/projects/telegram-autoreply && tail -30 logs/autoreply.log
```

---

## ⚠️ Three things to be careful about

1. **Pacing keeps you safe.** The bot waits 3–12 seconds before replying and never
   sends more than 60 messages per hour. Don't raise those numbers — sending to many
   strangers quickly is exactly what gets Telegram accounts blocked.
2. **`data/autoreply.session` is your login.** Anyone who copies that file can use
   your Telegram. Never share it, never upload it to GitHub. (The included
   `.gitignore` already blocks it.)
3. **This works on your own account**, which is why it can reply to everyone who
   messages you. Keep it polite and only reply to people who contact you first —
   that's normal usage, and that's what keeps the account safe.
