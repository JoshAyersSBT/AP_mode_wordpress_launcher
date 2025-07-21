import subprocess
import os
import sys
from status import log_info, log_success, log_warn, log_error  # Shared logging functions

# Constants
SSID = "BetaBox1"
PASSWORD = "BetaBox1"
INTERFACE = "uap0"
HOSTAPD_CONF = f"/etc/hostapd/hostapd.{INTERFACE}.conf"
UNMANAGED_CONF = f"/etc/NetworkManager/conf.d/unmanaged-{INTERFACE}.conf"

def run(cmd, check=True):
    log_info(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=check)

def write_hostapd_conf():
    log_info(f"Writing hostapd config to {HOSTAPD_CONF}...")

    if not 8 <= len(PASSWORD) <= 63:
        log_error("WPA password must be 8–63 characters.")
        sys.exit(1)

    os.makedirs(os.path.dirname(HOSTAPD_CONF), exist_ok=True)

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
    log_success("Hostapd config written successfully.")

def mark_interface_unmanaged():
    log_info(f"Marking {INTERFACE} as unmanaged by NetworkManager...")
    with open(UNMANAGED_CONF, "w") as f:
        f.write(f"""\
[keyfile]
unmanaged-devices=interface-name:{INTERFACE}
""")
    run("systemctl restart NetworkManager")
    log_success(f"Interface {INTERFACE} marked as unmanaged.")

def disable_system_hostapd():
    log_info("Disabling conflicting hostapd services...")
    run("systemctl stop hostapd@uap0.service", check=False)
    run("systemctl disable hostapd@uap0.service", check=False)
    run("systemctl stop hostapd.service", check=False)
    run("systemctl disable hostapd.service", check=False)
    run("systemctl mask hostapd.service", check=False)
    log_success("System-wide hostapd services disabled.")

def create_start_script():
    path = "/usr/local/bin/start_ap.sh"
    log_info(f"Creating AP startup script at {path}...")
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
    log_success("Manual AP launcher created.")

def main():
    if os.geteuid() != 0:
        log_error("This script must be run as root.")
        sys.exit(1)

    write_hostapd_conf()
    mark_interface_unmanaged()
    disable_system_hostapd()
    create_start_script()
    log_success("Hostapd installation and configuration complete. Run 'sudo start_ap.sh' to start the AP.")

if __name__ == "__main__":
    main()
