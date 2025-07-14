import os
import subprocess
from pathlib import Path
import pwd
import getpass

# Get the user running the script and their actual home directory
installing_user = getpass.getuser()
user_home = Path(pwd.getpwnam(installing_user).pw_dir)

SERVICE_NAME = "apmode-launcher"
SERVICE_FILE_PATH = f"/etc/systemd/system/{SERVICE_NAME}.service"
WORKING_DIR = str(user_home / "AP_mode_wordpress_launcher")
LAUNCH_CHECK_SCRIPT = os.path.join(WORKING_DIR, "conditional_launch.sh")
DESCRIPTION = "Startup daemon for AP-mode WordPress launcher with conditional STARTUP flag"

def create_conditional_script():
    script_content = f"""#!/bin/bash

CONF_FILE="{WORKING_DIR}/launch_settings.conf"
LAUNCH_SCRIPT="{WORKING_DIR}/launch.sh"

if [ -f "$CONF_FILE" ]; then
    STARTUP=$(grep -i '^STARTUP=' "$CONF_FILE" | cut -d '=' -f 2 | tr '[:upper:]' '[:lower:]')
    if [ "$STARTUP" = "true" ]; then
        echo "STARTUP flag is true. Launching with root privileges..."
        bash "$LAUNCH_SCRIPT"
    else
        echo "STARTUP flag is false. Skipping launch."
    fi
else
    echo "Config file not found: $CONF_FILE"
fi
"""
    print(f"Creating conditional launch script at {LAUNCH_CHECK_SCRIPT}")
    with open("/tmp/conditional_launch.sh", "w") as f:
        f.write(script_content)

    subprocess.run(["sudo", "mv", "/tmp/conditional_launch.sh", LAUNCH_CHECK_SCRIPT], check=True)
    subprocess.run(["sudo", "chmod", "+x", LAUNCH_CHECK_SCRIPT], check=True)

def create_service_file():
    service_content = f"""[Unit]
Description={DESCRIPTION}
After=network.target

[Service]
ExecStart={LAUNCH_CHECK_SCRIPT}
Restart=always
User=root
WorkingDirectory={WORKING_DIR}
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    print(f"Creating systemd service file at {SERVICE_FILE_PATH}")
    with open("/tmp/temp_service.service", "w") as f:
        f.write(service_content)

    subprocess.run(["sudo", "mv", "/tmp/temp_service.service", SERVICE_FILE_PATH], check=True)
    subprocess.run(["sudo", "chmod", "644", SERVICE_FILE_PATH], check=True)

def enable_service():
    print("Enabling service...")
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "enable", SERVICE_NAME], check=True)
    subprocess.run(["sudo", "systemctl", "start", SERVICE_NAME], check=True)
    print(f"✅ Service '{SERVICE_NAME}' installed and started.")

def main():
    launch_script_path = Path(WORKING_DIR) / "launch.sh"
    if not launch_script_path.exists():
        print(f"❌ Required launch script not found: {launch_script_path}")
        return

    create_conditional_script()
    create_service_file()
    enable_service()
    print("✅ Startup daemon installed successfully.")

if __name__ == "__main__":
    main()
