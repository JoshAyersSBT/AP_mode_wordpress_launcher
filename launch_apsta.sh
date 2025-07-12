#!/bin/bash

# PiPress Launch Script with AP-STA Mode Support
# Supports:
# - AP mode (default)
# - Local LAN hosting (-local)
# - Fast launch skipping dependency checks (-f or --fastLaunch)
# - AP-STA mode using uap0 virtual interface

set -e

USE_LOCAL=false
FAST_LAUNCH=false

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
    esac
done

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
        cat <<EOF | sudo tee -a /etc/dhcpcd.conf
interface uap0
    static ip_address=192.168.50.1/24
    nohook wpa_supplicant
EOF
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
sudo systemctl start apache2

echo "Launching monitoring Flask server..."
cd monitor
nohup python3 app.py > monitor.log 2>&1 &

echo "✅ PiPress AP-STA setup complete. Access the services using:"
echo "- WordPress: http://$AP_IP"
echo "- Monitor: http://$AP_IP:5000"
