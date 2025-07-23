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

def check_flag():
    if not os.path.exists(CONFIG_PATH):
        status(f"Config file not found at {CONFIG_PATH}", "ERROR")
        return False
    with open(CONFIG_PATH, "r") as f:
        for line in f:
            if line.strip().startswith("STARTUP"):
                return line.strip().split("=")[1].lower() == "true"
    return False

def write_service():
    status("Writing systemd service file...")
    service_contents = f"""\
[Unit]
Description=Start LMS on boot if STARTUP=true
After=network.target

[Service]
Type=simple
ExecStart=/bin/bash -c '[[ "$(grep STARTUP {CONFIG_PATH} | cut -d "=" -f2)" == "true" ]] && sudo bash {LAUNCHER_PATH}'
WorkingDirectory={HOME}/AP_mode_wordpress_launcher
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
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
    if not os.geteuid() == 0:
        status("Please run this script as root (sudo).", "ERROR")
        return
    if not os.path.exists(LAUNCHER_PATH):
        status(f"Launch script not found at {LAUNCHER_PATH}", "ERROR")
        return
    write_service()
    enable_service()

if __name__ == "__main__":
    main()
