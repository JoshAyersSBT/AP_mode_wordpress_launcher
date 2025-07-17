import subprocess
import os
import sys

DNSMASQ_CONF = "/etc/dnsmasq.uap0.conf"
SYSTEMD_UNIT = "/etc/systemd/system/dnsmasq@.service"

RED = '\033[1;31m'
GREEN = '\033[1;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[1;34m'
NC = '\033[0m'

def status(msg, level="INFO"):
    color = {
        "INFO": BLUE,
        "WARN": YELLOW,
        "ERROR": RED,
        "SUCCESS": GREEN
    }.get(level, NC)
    print(f"{color}[{level}] {msg}{NC}")

def run(cmd):
    status(f"Running: {cmd}", "INFO")
    subprocess.run(cmd, shell=True, check=True)

def write_dnsmasq_conf():
    status("Writing dedicated dnsmasq config for uap0...", "INFO")
    with open(DNSMASQ_CONF, "w") as f:
        f.write("""\
interface=uap0
bind-interfaces
domain-needed
bogus-priv
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h
""")
    status("dnsmasq config written.", "SUCCESS")

def write_systemd_unit():
    status("Writing systemd service unit for dnsmasq@.service...", "INFO")
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
    status("Systemd unit written.", "SUCCESS")

def reload_and_enable():
    status("Reloading systemd and enabling dnsmasq@uap0...", "INFO")
    run("systemctl daemon-reexec")
    run("systemctl daemon-reload")
    run("systemctl enable dnsmasq@uap0.service")
    status("dnsmasq@uap0.service enabled.", "SUCCESS")

def main():
    if os.geteuid() != 0:
        status("This script must be run as root.", "ERROR")
        sys.exit(1)

    write_dnsmasq_conf()
    write_systemd_unit()
    reload_and_enable()
    status("dnsmasq@uap0 systemd service is installed and enabled.", "SUCCESS")

if __name__ == "__main__":
    main()
