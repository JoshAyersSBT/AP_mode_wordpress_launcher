#!/bin/bash

# install_dependencies.sh
# Installs all required packages for PiPress project

set -e

DEPENDENCIES=(
    apache2
    php
    libapache2-mod-php
    php-mysql
    mariadb-server
    hostapd
    dnsmasq
    iptables
    curl
    wget
    dnsutils
    net-tools
    python3
    python3-flask
    python3-psutil
)

echo "Checking and installing dependencies..."

for pkg in "${DEPENDENCIES[@]}"; do
    if ! dpkg -s "$pkg" &> /dev/null; then
        echo "Installing $pkg..."
        sudo apt-get install -y "$pkg"
    else
        echo "$pkg is already installed."
    fi
done

echo "All dependencies are installed."
