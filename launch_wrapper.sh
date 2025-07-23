#!/bin/bash

LOG_FILE="/tmp/lms_boot.log"
CONFIG_PATH="/AP_mode_wordpress_launcher/launch_settings.conf"
LAUNCHER="/AP_mode_wordpress_launcher/launch.sh"

echo "[BOOT] LMS service launching at $(date)" >> "$LOG_FILE"

# --- Wait for wlan0 to become available ---
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

# --- Wait for iw to become responsive ---
ATTEMPTS=0
while ! iw list >/dev/null 2>&1; do
  echo "[WAIT] Waiting for iw to respond (firmware load?)..." >> "$LOG_FILE"
  sleep 1
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ $ATTEMPTS -ge 15 ]; then
    echo "[FAIL] 'iw' never responded. WiFi driver may be missing." >> "$LOG_FILE"
    exit 1
  fi
done
echo "[OK] 'iw' is working." >> "$LOG_FILE"

# --- Launch LMS with retry loop ---
if [[ "$(grep STARTUP "$CONFIG_PATH" | cut -d "=" -f2)" == "true" ]]; then
  echo "[INFO] STARTUP=true. Beginning launch loop..." >> "$LOG_FILE"
  until bash "$LAUNCHER"; do
    echo "[RETRY] LMS launch failed. Retrying in 5 seconds..." >> "$LOG_FILE"
    sleep 5
  done
  echo "[SUCCESS] LMS successfully started at $(date)" >> "$LOG_FILE"
else
  echo "[SKIP] STARTUP flag is not set. Skipping LMS launch." >> "$LOG_FILE"
fi
