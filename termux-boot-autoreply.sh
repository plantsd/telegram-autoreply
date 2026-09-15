#!/data/data/com.termux/files/usr/bin/sh
# ---------------------------------------------------------------------------
#  AUTO-START THE BOT AFTER YOUR PHONE REBOOTS
#
#  Termux cannot start itself. A small separate app called "Termux:Boot"
#  (free, from F-Droid) runs everything in  ~/.termux/boot/  after a restart.
#
#  One-time setup:
#      pkg install -y termux-boot            # or install the Termux:Boot app
#      mkdir -p ~/.termux/boot
#      cp ~/projects/telegram-autoreply/termux-boot-autoreply.sh ~/.termux/boot/
#      chmod +x ~/.termux/boot/termux-boot-autoreply.sh
#
#  After that, every reboot brings the bot back by itself.
# ---------------------------------------------------------------------------
termux-wake-lock 2>/dev/null || true

# give Android a moment to get Wi-Fi / mobile data up
sleep 25

PROJECT="$HOME/projects/telegram-autoreply"
[ -d "$PROJECT" ] || exit 0

cd "$PROJECT" || exit 0
[ -f .env ] || exit 0

# start.sh already knows how to run in the background (tmux) and how to avoid
# starting a second copy
bash start.sh >/dev/null 2>&1
