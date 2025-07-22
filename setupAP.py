#!/usr/bin/env python3

import subprocess
import time
import os
import configparser
from status import log_info, log_success, log_warn, log_error

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "..", "launch_settings.conf")

# Default values
SSID = "BetaBox1"
PASSWORD = "BetaBox1"

# ---------------- CONFIG LOADER ----------------
def load_config():
    global SSID, PASSWORD
    if not os.path.exists(CONFIG_PATH):
        print(f"\033[1;33m[WARN]\033[0m Config not found at {CONFIG_PATH}, using defaults.")
        return

    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)

    if "NETWORK" in config:
        SSID = config["NETWORK"].get("SSID", SSID)
        PASSWORD = config["NETWORK"].get("WAP_PASSPHRASE", PASSWORD)
    else:
        print(f"\033[1;33m[WARN]\033[0m NETWORK section missing in config. Using defaults.")

# ---------------- EXISTING CONSTANTS ----------------
INTERFACE = "uap0"
WLAN = "wlan0"
STATIC_AP_IP = "192.168.50.1"
HOSTAPD_CONF = f"/etc/hostapd/hostapd.{INTERFACE}.conf"
DNSMASQ_CONF = "/etc/dnsmasq.conf"

# Shell runner
def run(cmd, check=True, capture_output=False):
    log_info(cmd)
    if capture_output:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        return result.stdout.strip()
    else:
        subprocess.run(cmd, shell=True, check=check)

# Interface reset
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

# Connection checks
def is_connected():
    try:
        output = run("nmcli -t -f DEVICE,STATE dev", capture_output=True)
        return any(f"{WLAN}:connected" in line for line in output.splitlines())
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

# AP Setup
def create_ap_interface():
    log_info("Creating virtual AP interface...")

    # Clean up if it exists
    run(f"iw dev {INTERFACE} del", check=False)

    run(f"iw dev {WLAN} interface add {INTERFACE} type __ap")

    for _ in range(10):
        if os.path.exists(f"/sys/class/net/{INTERFACE}"):
            break
        time.sleep(0.5)
    else:
        log_error(f"{INTERFACE} failed to appear after creation.")
        return

    run(f"ip addr add {STATIC_AP_IP}/24 dev {INTERFACE}")
    run(f"ip link set {INTERFACE} up")
    log_success(f"{INTERFACE} created and brought u_


def configure_hostapd():
    log_info("Generating hostapd config...")
    clean_config = f"""interface={INTERFACE}
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
"""
    with open(HOSTAPD_CONF, "w", newline='\n') as f:
        f.write(clean_config)
    run(f"chmod 600 {HOSTAPD_CONF}")

'''def configure_dnsmasq():
    log_info("Writing dnsmasq config...")
    with open(DNSMASQ_CONF, "w") as f:
        f.write(f"""

# AP Mode DNSMasq Configuration
interface={INTERFACE}
bind-interfaces
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h

# Static hostnames for local domains
address=/learning.betabox/192.168.50.1
address=/monitor.betabox/192.168.50.1:
""")'''

def configure_dnsmasq():
    log_info("Writing dnsmasq config...")
    with open(DNSMASQ_CONF, "w") as f:
        f.write(f"""\

# AP Mode DNSMasq Configuration
interface={INTERFACE}
bind-interfaces
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h

# Hijack all DNS to local IP for captive portal
address=/#/192.168.50.1
""")
def ensure_lighttpd_installed():
    try:
        run("which lighttpd", capture_output=True)
    except subprocess.CalledProcessError:
        log_info("Installing lighttpd...")
        run("apt install -y lighttpd")


def configure_lighttpd_redirect():
    log_info("Configuring lighttpd to redirect to https://learning.betabox...")

    os.makedirs("/AP_mode_wordpress_launcher/www/captive-portal/", exist_ok=True)  # Ensure directory exists
    # Create redirect HTML page
    html = """\
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="refresh" content="0; url=https://learning.betabox" />
  </head>
  <body>
    Redirecting to <a href="https://learning.betabox">learning.betabox</a>...
  </body>
</html>
"""
    with open("/var/www/html/index.html", "w") as f:
        f.write(html)

    # Create redirect rule file
    rules = """\
$HTTP["host"] =~ ".*" {
    url.redirect = (
        "^/generate_204$" => "https://learning.betabox",
        "^/success.html$" => "https://learning.betabox",
        "^/success.txt$" => "https://learning.betabox"
    )
}
"""
    redirect_conf = "/etc/lighttpd/conf-available/99-redirect-rules.conf"
    with open(redirect_conf, "w") as f:
        f.write(rules)

    # Enable module and restart
    run("lighty-enable-mod redirect", check=False)
    run(f"ln -sf {redirect_conf} /etc/lighttpd/conf-enabled/")
    run("systemctl restart lighttpd")


def update_etc_hosts():
    log_info("Adding local domains to /etc/hosts...")
    hosts_line = "192.168.50.1 learning.betabox monitor.betabox\n"
    with open("/etc/hosts", "a") as f:
        f.write(hosts_line)


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

# Main
def main():
    if os.geteuid() != 0:
        log_error("Must be run as root.")
        return

    load_config()
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
    update_etc_hosts()
    start_ap_services()
    #ensure_lighttpd_installed()
    #configure_lighttpd_redirect()
    log_success(f"AP '{SSID}' is up on {INTERFACE} ({STATIC_AP_IP})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"Unexpected crash: {e}")