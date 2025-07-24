#!/usr/bin/env python3
import os
from subprocess import run
from pathlib import Path

SERVICE_NAME = "lms.service"
SERVICE_PATH = f"/etc/systemd/system/{SERVICE_NAME}"
LMS_BINARY = "/AP_mode_wordpress_launcher/launch_wrapper.sh"

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
Description=Whatever this does
After=graphical.target network-online.target
Requires=graphical.target

[Service]
ExecStart=/bin/bash /home/pi/AP_mode_wordpress_launcher/launch.sh
User=root
Restart=on-failure
RestartSec=5

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

    if not os.path.isfile(LMS_BINARY):
        status(f"Could not find LMS binary at {LMS_BINARY}. Make sure it's installed.", "ERROR")
        return

    run(["chmod", "+x", LMS_BINARY])
    write_service()
    enable_service()
    status("Reminder: run `sudo visudo` and add:", "INFO")
    status(f"  pi ALL=(ALL) NOPASSWD: {LMS_BINARY}", "INFO")

if __name__ == "__main__":
    main()
