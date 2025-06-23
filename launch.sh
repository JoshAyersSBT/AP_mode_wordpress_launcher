#!/bin/bash

# PiPress Launch Script with -local flag and improved package checks
# Sets up AP mode by default and optionally enables local network hosting

set -e

USE_LOCAL=false

if [[ "$1" == "-local" ]]; then
    USE_LOCAL=true
    echo "📡 Local network hosting enabled."
fi

DEPENDENCIES=(apache2 php libapache2-mod-php php-mysql mariadb-server hostapd dnsmasq iptables curl wget dnsutils net-tools python3 python3-flask python3-psutil)

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

echo "Checking and installing missing dependencies..."
for pkg in "${DEPENDENCIES[@]}"; do
    check_and_install "$pkg"
done
echo "All dependencies are installed."

if [ "$USE_LOCAL" = false ]; then
    echo "Stopping hostapd and dnsmasq..."
    sudo systemctl stop hostapd
    sudo systemctl stop dnsmasq

    echo "Enabling IP forwarding..."
    sudo sysctl -w net.ipv4.ip_forward=1
    sudo sed -i '/net.ipv4.ip_forward/s/^#//g' /etc/sysctl.conf

    echo "Configuring static IP for wlan0..."
    if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
        cat <<EOF | sudo tee -a /etc/dhcpcd.conf
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
    fi

    echo "Configuring dnsmasq..."
    sudo cp config/dnsmasq.conf /etc/dnsmasq.conf

    echo "Configuring hostapd..."
    sudo cp config/hostapd.conf /etc/hostapd/hostapd.conf
    sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

    echo "Starting AP services..."
    sudo systemctl start dnsmasq
    sudo systemctl unmask hostapd
    sudo systemctl enable hostapd
    sudo systemctl start hostapd
fi

# Get dynamic IP assigned to active interface
if [ "$USE_LOCAL" = true ]; then
    AP_IP=$(hostname -I | awk '{print $1}')
else
    AP_IP=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
fi

if [ -z "$AP_IP" ]; then
    echo "❌ Failed to detect IP address."
    exit 1
fi
echo "✅ Detected IP: $AP_IP"

# Configure iptables redirection if in AP-only mode
if [ "$USE_LOCAL" = false ]; then
    echo "Redirecting all HTTP traffic to WordPress server..."
    sudo iptables -t nat -F
    sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination $AP_IP:80
    sudo iptables -t nat -A POSTROUTING -j MASQUERADE
    sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"
fi

echo "Launching Apache and WordPress site..."
sudo systemctl enable apache2
sudo systemctl start apache2

echo "Launching monitoring Flask server..."
cd monitor
nohup python3 app.py > monitor.log 2>&1 &

echo "PiPress setup complete. Access the services using:"
echo "- WordPress: http://$AP_IP"
echo "- Monitor: http://$AP_IP:5000"
