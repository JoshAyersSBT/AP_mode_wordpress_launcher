#!/bin/bash
sleep 15  # Wait for system and interfaces to settle

CONFIG_PATH="/AP_mode_wordpress_launcher/launch_settings.conf"
LAUNCHER="/pi/AP_mode_wordpress_launcher/launch.sh"

echo "[BOOT] LMS service launching at $(date)" >> /tmp/lms_boot.log

if [[ "$(grep STARTUP "$CONFIG_PATH" | cut -d "=" -f2)" == "true" ]]; then
  until bash "$LAUNCHER"; do
    echo "[BOOT] Launch failed. Retrying..." >> /tmp/lms_boot.log
    sleep 5
  done
  echo "[BOOT] LMS started successfully." >> /tmp/lms_boot.log
else
  echo "[BOOT] LMS autostart disabled." >> /tmp/lms_boot.log
fi
