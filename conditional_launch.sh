#!/bin/bash

CONF_FILE="/home/nas/AP_mode_wordpress_launcher/launch_settings.conf"
LAUNCH_SCRIPT="/home/nas/AP_mode_wordpress_launcher/launch.sh"

if [ -f "$CONF_FILE" ]; then
    STARTUP=$(grep -i '^STARTUP=' "$CONF_FILE" | cut -d '=' -f 2 | tr '[:upper:]' '[:lower:]')
    if [ "$STARTUP" = "true" ]; then
        echo "STARTUP=true. Launching..."
        sudo bash "$LAUNCH_SCRIPT"
    else
        echo "STARTUP=false. Skipping launch."
    fi
else
    echo "Config not found: $CONF_FILE"
fi
