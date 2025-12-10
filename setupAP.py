#!/usr/bin/env python3

import subprocess
import time
import os
import configparser
import sys

from status import log_info, log_success, log_warn, log_error

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "launch_settings.conf")


# Default values
SSID = "BetaBox1"
PASSWORD = "BetaBox1"


# ---------------- Helpers & Config ----------------

def get_pi_serial() -> str:
    """Return the Pi's unique serial number, or '00000000' if unavailable."""
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("Serial"):
                    return line.strip().split(":")[1].strip()
    except Exception:
        pass
    return "00000000"


def load_config():
    global SSID, PASSWORD

    if not os.path.exists(CONFIG_PATH):
        print(f"\033[1;33m[WARN]\033[0m Config not found at {CONFIG_PATH}, using defaults.")
    else:
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)

        if "NETWORK" in config:
            # We still respect password from config, but SSID is now always derived from Pi serial.
            PASSWORD = config["NETWORK"].get("password", PASSWORD)

    # Derive SSID from Pi serial
    serial = get_pi_serial()
    suffix = serial[-4:]
    SSID = f"BetaBox-{suffix}"
    log_info(f"Using derived SSID: {SSID}")
    log_info(f"Using password: {PASSWORD}")


# ---------------- Network Helpers ----------------

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
    run("systemctl stop dnsmasq@uap0.service", check=False)
    run("systemctl stop lighttpd", check=False)
    run("systemctl stop apache2", check=False)

    # Remove uap0 if it exists
    run("ip link show uap0 && iw dev uap0 del || true", check=False)

    log_success("Cleaned up AP services.")


def is_connected():
    """
    Check if the device is currently connected to a Wi-Fi network via wlan0
    using nmcli.
    """
    try:
        # Check if there is any active connection on wlan0
        result = run(
            "nmcli -t -f DEVICE,STATE device | grep '^wlan0:connected'",
            capture_output=True,
        )
        return bool(result.strip())
    except subprocess.CalledProcessError:
        return False


def attempt_reconnect():
    """
    Try to reconnect wlan0 using the saved connection profiles with nmcli.
    """
    log_info("Attempting to reconnect to known Wi-Fi network on wlan0...")
    try:
        # List known connection profiles
        profiles = run("nmcli -t -f NAME connection show", capture_output=True).splitlines()
        for profile in profiles:
            profile = profile.strip()
            if not profile:
                continue

            log_info(f"Trying profile: {profile}")
            try:
                run(f"nmcli connection up id '{profile}'", check=True)
                log_success(f"Connected to: {profile}")
                return True
            except subprocess.CalledProcessError:
                continue

        log_error("Could not connect to any known network.")
        return False
    except subprocess.CalledProcessError:
        log_error("Failed to query connection profiles.")
        return False


def test_internet():
    log_info("Verifying internet connection...")
    try:
        run("ping -c 3 8.8.8.8", check=True)
        log_success("Internet connection verified.")
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------- AP Constants ----------------

INTERFACE = "uap0"
WLAN = "wlan0"
STATIC_AP_IP = "192.168.50.1"
HOSTAPD_CONF = f"/etc/hostapd/hostapd.{INTERFACE}.conf"
DNSMASQ_CONF = "/etc/dnsmasq.conf"


# ---------------- Shell runner ----------------

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
    run("systemctl stop dnsmasq@uap0.service", check=False)
    run("systemctl stop lighttpd", check=False)
    run("systemctl stop apache2", check=False)

    # Remove uap0 if it exists
    run("ip link show uap0 && iw dev uap0 del || true", check=False)

    log_success("Cleaned up AP services.")


def is_connected():
    """
    Check if the device is currently connected to a Wi-Fi network via wlan0
    using nmcli.
    """
    try:
        # Check if there is any active connection on wlan0
        result = run(
            "nmcli -t -f DEVICE,STATE device | grep '^wlan0:connected'",
            capture_output=True,
        )
        return bool(result.strip())
    except subprocess.CalledProcessError:
        return False


def attempt_reconnect():
    """
    Try to reconnect wlan0 using the saved connection profiles with nmcli.
    """
    log_info("Attempting to reconnect to known Wi-Fi network on wlan0...")
    try:
        # List known connection profiles
        profiles = run("nmcli -t -f NAME connection show", capture_output=True).splitlines()
        for profile in profiles:
            profile = profile.strip()
            if not profile:
                continue

            log_info(f"Trying profile: {profile}")
            try:
                run(f"nmcli connection up id '{profile}'", check=True)
                log_success(f"Connected to: {profile}")
                return True
            except subprocess.CalledProcessError:
                continue

        log_error("Could not connect to any known network.")
        return False
    except subprocess.CalledProcessError:
        log_error("Failed to query connection profiles.")
        return False


def test_internet():
    log_info("Verifying internet connection...")
    try:
        run("ping -c 3 8.8.8.8", check=True)
        log_success("Internet connection verified.")
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------- AP Config ----------------

def create_ap_interface():
    """
    Create a separate AP interface uap0 linked to wlan0, with a stable IP.
    """
    log_info("Creating uap0 interface...")
    run(f"iw dev {WLAN} interface add {INTERFACE} type __ap", check=False)

    log_info(f"Assigning static IP {STATIC_AP_IP}/24 to {INTERFACE}...")
    run(f"ip addr flush dev {INTERFACE}", check=False)
    run(f"ip addr add {STATIC_AP_IP}/24 dev {INTERFACE}", check=True)
    run(f"ip link set {INTERFACE} up", check=True)


def wait_for_interface(ifname, timeout=10):
    """
    Wait until the given interface exists and is up, or timeout.
    """
    log_info(f"Waiting for interface {ifname} to become available...")
    for _ in range(timeout * 2):
        try:
            result = run(f"ip link show {ifname}", capture_output=True)
            if "state UP" in result or "state UNKNOWN" in result:
                log_success(f"Interface {ifname} is up.")
                return True
        except subprocess.CalledProcessError:
            pass
        time.sleep(0.5)
    log_error(f"Timed out waiting for interface {ifname}.")
    return False


def configure_hostapd():
    """
    Write hostapd config for the AP interface.
    """
    log_info("Writing hostapd config...")
    config = f"""\
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
"""
    with open(HOSTAPD_CONF, "w", newline='\n') as f:
        f.write(config)
    run(f"chmod 600 {HOSTAPD_CONF}")


def configure_dnsmasq():
    log_info("Writing dnsmasq config...")
    with open(DNSMASQ_CONF, "w") as f:
        f.write(f"""\

# AP Mode DNSMasq Configuration
interface={INTERFACE}
bind-interfaces
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h

# Hijack all DNS to local IP for captive portal
address=/#/{STATIC_AP_IP}
""")
    log_success("dnsmasq.conf written.")


def install_dnsmasq_uap0_override():
    """
    Make sure dnsmasq runs with our config in AP mode without conflicting with
    any existing usage on other interfaces.
    """
    log_info("Installing dnsmasq@uap0 override (if using template service)...")
    override_dir = "/etc/systemd/system/dnsmasq@uap0.service.d"
    os.makedirs(override_dir, exist_ok=True)
    override_conf = os.path.join(override_dir, "override.conf")
    with open(override_conf, "w", newline="\n") as f:
        f.write(f"""\
[Service]
ExecStart=
ExecStart=/usr/sbin/dnsmasq -k --conf-file={DNSMASQ_CONF} --interface={INTERFACE}
""")
    run("systemctl daemon-reload", check=False)
    log_success("dnsmasq override installed.")


def update_etc_hosts():
    """
    Add entries for learning.betabox and monitor.betabox to /etc/hosts
    pointing to the AP IP.
    """
    log_info("Updating /etc/hosts for learning.betabox and monitor.betabox...")
    hosts_path = "/etc/hosts"
    lines = []
    if os.path.exists(hosts_path):
        with open(hosts_path, "r") as f:
            lines = f.readlines()

    # Remove old lines for these hostnames
    filtered = []
    for line in lines:
        if "learning.betabox" in line or "monitor.betabox" in line:
            continue
        filtered.append(line)

    # Append new entries
    filtered.append(f"{STATIC_AP_IP} learning.betabox\n")
    filtered.append(f"{STATIC_AP_IP} monitor.betabox\n")

    with open(hosts_path, "w") as f:
        f.writelines(filtered)

    log_success("Updated /etc/hosts.")


def configure_apache_for_wordpress():
    """
    Ensure Apache is serving /AP_mode_wordpress_launcher/www/captive-portal
    as the main site, with a name-based vhost for learning.betabox.
    """
    log_info("Configuring Apache for captive portal content...")

    site_conf = f"""\
        <VirtualHost *:80>
            ServerName learning.betabox
            # Catch *any* host and treat it as the captive portal
            ServerAlias learning.betabox
            ServerAlias *

            DocumentRoot /AP_mode_wordpress_launcher/www/captive-portal

            # Global rewrite rules for captive portal behavior
            RewriteEngine On
            # 1) Do NOT redirect if user is already on the portal host…
            RewriteCond %{HTTP_HOST} !^learning\.betabox$ [NC]
            # 2) …or if they’re targeting the monitor hostname…
            RewriteCond %{HTTP_HOST} !^monitor\.betabox$ [NC]
            # 3) …or if they’re using a raw IPv4 address (e.g. 192.168.50.1)
            RewriteCond %{HTTP_HOST} !^[0-9.]+$ [NC]
            # For anything else, force them into the captive portal.
            RewriteRule ^/(.*)$ http://learning.betabox/ [R=302,L]

            <Directory /AP_mode_wordpress_launcher/www/captive-portal>
                Options Indexes FollowSymLinks
                AllowOverride All
                Require all granted
                RewriteEngine On
            </Directory>

            ErrorLog /var/log/apache2/learning_error.log
            CustomLog /var/log/apache2/learning_access.log combined
        </VirtualHost>

            """

    apache_site_path = "/etc/apache2/sites-available/pipress.conf"
    os.makedirs("/AP_mode_wordpress_launcher/www/captive-portal/", exist_ok=True)

    with open(apache_site_path, "w", newline="\n") as f:
        f.write(site_conf)

    # Enable site and rewrite
    run("a2enmod rewrite", check=False)
    run("a2ensite pipress.conf", check=False)
    run("a2dissite 000-default.conf", check=False)
    # Restart Apache to pick up changes
    run("systemctl restart apache2", check=True)
    log_success("Apache virtual host configured for learning.betabox.")


def force_apache_global_defaults():
    """
    Ensure Apache’s global config is reasonable for our captive portal.
    """
    log_info("Ensuring Apache global config is set for captive portal usage...")

    apache_conf = "/etc/apache2/apache2.conf"
    if os.path.exists(apache_conf):
        with open(apache_conf, "r") as f:
            conf = f.read()
        # Minimal patching: ensure AllowOverride for our directory
        if "<Directory /AP_mode_wordpress_launcher/www/captive-portal>" not in conf:
            conf += """\

<Directory /AP_mode_wordpress_launcher/www/captive-portal>
    Options Indexes FollowSymLinks
    AllowOverride All
    Require all granted
</Directory>
"""
            with open(apache_conf, "w", newline="\n") as f:
                f.write(conf)
            log_success("Updated apache2.conf for captive portal directory.")
    else:
        log_warn("apache2.conf not found; skipping global defaults.")

    # Make sure the default site (if any) does not conflict
    default_site = "/etc/apache2/sites-available/000-default.conf"
    if os.path.exists(default_site):
        with open(default_site, "r") as f:
            contents = f.read()
        # If it's not empty, comment it out or minimal change
        if "<VirtualHost" in contents:
            new_contents = "# Disabled by AP setup\n" + "\n".join(
                "# " + line for line in contents.splitlines()
            ) + "\n"
            with open(default_site, "w", newline="\n") as f:
                f.write(new_contents)
            log_success("Disabled 000-default.conf to avoid vhost conflicts.")

    # Restart Apache to pick up changes
    run("systemctl restart apache2", check=False)


def ensure_lighttpd_installed():
    """
    Install lighttpd if not present. We will use it for captive portal redirects.
    """
    log_info("Checking for lighttpd...")
    try:
        run("lighttpd -v", check=True)
        log_success("lighttpd is already installed.")
    except subprocess.CalledProcessError:
        log_info("Installing lighttpd...")
        run("apt-get update", check=True)
        run("apt-get install -y lighttpd", check=True)
        log_success("lighttpd installed.")


def configure_lighttpd_redirect():
    """
    Configure lighttpd for a simple captive portal redirect, by hosting a tiny site
    that immediately redirects to https://learning.betabox.
    """
    log_info("Configuring lighttpd for captive portal redirects...")

    os.makedirs("/AP_mode_wordpress_launcher/www/captive-portal/", exist_ok=True)
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

    # Enable the config and ensure server root
    run("lighty-enable-mod redirect", check=False)
    run("lighty-enable-mod 99-redirect-rules", check=False)

    # Set document root
    lighttpd_conf = "/etc/lighttpd/lighttpd.conf"
    if os.path.exists(lighttpd_conf):
        with open(lighttpd_conf, "r") as f:
            content = f.read()
        if "server.document-root" not in content:
            content += '\nserver.document-root = "/AP_mode_wordpress_launcher/www/captive-portal"\n'
        else:
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("server.document-root"):
                    lines[i] = 'server.document-root = "/AP_mode_wordpress_launcher/www/captive-portal"'
            content = "\n".join(lines)
        with open(lighttpd_conf, "w") as f:
            f.write(content)

    # Restart lighttpd
    run("systemctl restart lighttpd", check=False)
    run("systemctl enable lighttpd", check=False)
    log_success("lighttpd configured for captive portal redirects.")


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

    # Try to stop any running instance first
    run(f"systemctl stop {dns_unit}", check=False)

    # Now try to start
    try:
        run(f"systemctl enable {dns_unit}", check=False)
        run(f"systemctl start {dns_unit}", check=True)
        log_success(f"{dns_unit} started successfully.")
        return True
    except subprocess.CalledProcessError as e:
        # We treat this as non-fatal, but we log warnings
        log_warn(f"Could not start {dns_unit}: {e}")
        log_warn(
            "Captive portal DNS/DHCP may not function, but the tool will stay up. "
            f"Users can still connect to http://{STATIC_AP_IP}/ directly."
        )
        return False


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
    install_dnsmasq_uap0_override()
    update_etc_hosts()

    configure_apache_for_wordpress()
    force_apache_global_defaults()
    dns_ok = start_ap_services()
    # ensure_lighttpd_installed()
    # configure_lighttpd_redirect()

    if not dns_ok:
        log_warn("AP is up but dnsmasq is not running. Captive portal DNS/DHCP may not function.")
        log_warn(f"Users can still access the tool directly at: http://{STATIC_AP_IP}/")

    log_success(f"AP '{SSID}' is up on {INTERFACE} ({STATIC_AP_IP})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"Unexpected crash: {e}")
