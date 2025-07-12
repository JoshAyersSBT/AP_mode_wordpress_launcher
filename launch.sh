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
            echo "🔧 Opening configuration menu..."

            # Load current values or use default fallback
            CUR_USE_LOCAL=${USE_LOCAL:-false}
            CUR_FAST_LAUNCH=${FAST_LAUNCH:-false}

            NEW_USE_LOCAL=$(whiptail --title "PiPress Config" --yesno "Use local LAN hosting?\n\nNo = AP mode (default)" 12 60 3>&1 1>&2 2>&3 && echo "true" || echo "false")
            NEW_FAST_LAUNCH=$(whiptail --title "PiPress Config" --yesno "Enable fast launch?\n\nSkip dependency checks?" 12 60 3>&1 1>&2 2>&3 && echo "true" || echo "false")

            cat <<EOF > "$CONFIG_FILE"
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
    local pkg="\$1"
    PKG_STATUS=\$(dpkg-query -W -f='\${Status}' "\$pkg" 2>/dev/null || true)
    if [[ "\$PKG_STATUS" != *"install ok installed"* ]]; then
        echo "Installing \$pkg..."
        sudo apt-get install -y "\$pkg"
    else
        echo "\$pkg is already installed."
    fi
}

if [ "\$FAST_LAUNCH" = false ]; then
    echo "Checking and installing missing dependencies..."
    for pkg in "\${DEPENDENCIES[@]}"; do
        check_and_install "\$pkg"
    done
    echo "All dependencies are installed."
fi

if [ "\$USE_LOCAL" = false ]; then
    echo "Setting up AP-STA mode..."

    echo "Stopping hostapd and dnsmasq..."
    sudo systemctl stop hostapd || echo "hostapd was not running"
    sudo systemctl stop dnsmasq || echo "dnsmasq was not running"

    echo "Creating uap0 interface..."
    sudo iw dev wlan0 interface add uap0 type __ap || echo "uap0 already exists"

    echo "Bringing up uap0..."
    sudo ifconfig uap0 up

    echo "Configuring static IP for uap0..."
    if ! grep -q "interface uap0" /etc/dhcpcd.conf; then
        cat <<EOF2 | sudo tee -a /etc/dhcpcd.conf
interface uap0
    static ip_address=192.168.50.1/24
    nohook wpa_supplicant
EOF2
    fi

    echo "Enabling IP forwarding..."
    sudo sysctl -w net.ipv4.ip_forward=1
    sudo sed -i '/net.ipv4.ip_forward/s/^#//g' /etc/sysctl.conf

    echo "Configuring dnsmasq..."
    sudo cp config/dnsmasq.conf /etc/dnsmasq.conf

    echo "Configuring hostapd..."
    sudo cp config/hostapd.conf /etc/hostapd/hostapd.conf
    sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

    echo "Starting AP services..."
    sudo systemctl unmask hostapd
    sudo systemctl enable hostapd
    sudo systemctl start dnsmasq
    sudo systemctl start hostapd

    echo "Setting up iptables for NAT..."
    sudo iptables -t nat -F
    sudo iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE
    sudo iptables -A FORWARD -i wlan0 -o uap0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    sudo iptables -A FORWARD -i uap0 -o wlan0 -j ACCEPT
    sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"
fi

# Get active IP
if [ "\$USE_LOCAL" = true ]; then
    AP_IP=\$(hostname -I | awk '{print \$1}')
else
    AP_IP=\$(ip -4 addr show uap0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
fi

if [ -z "\$AP_IP" ]; then
    echo "❌ Failed to detect IP address."
    exit 1
fi
echo "✅ Detected IP: \$AP_IP"

echo "Launching Apache and WordPress site..."
sudo systemctl enable apache2
sudo systemctl restart apache2

echo "Launching monitoring Flask server..."
cd monitor
nohup python3 app.py > monitor.log 2>&1 &

echo "PiPress setup complete. Access the services using:"
echo "- Web Portal: http://\$AP_IP"
echo "- Monitor:   http://\$AP_IP:5000"
