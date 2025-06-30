#!/bin/bash

# PiPress Launch Script (Absolute Webroot Enforced)
# Serves ./www/captive-portal directly using full Apache reconfiguration
# Supports: -local for LAN mode and -f / --fastLaunch to skip dependency checks

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

PROJECT_DIR="$(cd "$(dirname "$0")"; pwd)"
WEB_ROOT="$PROJECT_DIR/www/captive-portal"


if [ ! -d "$WEB_ROOT" ]; then
    echo " ERROR: Web root directory not found at: $WEB_ROOT"
    exit 1
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

if [ "$FAST_LAUNCH" = false ]; then
    echo "Checking and installing missing dependencies..."
    for pkg in "${DEPENDENCIES[@]}"; do
        check_and_install "$pkg"
    done
    echo "All dependencies are installed."
fi

if [ "$USE_LOCAL" = false ]; then
    echo "Stopping hostapd and dnsmasq..."
    sudo systemctl stop hostapd || true
    sudo systemctl stop dnsmasq || true

    echo "Status: Enabling IP forwarding..."
    sudo sysctl -w net.ipv4.ip_forward=1
    sudo sed -i '/net.ipv4.ip_forward/s/^#//g' /etc/sysctl.conf

    echo "Status: Configuring static IP for wlan0..."
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
    sudo systemctl unmask hostapd
    sudo systemctl enable hostapd
    sudo systemctl start hostapd
    sudo systemctl start dnsmasq
fi

# Get dynamic IP
if [ "$USE_LOCAL" = true ]; then
    AP_IP=$(hostname -I | awk '{print $1}')
else
    AP_IP=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
fi

if [ -z "$AP_IP" ]; then
    echo " Failed to detect IP address."
    exit 1
fi
echo " Detected IP: $AP_IP"

# Write full Apache config
echo " Overwriting Apache config to serve: $WEB_ROOT"
sudo tee /etc/apache2/sites-available/000-default.conf > /dev/null <<EOF
<VirtualHost *:80>
    ServerAdmin webmaster@localhost
    DocumentRoot $WEB_ROOT
    <Directory $WEB_ROOT>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    ErrorLog \${APACHE_LOG_DIR}/error.log
    CustomLog \${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
EOF

# Fix ownership and restart Apache
sudo chown -R www-data:www-data "$WEB_ROOT"
sudo chmod -R 755 "$WEB_ROOT"
sudo a2ensite 000-default.conf
sudo systemctl reload apache2
sudo systemctl restart apache2

# Configure iptables redirect (AP mode only)
if [ "$USE_LOCAL" = false ]; then
    echo "Redirecting all HTTP traffic to $AP_IP..."
    sudo iptables -t nat -F
    sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination $AP_IP:80
    sudo iptables -t nat -A POSTROUTING -j MASQUERADE
    sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"
fi

# Start monitor
echo "Launching Flask monitor..."
cd "$PROJECT_DIR/monitor"
nohup python3 app.py > monitor.log 2>&1 &

echo " PiPress setup complete."
echo "- Web Portal: http://$AP_IP"
echo "- Monitor:   http://$AP_IP:5000"
