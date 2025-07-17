import subprocess
import os
import sys

# Constants
SSID = "BetaBox1"
PASSWORD = "BetaBox1"
INTERFACE = "uap0"
HOSTAPD_CONF = f"/etc/hostapd/hostapd.{INTERFACE}.conf"
UNMANAGED_CONF = f"/etc/NetworkManager/conf.d/unmanaged-{INTERFACE}.conf"

# ANSI Colors
RED = '\033[1;31m'
GREEN = '\033[1;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[1;34m'
NC = '\033[0m'  # No Color

def status(msg, level="INFO"):
    color = {
        "INFO": BLUE,
        "WARN": YELLOW,
        "ERROR": RED,
        "SUCCESS": GREEN
    }.get(level, NC)
    print(f"{color}[{level}] {msg}{NC}")

def run(cmd, check=True):
    status(f"Running: {cmd}", "INFO")
    subprocess.run(cmd, shell=True, check=check)

def write_hostapd_conf():
    status(f"Writing hostapd config to {HOSTAPD_CONF}...", "INFO")
    if not 8 <= len(PASSWORD) <= 63:
        status("WPA password must be 8–63 characters.", "ERROR")
        sys.exit(1)

    with open(HOSTAPD_CONF, "w") as f:
        f.write(f"""\
interface={INTERFACE}
driver=nl80211
ssid={SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={PASSWORD}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
""")
    status("Hostapd config written successfully.", "SUCCESS")

def mark_interface_unmanaged():
    status(f"Marking {INTERFACE} as unmanaged by NetworkManager...", "INFO")
    with open(UNMANAGED_CONF, "w") as f:
        f.write(f"""\
[keyfile]
unmanaged-devices=interface-name:{INTERFACE}
""")
    run("systemctl restart NetworkManager")
    status(f"Interface {INTERFACE} marked as unmanaged.", "SUCCESS")

def disable_system_hostapd():
    status("Disabling conflicting hostapd services...", "INFO")
    run("systemctl stop hostapd@uap0.service", check=False)
    run("systemctl disable hostapd@uap0.service", check=False)
    run("systemctl stop hostapd.service", check=False)
    run("systemctl disable hostapd.service", check=False)
    run("systemctl mask hostapd.service", check=False)
    status("System-wide hostapd services disabled.", "SUCCESS")

def create_start_script():
    path = "/usr/local/bin/start_ap.sh"
    status(f"Creating AP startup script at {path}...", "INFO")
    with open(path, "w") as f:
        f.write(f"""#!/bin/bash
if ! ip link show {INTERFACE} &>/dev/null; then
    echo "[ERROR] {INTERFACE} does not exist. Create it with 'iw dev wlan0 interface add {INTERFACE} type __ap'"
    exit 1
fi

ip addr add 192.168.50.1/24 dev {INTERFACE}
ip link set {INTERFACE} up
hostapd -B {HOSTAPD_CONF}
systemctl restart dnsmasq
echo "[SUCCESS] AP '{SSID}' started on {INTERFACE}"
""")
    run(f"chmod +x {path}")
    status("Manual AP launcher created.", "SUCCESS")

def main():
    if os.geteuid() != 0:
        status("This script must be run as root.", "ERROR")
        sys.exit(1)

    write_hostapd_conf()
    mark_interface_unmanaged()
    disable_system_hostapd()
    create_start_script()
    status("Hostapd installation and configuration complete. Run 'sudo start_ap.sh' to start the AP.", "SUCCESS")

if __name__ == "__main__":
    main()
