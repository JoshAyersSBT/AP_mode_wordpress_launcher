#!/bin/bash

LOG_FILE="/tmp/lms_boot.log"
CONFIG_PATH="/AP_mode_wordpress_launcher/launch_settings.conf"
LAUNCHER="/AP_mode_wordpress_launcher/launch.sh"

echo "[BOOT] LMS service launching at $(date)" >> "$LOG_FILE"

# --- Final delay to ensure all daemons/interfaces settle ---
sleep 20
echo "[WAIT] Delayed launch for system readiness..." >> "$LOG_FILE"

# --- Wait for wlan0 interface to appear ---
MAX_WAIT=30
WAITED=0
while ! ip link show wlan0 >/dev/null 2>&1; do
  echo "[WAIT] Waiting for wlan0 to become available..." >> "$LOG_FILE"
  sleep 1
  WAITED=$((WAITED + 1))
  if [ $WAITED -ge $MAX_WAIT ]; then
    echo "[FAIL] wlan0 never appeared after $MAX_WAIT seconds." >> "$LOG_FILE"
    exit 1
  fi
done
echo "[OK] wlan0 is available after $WAITED seconds." >> "$LOG_FILE"

# --- Wait for iw to respond ---
ATTEMPTS=0
while ! iw list >/dev/null 2>&1; do
  echo "[WAIT] Waiting for iw to respond..." >> "$LOG_FILE"
  sleep 1
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ $ATTEMPTS -ge 15 ]; then
    echo "[FAIL] 'iw' not responding — possible driver issue." >> "$LOG_FILE"
    exit 1
  fi
done
echo "[OK] iw is responsive." >> "$LOG_FILE"

# --- Launch LMS ---
if [[ "$(grep STARTUP "$CONFIG_PATH" | cut -d "=" -f2)" == "true" ]]; then
  echo "[INFO] STARTUP=true. Beginning LMS launch loop..." >> "$LOG_FILE"
  until bash "$LAUNCHER"; do
    echo "[RETRY] LMS launch failed. Retrying in 5 seconds..." >> "$LOG_FILE"
    sleep 5
  done
  echo "[SUCCESS] LMS successfully started at $(date)" >> "$LOG_FILE"
else
  echo "[SKIP] STARTUP flag is not set. Skipping LMS launch." >> "$LOG_FILE"
  exit 0
fi

# --- Launch terminal to display LMS status ---
TERMINAL=$(command -v lxterminal || command -v x-terminal-emulator || command -v gnome-terminal)

if [ -n "$TERMINAL" ]; then
  echo "[INFO] Launching terminal with 'sudo LMS --status'" >> "$LOG_FILE"
  sudo -u pi DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority \
    $TERMINAL -e "bash -c 'sudo LMS --status; exec bash'" &
else
  echo "[WARN] No compatible terminal emulator found for LMS status." >> "$LOG_FILE"
fi
