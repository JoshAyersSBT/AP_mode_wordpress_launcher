#!/usr/bin/env python3
import os
import getpass
from pathlib import Path
from subprocess import run

SERVICE_NAME = "lms-launch.service"
USER = getpass.getuser()
HOME = str(Path.home())
LAUNCHER_PATH = f"/AP_mode_wordpress_launcher/launch.sh"
CONFIG_PATH = f"/AP_mode_wordpress_launcher/launch_settings.conf"
SERVICE_PATH = f"/etc/systemd/system/{SERVICE_NAME}"

def status(msg, level="INFO"):
    color = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARN": "\033[93m",
        "ERROR": "\033[91m"
    }.get(level, "\033[0m")
    print(f"{color}[{level}] {msg}\033[0m")

def write_service():
    status("Writing systemd service file...")
    service_contents = f"""\
[Unit]
Description=Start LMS launcher with retries after all services
After=multi-user.target network-online.target systemd-udevd.service hostapd.service dnsmasq.service
Requires=network-online.target
Wants=multi-user.target

[Service]
Type=simple
ExecStart=/bin/bash /AP_mode_wordpress_launcher/launch_wrapper.sh
RemainAfterExit=true
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target

"""
    with open(SERVICE_PATH, "w") as f:
        f.write(service_contents)
    status(f"Service written to {SERVICE_PATH}", "SUCCESS")

def enable_service():
    run(["systemctl", "daemon-reexec"])
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", SERVICE_NAME])
    status(f"Enabled {SERVICE_NAME} to run on startup.", "SUCCESS")

def main():
    if os.geteuid() != 0:
        status("Please run this script as root (sudo).", "ERROR")
        return
    if not os.path.exists(LAUNCHER_PATH):
        status(f"Launch script not found at {LAUNCHER_PATH}", "ERROR")
        return
    run(["chmod","+x","launch_wrapper.sh"])
    write_service()
    enable_service()

if __name__ == "__main__":
    main()
