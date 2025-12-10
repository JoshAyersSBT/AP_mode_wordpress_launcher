#!/bin/bash

# install_dependencies.sh
# Installs all required packages for PiPress project, including Jupyter deps

set -euo pipefail

# Base dependencies for PiPress
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
    # --- Jupyter-related APT deps ---
    python3-pip
    python3-venv
    build-essential
    libatlas3-base
)

# Jupyter virtualenv location
JUPYTER_VENV="/opt/pipress/jupyter_venv"

# Python packages to install into the Jupyter venv
JUPYTER_PIP_PACKAGES=(
    notebook
    jupyterlab
    jupyter_server
    nbclassic
    ipykernel
)

echo "Updating APT package index..."
sudo apt-get update

echo "Checking and installing APT dependencies..."

for pkg in "${DEPENDENCIES[@]}"; do
    if ! dpkg -s "$pkg" &> /dev/null; then
        echo "Installing $pkg..."
        sudo apt-get install -y "$pkg"
    else
        echo "$pkg is already installed."
    fi
done

echo "Base dependencies are installed."

# --- Jupyter virtualenv setup ---
echo "Setting up Jupyter virtual environment..."

if [ -d "$JUPYTER_VENV" ]; then
    echo "Jupyter venv already exists at $JUPYTER_VENV"
else
    echo "Creating Jupyter venv at $JUPYTER_VENV..."
    sudo mkdir -p "$(dirname "$JUPYTER_VENV")"
    sudo python3 -m venv "$JUPYTER_VENV"
    sudo chown -R "$USER":"$USER" "$JUPYTER_VENV"
fi

JUPYTER_PIP="$JUPYTER_VENV/bin/pip"

if [ ! -x "$JUPYTER_PIP" ]; then
    echo "Error: pip not found in venv at $JUPYTER_PIP"
    exit 1
fi

echo "Upgrading pip in Jupyter venv..."
"$JUPYTER_PIP" install --upgrade pip

echo "Installing Jupyter Python packages into venv..."
"$JUPYTER_PIP" install "${JUPYTER_PIP_PACKAGES[@]}"

echo "All dependencies (including Jupyter stack) are installed."
echo "Jupyter venv: $JUPYTER_VENV"
echo "To use it, run: source \"$JUPYTER_VENV/bin/activate\""
