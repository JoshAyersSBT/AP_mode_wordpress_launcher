import os
import subprocess
from pathlib import Path
import pwd
import getpass

# Get the installing user's name and home directory
installing_user = getpass.getuser()
home_dir = Path(pwd.getpwnam(installing_user).pw_dir).resolve()

SERVICE_NAME = "apmode-launcher"
SERVICE_FILE_PATH = f"/etc/systemd/system/{SERVICE_NAME}.service"
WORKING_DIR = str(home_dir / "AP_mode_wordpress_launcher")
LAUNCH_SCRIPT_PATH = os.path.join(WORKING_DIR, "launch.sh")
CONF_FILE_PATH = os.path.join(WORKING_DIR, "launch_settings.conf")
CHECK_SCRIPT_PATH = os.path.join(WORKING_DIR, "conditional_launch.sh")

def create_conditional_script():
    script = f"""#!/bin/bash

CONF_FILE="{CONF_FILE_PATH}"
LAUNCH_SCRIPT="{LAUNCH_SCRIPT_PATH}"

if [ -f "$CONF_FILE" ]; then
    STARTUP=$(grep -i '^STARTUP=' "$CONF_FILE" | cut -d '=' -f 2 | tr '[:upper:]' '[:lower:]')
    if [ "$STARTUP" = "true" ]; then
        echo "STARTUP flag is true. Running launch script with sudo..."
        sudo bash "$LAUNCH_SCRIPT"
    else
        echo "STARTUP flag is false. Skipping launch."
    fi
else
    echo "Configuration file not found: $CONF_FILE"
fi
"""
    print(f"✅ Writing conditional script to: {CHECK_SCRIPT_PATH}")
    with open("/tmp/conditional_launch.sh", "w") as f:
        f.write(script)
    subprocess.run(["sudo", "mv", "/tmp/conditional_launch.sh", CHECK_SCRIPT_PATH], check=True)
    subprocess.run(["sudo", "chmod", "+x", CHECK_SCRIPT_PATH], check=True)

def create_service_file():
    service = f"""[Unit]
Description=Start WordPress launcher on boot if STARTUP flag is true
After=network.target

[Service]
ExecStart={CHECK_SCRIPT_PATH}
User={installing_user}
WorkingDirectory={WORKING_DIR}
Restart=always
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    print(f"✅ Writing service file to: {SERVICE_FILE_PATH}")
    with open("/tmp/{SERVICE_NAME}.service", "w") as f:
        f.write(service)
    subprocess.run(["sudo", "mv", f"/tmp/{SERVICE_NAME}.service", SERVICE_FILE_PATH], check=True)
    subprocess.run(["sudo", "chmod", "644", SERVICE_FILE_PATH], check=True)

def enable_service():
    print("✅ Enabling systemd service...")
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "enable", SERVICE_NAME], check=True)
    subprocess.run(["sudo", "systemctl", "start", SERVICE_NAME], check=True)

def main():
    if not os.path.isfile(LAUNCH_SCRIPT_PATH):
        print(f"❌ ERROR: launch.sh not found at: {LAUNCH_SCRIPT_PATH}")
        return

    create_conditional_script()
    create_service_file()
    enable_service()
    print("✅ Startup daemon installed successfully.")

if __name__ == "__main__":
    main()
