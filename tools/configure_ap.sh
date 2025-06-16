#!/bin/bash

# configure_ap.sh
# Configures Raspberry Pi to act as a Wi-Fi access point using hostapd and dnsmasq

set -e

echo "Stopping existing hostapd and dnsmasq services..."
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# Enable IP forwarding
echo "Enabling IP forwarding..."
sudo sysctl -w net.ipv4.ip_forward=1
sudo sed -i '/net.ipv4.ip_forward/s/^#//g' /etc/sysctl.conf

# Set static IP for wlan0 if not already configured
echo "Configuring static IP for wlan0..."
if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
    cat <<EOF | sudo tee -a /etc/dhcpcd.conf
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
fi

# Copy configuration files
echo "Copying dnsmasq and hostapd config files..."
sudo cp config/dnsmasq.conf /etc/dnsmasq.conf
sudo cp config/hostapd.conf /etc/hostapd/hostapd.conf
sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

# Restart services
echo "Starting dnsmasq and hostapd..."
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl start hostapd
sudo systemctl restart dnsmasq

echo "Access point configured. SSID should now be discoverable."
