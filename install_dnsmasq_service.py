import subprocess
import os
import sys
from utils.status import log_info, log_success, log_warn, log_error  # Shared status functions

DNSMASQ_CONF = "/etc/dnsmasq.uap0.conf"
SYSTEMD_UNIT = "/etc/systemd/system/dnsmasq@.service"

def run(cmd):
    log_info(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def write_dnsmasq_conf():
    log_info("Writing dedicated dnsmasq config for uap0...")
    with open(DNSMASQ_CONF, "w") as f:
        f.write("""\
interface=uap0
bind-interfaces
domain-needed
bogus-priv
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h
""")
    log_success("dnsmasq config written.")

def write_systemd_unit():
    log_info("Writing systemd service unit for dnsmasq@.service...")
    with open(SYSTEMD_UNIT, "w") as f:
        f.write("""\
[Unit]
Description=Per-interface dnsmasq instance for %i
After=network.target
Wants=network.target
Requires=network-online.target
ConditionPathExists=/sys/class/net/%i

[Service]
ExecStart=/usr/sbin/dnsmasq --no-daemon --conf-file=/etc/dnsmasq.%i.conf
Restart=on-failure

[Install]
WantedBy=multi-user.target
""")
    log_success("Systemd unit written.")

def reload_and_enable():
    log_info("Reloading systemd and enabling dnsmasq@uap0...")
    run("systemctl daemon-reexec")
    run("systemctl daemon-reload")
    run("systemctl enable dnsmasq@uap0.service")
    log_success("dnsmasq@uap0.service enabled.")

def main():
    if os.geteuid() != 0:
        log_error("This script must be run as root.")
        sys.exit(1)

    write_dnsmasq_conf()
    write_systemd_unit()
    reload_and_enable()
    log_success("dnsmasq@uap0 systemd service is installed and enabled.")

if __name__ == "__main__":
    main()
