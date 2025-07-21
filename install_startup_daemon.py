import os
import subprocess
from pathlib import Path
import getpass
from status import log_info, log_success, log_warn, log_error , status  # ← Use centralized status logging

user = getpass.getuser()
home_dir = str(Path.home())
launcher_dir = "/AP_mode_wordpress_launcher"
launch_script = "/AP_mode_wordpress_launcher/launch.sh"
config_file = "/AP_mode_wordpress_launcher/launch_settings.conf"
check_script = "/AP_mode_wordpress_launcher/conditional_launch.sh"
service_name = "apmode-launcher"
service_file = f"/etc/systemd/system/{service_name}.service"

def write_conditional_script():
    log_info(f"Creating conditional launch script at {check_script}")
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
    log_success("Conditional launch script installed.")

def write_service_file():
    log_info(f"Creating systemd service file at {service_file}")
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
    log_success("Systemd service file created.")

def enable_service():
    log_info("Reloading systemd and enabling startup daemon...")
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
    subprocess.run(["sudo", "systemctl", "start", service_name], check=True)
    log_success("Startup daemon enabled and started.")

def main():
    if not os.path.isfile(launch_script):
        log_error(f"launch.sh not found at {launch_script}")
        return
    if not os.path.isfile(config_file):
        log_warn(f"launch_settings.conf not found at {config_file} (defaulting to STARTUP=false)")

    write_conditional_script()
    write_service_file()
    enable_service()
    log_success("Startup daemon installed successfully.")

if __name__ == "__main__":
    main()
