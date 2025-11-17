#!/usr/bin/env python3

import subprocess
import time
import os
import configparser
from status import log_info, log_success, log_warn, log_error
import sys
from multiprocessing import Process

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "launch_settings.conf")

MONITOR_DIR = "/AP_mode_wordpress_launcher/monitor"
MONITOR_HOST = "0.0.0.0"
MONITOR_PORT = 35373  # keep what your UI expects (or whatever you write to monitor_port.txt)

# Default values
SSID = "BetaBox1"
PASSWORD = "BetaBox1"


# setupAP.py (add near the top with the other imports)
import sys
from multiprocessing import Process   # >>>
# >>>
MONITOR_DIR = "/AP_mode_wordpress_launcher/monitor"
MONITOR_HOST = "0.0.0.0"
MONITOR_PORT = 35373  # keep what your UI expects (or whatever you write to monitor_port.txt)


# ----- Monitor Helpers ------
def _run_monitor():  # >>>
    # Import and run the Flask app in this child process
    if MONITOR_DIR not in sys.path:
        sys.path.insert(0, MONITOR_DIR)
    # app.py must expose `app = Flask(__name__)`
    from app import app  # noqa: F401
    # Optional: write the port file if your UI reads it
    try:
        with open(os.path.join(MONITOR_DIR, "monitor_port.txt"), "w") as f:
            f.write(str(MONITOR_PORT))
    except Exception:
        pass
    try:
        # Prefer waitress if available; otherwise use Flask dev server
        try:
            from waitress import serve  # type: ignore
            print(f"[MONITOR] waitress on {MONITOR_HOST}:{MONITOR_PORT}", flush=True)
            serve(app, host=MONITOR_HOST, port=MONITOR_PORT)
        except Exception:
            print(f"[MONITOR] Flask dev server on {MONITOR_HOST}:{MONITOR_PORT}", flush=True)
            app.run(host=MONITOR_HOST, port=MONITOR_PORT, threaded=True)
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)

_monitor_proc: Process | None = None  # >>>

def start_monitor():  # >>>
    global _monitor_proc
    if _monitor_proc and _monitor_proc.is_alive():
        return
    _monitor_proc = Process(target=_run_monitor, name="MonitorProcess", daemon=True)
    _monitor_proc.start()
    # Optional: quick readiness wait
    import socket, time as _t
    for _ in range(40):  # ~4s
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", MONITOR_PORT)) == 0:
                print("[MONITOR] ready")
                return
        _t.sleep(0.1)
    print("[MONITOR] failed to bind (continuing)")  # don’t abort AP bring-up

def stop_monitor():  # >>>
    global _monitor_proc
    if _monitor_proc and _monitor_proc.is_alive():
        _monitor_proc.terminate()
        _monitor_proc.join(timeout=5)
    _monitor_proc = None


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

def reset_wlan_interfaces():
    log_info("Resetting AP-related services (non-destructive)...")

    # Only stop services related to AP — don’t touch wlan0
    run("systemctl stop hostapd", check=False)
    run("systemctl stop dnsmasq", check=False)
    run(f"iw dev {INTERFACE} del", check=False)

    log_success("Cleaned up AP services.")


# Connection checks
def is_connected():
    try:
        output = run("nmcli -t -f DEVICE,STATE dev", capture_output=True)
        return any(f"{WLAN}:connected" in line for line in output.splitlines())
    except:
        return False

def attempt_reconnect():
    import time
    import subprocess

    def is_eth_connected():
        result = subprocess.run(
            ["cat", "/sys/class/net/eth0/carrier"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0 and result.stdout.decode().strip() == "1"

    if is_eth_connected():
        log_info("Ethernet is connected. Skipping Wi-Fi reconnection.")
        return True

    if os.system("systemctl is-active --quiet NetworkManager") != 0:
        log_info("NetworkManager is not active. Skipping nmcli Wi-Fi reconnect.")
        return False

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

    run(f"iw dev {INTERFACE} del", check=False)
    run(f"iw dev {WLAN} interface add {INTERFACE} type __ap")

    # Bring interface up immediately after creation
    run(f"ip link set {INTERFACE} up")

    # Wait for system to recognize it
    for _ in range(10):
        if os.path.exists(f"/sys/class/net/{INTERFACE}"):
            break
        time.sleep(0.5)
    else:
        log_error(f"{INTERFACE} failed to appear after creation.")
        return

    run(f"ip addr add {STATIC_AP_IP}/24 dev {INTERFACE}")
    log_success(f"{INTERFACE} created and brought up.")



def wait_for_interface(interface: str, max_tries=10):
    import subprocess

    log_info(f"Waiting for interface {interface} to appear...")
    for i in range(max_tries):
        result = subprocess.run(
            ["ip", "link", "show", interface],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            log_success(f"Interface {interface} is present.")
            return True
        time.sleep(0.5)

    log_error(f"Interface {interface} did not appear after {max_tries} tries.")
    return False


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
    with open("/AP_mode_wordpress_launcher/www/captive-portal/index.html", "w") as f:
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

def force_apache_global_defaults():
    log_info("Enforcing Apache global default DocumentRoot and ServerName...")

    # Step 1: Set ServerName in apache2.conf
    apache_conf = "/etc/apache2/apache2.conf"
    with open(apache_conf, "r") as f:
        lines = f.readlines()
    if not any("ServerName" in line for line in lines):
        with open(apache_conf, "a") as f:
            f.write("\nServerName localhost\n")
        log_success("Added ServerName to apache2.conf")

    # Step 2: Update 000-default.conf DocumentRoot
    default_conf = "/etc/apache2/sites-available/000-default.conf"
    new_lines = []
    found = False
    with open(default_conf, "r") as f:
        for line in f:
            if "DocumentRoot" in line:
                new_lines.append("    DocumentRoot /AP_mode_wordpress_launcher/www/captive-portal\n")
                found = True
            else:
                new_lines.append(line)
    if found:
        with open(default_conf, "w") as f:
            f.writelines(new_lines)
        log_success("Updated DocumentRoot in 000-default.conf")
    else:
        log_warn("DocumentRoot line not found in 000-default.conf")

    # Step 3: Enable 000-default.conf
    run("sudo a2ensite 000-default.conf", check=False)

    # Step 4: Restart Apache
    run("systemctl restart apache2")
def configure_apache_for_wordpress():
    log_info("Configuring Apache virtual host for captive portal...")

    apache_conf_path = "/etc/apache2/sites-available/pipress.conf"
    apache_conf = """\
    <VirtualHost *:80>
        ServerName learning.betabox
        ServerAlias monitor.betabox

        DocumentRoot /AP_mode_wordpress_launcher/www/captive-portal

        <Directory /AP_mode_wordpress_launcher/www/captive-portal>
            Options FollowSymLinks
            AllowOverride All
            Require all granted
            DirectoryIndex index.html index.php
        </Directory>

        ErrorLog ${APACHE_LOG_DIR}/pipress_error.log
        CustomLog ${APACHE_LOG_DIR}/pipress_access.log combined
    </VirtualHost>
"""
    with open(apache_conf_path, "w") as f:
        f.write(apache_conf)

    # Ensure rewrite is active and default site is OFF
    run("a2enmod rewrite", check=False)
    run("a2dissite 000-default.conf", check=False)
    run("a2ensite pipress.conf", check=False)
    run("systemctl restart apache2", check=True)

    log_success("Apache now serves the captive portal at http://learning.betabox")



def update_etc_hosts():
    log_info("Adding local domains to /etc/hosts...")
    hosts_line = "192.168.50.1 learning.betabox monitor.betabox\n"
    with open("/etc/hosts", "a") as f:
        f.write(hosts_line)


def start_ap_services():
    """
    Bring up hostapd on the AP interface and attempt to start dnsmasq.

    dnsmasq is treated as OPTIONAL:
    - If it starts, great: captive DNS/DHCP works.
    - If it fails (port 53 in use, unknown interface, etc.), we log warnings
      but DO NOT raise, so the web tool remains reachable by IP.
    """
    log_info("Ensuring uap0 is available before launching services...")
    for _ in range(10):
        if os.system(f"ip link show {INTERFACE} > /dev/null 2>&1") == 0:
            break
        time.sleep(0.5)
    else:
        log_error("uap0 not found. Aborting hostapd and DNS startup.")
        # uap0 missing really is fatal: no AP at all.
        raise RuntimeError("uap0 interface missing")

    # Clean up any stray hostapd instance tied to uap0
    run("pkill -f 'hostapd.*uap0'", check=False)

    log_info("Starting hostapd...")
    # These are "best effort"; restart is the real gate.
    run("sudo systemctl unmask hostapd", check=False)
    run("sudo systemctl enable hostapd", check=False)
    # If hostapd fails to start, that's a hard failure.
    run("sudo systemctl restart hostapd", check=True)

    # ---------- dnsmasq: OPTIONAL ----------
    log_info("Starting dnsmasq (optional; will fail gracefully if it can’t start)...")
    dns_unit = "dnsmasq@uap0.service" if os.path.exists("/etc/systemd/system/dnsmasq@.service") else "dnsmasq"

    max_retries = 5
    dns_ok = False
    for attempt in range(1, max_retries + 1):
        # Do NOT let a non-zero exit abort the script
        run(f"systemctl restart {dns_unit}", check=False)

        # Check if it actually became active
        result = subprocess.run(["systemctl", "is-active", "--quiet", dns_unit])
        if result.returncode == 0:
            log_success(f"{dns_unit} is running (attempt {attempt}).")
            dns_ok = True
            break

        log_warn(f"{dns_unit} failed to start (attempt {attempt}/{max_retries}). Retrying...")
        time.sleep(1)

    if not dns_ok:
        log_warn(f"{dns_unit} failed to start after {max_retries} attempts.")
        log_warn("dnsmasq is OPTIONAL for this setup; captive DNS/DHCP may not work.")
        log_warn(f"Clients may need a manual IP or existing LAN DHCP,")
        log_warn(f"and can reach the portal directly via: http://{STATIC_AP_IP}/")

    # Caller can use this to decide how loudly to warn.
    return dns_ok

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


    if not test_internet():
        log_error("Internet unavailable. starting in AP mode without passthrough.")


    log_success("Internet confirmed. Starting AP setup.")
    create_ap_interface()
    wait_for_interface("uap0")
    configure_hostapd()
    configure_dnsmasq()
    update_etc_hosts()
    
    configure_apache_for_wordpress()
    force_apache_global_defaults()
    dns_ok = start_ap_services()
    #ensure_lighttpd_installed()
    #configure_lighttpd_redirect()
    start_monitor()

    if not dns_ok:
        log_warn("AP is up but dnsmasq is not running. Captive portal DNS/DHCP may not function.")
        log_warn(f"Users can still access the tool directly at: http://{STATIC_AP_IP}/")

    log_success(f"AP '{SSID}' is up on {INTERFACE} ({STATIC_AP_IP})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"Unexpected crash: {e}")
    finally:
        stop_monitor()  