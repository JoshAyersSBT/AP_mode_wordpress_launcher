#!/bin/bash

# PiPress Launch Script
# Sets up AP mode and launches WordPress and monitoring server on a headless Raspberry Pi

set -e

DEPENDENCIES=(apache2 php libapache2-mod-php php-mysql mariadb-server hostapd dnsmasq iptables curl wget dnsutils net-tools python3 python3-flask python3-psutil)

echo "Checking and installing missing dependencies..."

for pkg in "${DEPENDENCIES[@]}"; do
    if ! dpkg -s "$pkg" &> /dev/null; then
        echo "Installing $pkg..."
        sudo apt-get install -y "$pkg"
    else
        echo "$pkg is already installed."
    fi
done

echo "All dependencies are installed."

# Disable services before configuring
echo "Stopping hostapd and dnsmasq..."
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# Enable IP forwarding
echo "Enabling IP forwarding..."
sudo sysctl -w net.ipv4.ip_forward=1
sudo sed -i '/net.ipv4.ip_forward/s/^#//g' /etc/sysctl.conf

# Set static IP for wlan0
echo "Configuring static IP for wlan0..."
if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
    cat <<EOF | sudo tee -a /etc/dhcpcd.conf
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
fi

# Configure dnsmasq
echo "Configuring dnsmasq..."
sudo cp config/dnsmasq.conf /etc/dnsmasq.conf

# Configure hostapd
echo "Configuring hostapd..."
sudo cp config/hostapd.conf /etc/hostapd/hostapd.conf
sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

# Start services
echo "Starting AP services..."
sudo systemctl start dnsmasq
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl start hostapd

# Set up iptables redirect for HTTP
echo "Redirecting all HTTP traffic to WordPress server..."
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination 192.168.4.1:80
sudo iptables -t nat -A POSTROUTING -j MASQUERADE
sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"

# Launch Apache
echo "Launching Apache and WordPress site..."
sudo systemctl enable apache2
sudo systemctl start apache2

# Launch monitoring server
echo "Launching monitoring Flask server..."
cd monitor
nohup python3 app.py > monitor.log 2>&1 &

echo "PiPress setup complete. Connect to 'MyPiHotspot' and access:"
echo "- WordPress: http://192.168.4.1"
echo "- Monitor: http://192.168.4.1:5000"
