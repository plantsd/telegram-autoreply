#!/bin/bash
# macOS double-click launcher for the setup wizard.
cd "$(dirname "$0")" || exit 1
echo "=============================================================="
echo "   TELEGRAM AUTO-REPLY - SETUP (Mac)"
echo "=============================================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python is not installed on this Mac yet."
  echo "Open the App Store / python.org, install Python 3, then run this again."
  read -r -p "Press Enter to close..."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Installing helper programs, please wait 1-3 minutes..."
  python3 -m venv .venv || { echo "Could not create the setup folder."; read -r; exit 1; }
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt || { echo "Download failed - check the internet."; read -r; exit 1; }
  echo "Done installing."
  echo
fi

./.venv/bin/python setup_wizard.py
echo
echo "Next step: double-click  2-START-Mac.command"
read -r -p "Press Enter to close..."
