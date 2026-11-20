#!/bin/bash
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.12 or later with Tk support from python.org, then try again."
  read -r -p "Press Enter to close. "
  exit 1
fi
python3 main.py --demo --demo-date 2030-01-07
status=$?
if [ "$status" -ne 0 ]; then
  echo "The app did not start. Check Python/Tk with: python3 -m tkinter"
  read -r -p "Press Enter to close. "
fi
exit "$status"
