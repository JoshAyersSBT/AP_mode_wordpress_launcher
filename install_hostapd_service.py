import subprocess
import os

SSID = "BetaBox1"
PASSWORD = "BetaBox1"
INTERFACE = "uap0"
HOSTAPD_CONF = f"/etc/hostapd/hostapd.{INTERFACE}.conf"
UNMANAGED_CONF = f"/etc/NetworkManager/conf.d/unmanaged-{INTERFACE}.conf"

def run(cmd, check=True):
    print(f"🔧 {cmd}")
    subprocess.run(cmd, shell=True, check=check)

def write_hostapd_conf():
    print(f"🛠️ Writing {HOSTAPD_CONF}...")
    if not 8 <= len(PASSWORD) <= 63:
        print("❌ WPA password must be 8–63 characters.")
        exit(1)

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

def mark_interface_unmanaged():
    print(f"📡 Marking {INTERFACE} as unmanaged by NetworkManager...")
    with open(UNMANAGED_CONF, "w") as f:
        f.write(f"""\
[keyfile]
unmanaged-devices=interface-name:{INTERFACE}
""")
    run("systemctl restart NetworkManager")

def disable_system_hostapd():
    print("🚫 Disabling hostapd services to prevent interference...")
    run("systemctl stop hostapd@uap0.service", check=False)
    run("systemctl disable hostapd@uap0.service", check=False)
    run("systemctl stop hostapd.service", check=False)
    run("systemctl disable hostapd.service", check=False)
    run("systemctl mask hostapd.service", check=False)

def create_start_script():
    path = "/usr/local/bin/start_ap.sh"
    print(f"📝 Creating manual AP launcher: {path}")
    with open(path, "w") as f:
        f.write(f"""#!/bin/bash
if ! ip link show {INTERFACE} &>/dev/null; then
    echo "❌ {INTERFACE} does not exist. Create it with 'iw dev wlan0 interface add {INTERFACE} type __ap'"
    exit 1
fi

ip addr add 192.168.50.1/24 dev {INTERFACE}
ip link set {INTERFACE} up
hostapd -B {HOSTAPD_CONF}
systemctl restart dnsmasq
echo "✅ AP '{SSID}' started on {INTERFACE}"
""")
    run(f"chmod +x {path}")

def main():
    if os.geteuid() != 0:
        print("❌ This script must be run as root.")
        exit(1)

    write_hostapd_conf()
    mark_interface_unmanaged()
    disable_system_hostapd()
    create_start_script()
    print("✅ Hostapd config complete. Run 'sudo start_ap.sh' after preparing uap0.")

if __name__ == "__main__":
    main()
