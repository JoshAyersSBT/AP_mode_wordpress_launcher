import subprocess
import time
import os

SSID = "BetaBox1"
PASSWORD = "BetaBox1"
INTERFACE = "uap0"
WLAN = "wlan0"
STATIC_AP_IP = "192.168.50.1"
HOSTAPD_CONF = f"/etc/hostapd/hostapd.{INTERFACE}.conf"
DNSMASQ_CONF = "/etc/dnsmasq.conf"

# ANSI colors
RED = "\033[1;31m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[1;34m"
NC = "\033[0m"

def log_info(msg): print(f"{BLUE}[INFO]{NC} {msg}")
def log_success(msg): print(f"{GREEN}[SUCCESS]{NC} {msg}")
def log_warn(msg): print(f"{YELLOW}[WARN]{NC} {msg}")
def log_error(msg): print(f"{RED}[ERROR]{NC} {msg}")

def run(cmd, check=True, capture_output=False):
    log_info(cmd)
    if capture_output:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        return result.stdout.strip()
    else:
        subprocess.run(cmd, shell=True, check=check)

def reset_wlan_interfaces():
    log_info("Resetting wlan0 and cleaning up old AP interfaces...")

    run("systemctl stop hostapd", check=False)
    run("systemctl stop dnsmasq", check=False)
    run(f"iw dev {INTERFACE} del", check=False)

    run("modprobe -r brcmfmac", check=False)
    run("modprobe brcmfmac")

    run("rfkill unblock wifi")
    run("nmcli radio wifi on")
    run(f"nmcli dev set {WLAN} managed yes")
    run(f"ip link set {WLAN} down")
    run(f"ip addr flush dev {WLAN}")
    run(f"ip link set {WLAN} up")
    run("systemctl restart NetworkManager")

def is_connected():
    try:
        output = run("nmcli -t -f DEVICE,STATE dev", capture_output=True)
        for line in output.splitlines():
            if f"{WLAN}:connected" in line:
                return True
        return False
    except:
        return False

def attempt_reconnect():
    log_info("Scanning and reconnecting to known Wi-Fi networks...")
    run("nmcli radio wifi on")
    run("nmcli dev wifi rescan")
    time.sleep(3)
    known = run("nmcli connection show", capture_output=True)
    networks = [line.split()[0] for line in known.splitlines()[1:] if "wifi" in line]

    if not networks:
        log_error("No saved Wi-Fi networks found.")
        return False

    for net in networks:
        try:
            log_info(f"Trying to connect to: {net}")
            run(f"nmcli con up '{net}'")
            time.sleep(5)
            if is_connected():
                log_success(f"Connected to: {net}")
                return True
        except subprocess.CalledProcessError:
            continue

    log_error("Could not connect to any known network.")
    return False

def test_internet():
    log_info("Verifying internet connection...")
    try:
        run("ping -c 2 1.1.1.1", check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def create_ap_interface():
    log_info("Creating virtual AP interface...")
    run(f"iw dev {WLAN} interface add {INTERFACE} type __ap")
    run(f"ip addr add {STATIC_AP_IP}/24 dev {INTERFACE}")
    run(f"ip link set {INTERFACE} up")

def configure_hostapd():
    log_info("Generating hostapd config...")
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

def configure_dnsmasq():
    log_info("Writing dnsmasq config...")
    with open(DNSMASQ_CONF, "w") as f:
        f.write(f"""\
interface={INTERFACE}
bind-interfaces
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h
""")

def start_ap_services():
    log_info("Starting hostapd...")
    run(f"hostapd -B {HOSTAPD_CONF}")

    log_info("Waiting for uap0 to be ready before starting dnsmasq...")
    for _ in range(10):
        if os.system(f"ip link show {INTERFACE} > /dev/null 2>&1") == 0:
            break
        time.sleep(0.5)
    else:
        log_error("uap0 not found. Aborting DNS.")
        return

    log_info("Starting dnsmasq...")
    run("systemctl restart dnsmasq")

def main():
    if os.geteuid() != 0:
        log_error("Must be run as root.")
        return

    reset_wlan_interfaces()
    log_info("Waiting 5 seconds...")
    time.sleep(5)

    if not is_connected():
        if not attempt_reconnect():
            log_error("Could not connect to internet.")
            return

    if not test_internet():
        log_error("Internet unavailable. Aborting.")
        return

    log_success("Internet confirmed. Starting AP setup.")
    create_ap_interface()
    configure_hostapd()
    configure_dnsmasq()
    start_ap_services()
    log_success(f"AP '{SSID}' is up on {INTERFACE} ({STATIC_AP_IP})")

if __name__ == "__main__":
    main()
