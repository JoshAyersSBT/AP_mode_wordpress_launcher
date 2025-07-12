#!/bin/bash

# PiPress Launch Script with AP-STA Mode Support + Configurable Settings

set -e

CONFIG_FILE="./launch_settings.conf"
USE_LOCAL=false
FAST_LAUNCH=false

# Load settings if config file exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Handle CLI arguments
for arg in "$@"; do
    case $arg in
        -l|--local)
            USE_LOCAL=true
            echo "📡 Local network hosting enabled."
            ;;
        -f|--fastLaunch)
            FAST_LAUNCH=true
            echo "⚡ Fast launch: skipping dependency checks."
            ;;
--config)
    while true; do
        OPTION=$(whiptail --title "PiPress Config Utility" --menu "Select an option:" 20 70 10 \
        "1" "Toggle USE_LOCAL (Currently: $USE_LOCAL)" \
        "2" "Toggle FAST_LAUNCH (Currently: $FAST_LAUNCH)" \
        "3" "Run install_hostapd_service.py" \
        "4" "Run install_dnsmasq_service.py" \
        "5" "Exit config utility" 3>&1 1>&2 2>&3)

        exitstatus=$?
        if [ $exitstatus -ne 0 ]; then
            echo "Exited config."
            exit 0
        fi

        case $OPTION in
            1)
                USE_LOCAL=$( [ "$USE_LOCAL" = true ] && echo false || echo true )
                ;;
            2)
                FAST_LAUNCH=$( [ "$FAST_LAUNCH" = true ] && echo false || echo true )
                ;;
            3)
                echo "⚙️ Running install_hostapd_service.py..."
                sudo python3 install_hostapd_service.py
                ;;
            4)
                echo "⚙️ Running install_dnsmasq_service.py..."
                sudo python3 install_dnsmasq_service.py
                ;;
            5)
                echo "Saving config and exiting..."
                break
                ;;
        esac
    done

    # Save config after exiting menu
    cat <<EOF > "$CONFIG_FILE"
USE_LOCAL=$USE_LOCAL
FAST_LAUNCH=$FAST_LAUNCH
EOF

    echo "✅ Settings saved."
    exit 0
    ;;

USE_LOCAL=$NEW_USE_LOCAL
FAST_LAUNCH=$NEW_FAST_LAUNCH
EOF

            echo "✅ Settings updated:"
            echo "- USE_LOCAL=$NEW_USE_LOCAL"
            echo "- FAST_LAUNCH=$NEW_FAST_LAUNCH"
            echo "Re-run the script to apply changes."
            exit 0
            ;;
    esac
done

# Save effective settings back to config file
cat <<EOF > "$CONFIG_FILE"
USE_LOCAL=$USE_LOCAL
FAST_LAUNCH=$FAST_LAUNCH
EOF

DEPENDENCIES=(apache2 php libapache2-mod-php php-mysql mariadb-server hostapd dnsmasq iptables iw curl wget dnsutils net-tools python3 python3-flask python3-psutil)

check_and_install() {
    local pkg="$1"
    PKG_STATUS=$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)
    if [[ "$PKG_STATUS" != *"install ok installed"* ]]; then
        echo "Installing $pkg..."
        sudo apt-get install -y "$pkg"
    else
        echo "$pkg is already installed."
    fi
}

if [ "$FAST_LAUNCH" = false ]; then
    echo "Checking and installing missing dependencies..."
    for pkg in "${DEPENDENCIES[@]}"; do
        check_and_install "$pkg"
    done
    echo "All dependencies are installed."
fi

if [ "$USE_LOCAL" = false ]; then
    echo "🚀 Running AP mode setup with settupAP.py..."

    if [ "$EUID" -ne 0 ]; then
        echo "❌ This script must be run as root for AP setup."
        exit 1
    fi

    # Try running inside virtual environment first
    if [ -d "./monitorEnviroment" ]; then
        echo "🧪 Trying monitorEnviroment..."
        source ./monitorEnviroment/bin/activate
        if python3 ./monitor/settupAP.py; then
            deactivate
        else
            echo "⚠️ Virtualenv execution failed, falling back to system Python..."
            deactivate
            sudo python3 ./monitor/settupAP.py
        fi
    else
        echo "⚠️ Virtual environment not found. Running with system Python..."
        sudo python3 ./monitor/settupAP.py
    fi
fi

# Get active IP
if [ "$USE_LOCAL" = true ]; then
    AP_IP=$(hostname -I | awk '{print $1}')
else
    AP_IP=$(ip -4 addr show uap0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
fi

if [ -z "$AP_IP" ]; then
    echo "❌ Failed to detect IP address."
    exit 1
fi
echo "✅ Detected IP: $AP_IP"

echo "Launching Apache and WordPress site..."
sudo systemctl enable apache2
sudo systemctl restart apache2

echo "Launching monitoring Flask server..."
cd monitor
nohup python3 app.py > monitor.log 2>&1 &

echo "PiPress setup complete. Access the services using:"
echo "- Web Portal: http://$AP_IP"
echo "- Monitor:   http://$AP_IP:5000"
