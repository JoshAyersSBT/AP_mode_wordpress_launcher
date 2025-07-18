import os
import subprocess
from pathlib import Path
import getpass

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

user = getpass.getuser()
home_dir = str(Path.home())
launcher_dir = os.path.join(home_dir, "AP_mode_wordpress_launcher")
launch_script = "/AP_mode_wordpress_launcher/launch.sh"
config_file = os.path.join(launcher_dir, "launch_settings.conf")
check_script = os.path.join(launcher_dir, "conditional_launch.sh")
service_name = "apmode-launcher"
service_file = f"/etc/systemd/system/{service_name}.service"

def write_conditional_script():
    status(f"Creating conditional launch script at {check_script}", "INFO")
    script = f"""#!/bin/bash

CONF_FILE="{config_file}"
LAUNCH_SCRIPT="{launch_script}"

if [ -f "$CONF_FILE" ]; then
    STARTUP=$(grep -i '^STARTUP=' "$CONF_FILE" | cut -d '=' -f 2 | tr '[:upper:]' '[:lower:]')
    if [ "$STARTUP" = "true" ]; then
        echo "[INFO] STARTUP=true. Launching..."
        sudo bash "$LAUNCH_SCRIPT"
    else
        echo "[INFO] STARTUP=false. Skipping launch."
    fi
else
    echo "[WARN] Config not found: $CONF_FILE"
fi
"""
    with open("/tmp/conditional_launch.sh", "w") as f:
        f.write(script)
    subprocess.run(["sudo", "mv", "/tmp/conditional_launch.sh", check_script], check=True)
    subprocess.run(["sudo", "chmod", "+x", check_script], check=True)
    status("Conditional launch script installed.", "SUCCESS")

def write_service_file():
    status(f"Creating systemd service file at {service_file}", "INFO")
    service = f"""[Unit]
Description=Launch AP Mode WordPress server if STARTUP flag is set
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={launcher_dir}
ExecStart={check_script}
Restart=always
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    with open("/tmp/apmode-launcher.service", "w") as f:
        f.write(service)
    subprocess.run(["sudo", "mv", "/tmp/apmode-launcher.service", service_file], check=True)
    subprocess.run(["sudo", "chmod", "644", service_file], check=True)
    status("Systemd service file created.", "SUCCESS")

def enable_service():
    status("Reloading systemd and enabling startup daemon...", "INFO")
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
    subprocess.run(["sudo", "systemctl", "start", service_name], check=True)
    status("Startup daemon enabled and started.", "SUCCESS")

def main():
    if not os.path.isfile(launch_script):
        status(f"launch.sh not found at {launch_script}", "ERROR")
        return
    if not os.path.isfile(config_file):
        status(f"launch_settings.conf not found at {config_file} (defaulting to STARTUP=false)", "WARN")

    write_conditional_script()
    write_service_file()
    enable_service()
    status("Startup daemon installed successfully.", "SUCCESS")

if __name__ == "__main__":
    main()
