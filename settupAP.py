import subprocess
import time
import os

SSID = "PiRepeater"
PASSWORD = "raspberry"
INTERFACE = "uap0"
STATIC_AP_IP = "192.168.50.1"
HOSTAPD_CONF = "/etc/hostapd/hostapd.conf"
DNSMASQ_CONF = "/etc/dnsmasq.conf"
HOSTAPD_DEFAULT = "/etc/default/hostapd"

def run(cmd, check=True, capture_output=False):
    print(f"🔧 {cmd}")
    if capture_output:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        return result.stdout.strip()
    else:
        subprocess.run(cmd, shell=True, check=check)
def reset_wlan0():
    print("🔄 Reinitializing wlan0...")
    run("rfkill unblock wifi")
    run("nmcli radio wifi on")
    run("nmcli dev set wlan0 managed yes")
    run("ip link set wlan0 up")

def is_connected():
    try:
        output = run("nmcli -t -f DEVICE,STATE dev", capture_output=True)
        for line in output.splitlines():
            if "wlan0:connected" in line:
                return True
        return False
    except:
        return False
def reset_wlan_interfaces():
    print("🧹 Resetting all Wi-Fi interfaces...")

    run("systemctl stop hostapd", check=False)
    run("systemctl stop dnsmasq", check=False)
    run("iw dev uap0 del", check=False)

    # Fully unload and reload the kernel driver
    run("modprobe -r brcmfmac", check=False)
    run("modprobe brcmfmac")

    run("rfkill unblock wifi")
    run("nmcli radio wifi on")
    run("nmcli dev set wlan0 managed yes")
    run("ip link set wlan0 down")
    run("ip addr flush dev wlan0")
    run("ip link set wlan0 up")
    run("systemctl restart NetworkManager")

    print("✅ wlan0 kernel reset complete.")


def attempt_reconnect():
    print("🔍 Scanning for saved networks...")
    run("nmcli radio wifi on")
    run("nmcli dev wifi rescan")
    time.sleep(3)
    known = run("nmcli connection show", capture_output=True)
    networks = [line.split()[0] for line in known.splitlines()[1:] if "wifi" in line]
    
    if not networks:
        print("❌ No saved Wi-Fi networks found.")
        return False

    print("📶 Attempting to connect to known networks...")
    for net in networks:
        try:
            run(f"nmcli con up '{net}'")
            time.sleep(5)
            if is_connected():
                print(f"✅ Connected to: {net}")
                return True
        except subprocess.CalledProcessError:
            continue

    print("❌ Could not connect to any saved network.")
    return False

def test_internet():
    print("🌍 Verifying internet connection...")
    try:
        run("ping -c 2 1.1.1.1", check=True)
        return True
    except subprocess.CalledProcessError:
        print("❌ No internet access.")
        return False

def configure_hostapd():
    with open(HOSTAPD_CONF, "w") as f:
        f.write(f"""
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
    run(f'sed -i "s|^#DAEMON_CONF=.*|DAEMON_CONF=\\"{HOSTAPD_CONF}\\"|" {HOSTAPD_DEFAULT}')
    run(f'sed -i "s|^DAEMON_CONF=.*|DAEMON_CONF=\\"{HOSTAPD_CONF}\\"|" {HOSTAPD_DEFAULT}')

def configure_dnsmasq():
    with open(DNSMASQ_CONF, "w") as f:
        f.write(f"""
interface={INTERFACE}
bind-interfaces
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h
""")

def create_ap_interface():
    print("🔁 Creating AP interface...")
    run(f"iw dev wlan0 interface add {INTERFACE} type __ap")
    run(f"ip addr add {STATIC_AP_IP}/24 dev {INTERFACE}")
    run(f"ip link set {INTERFACE} up")

def start_services():
    run("systemctl restart hostapd")
    run("systemctl restart dnsmasq")

def main():
    if os.geteuid() != 0:
        print("❌ Must be run as root.")
        return

    reset_wlan_interfaces()
    print("⏳ Waiting 5 seconds for interface to reinitialize...")
    time.sleep(5)

    if not is_connected():
        print("📡 Not connected to Wi-Fi. Attempting reconnection...")
        if not attempt_reconnect():
            print("❌ Aborting: No Wi-Fi.")
            return

    if not test_internet():
        print("❌ Aborting: No internet.")
        return

    print("✅ Internet confirmed. Proceeding with AP setup.")
    create_ap_interface()
    configure_hostapd()
    configure_dnsmasq()
    start_services()
    print(f"✅ Access Point '{SSID}' ready on {INTERFACE} ({STATIC_AP_IP})")

if __name__ == "__main__":
    main()
