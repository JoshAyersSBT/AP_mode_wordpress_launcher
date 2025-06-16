#!/bin/bash

# redirect_clients.sh
# Redirects all HTTP traffic to local WordPress server (192.168.4.1:80)

set -e

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Setting up iptables rules for HTTP redirection..."

# Clear existing NAT rules
sudo iptables -t nat -F

# Redirect incoming HTTP requests to WordPress server
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination 192.168.4.1:80
sudo iptables -t nat -A POSTROUTING -j MASQUERADE

# Save iptables rules
sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"

log "All HTTP traffic will now be redirected to http://192.168.4.1"
