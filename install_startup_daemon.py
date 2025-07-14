import os
import subprocess
from pathlib import Path
import getpass

# Get current user and correct home path
user = getpass.getuser()
home_dir = str(Path.home())
launcher_dir = os.path.join(home_dir, "AP_mode_wordpress_launcher")
launch_script = os.path.join(launcher_dir, "launch.sh")
config_file = os.path.join(launcher_dir, "launch_settings.conf")
check_script = os.path.join(launcher_dir, "conditional_launch.sh")
service_name = "apmode-launcher"
service_file = f"/etc/systemd/system/{service_name}.service"

def write_conditional_script():
    script = f"""#!/bin/bash

CONF_FILE="{config_file}"
LAUNCH_SCRIPT="{launch_script}"

if [ -f "$CONF_FILE" ]; then
    STARTUP=$(grep -i '^STARTUP=' "$CONF_FILE" | cut -d '=' -f 2 | tr '[:upper:]' '[:lower:]')
    if [ "$STARTUP" = "true" ]; then
        echo "STARTUP=true. Launching..."
        sudo bash "$LAUNCH_SCRIPT"
    else
        echo "STARTUP=false. Skipping launch."
    fi
else
    echo "Config not found: $CONF_FILE"
fi
"""
    print(f"📄 Writing conditional_launch.sh to {check_script}")
    with open("/tmp/conditional_launch.sh", "w") as f:
        f.write(script)
    subprocess.run(["sudo", "mv", "/tmp/conditional_launch.sh", check_script], check=True)
    subprocess.run(["sudo", "chmod", "+x", check_script], check=True)

def write_service_file():
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
    print(f"🧾 Writing service to {service_file}")
    with open("/tmp/apmode-launcher.service", "w") as f:
        f.write(service)
    subprocess.run(["sudo", "mv", "/tmp/apmode-launcher.service", service_file], check=True)
    subprocess.run(["sudo", "chmod", "644", service_file], check=True)

def enable_service():
    print("🔄 Reloading and enabling service...")
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
    subprocess.run(["sudo", "systemctl", "start", service_name], check=True)

def main():
    if not os.path.isfile(launch_script):
        print(f"❌ launch.sh not found at {launch_script}")
        return
    if not os.path.isfile(config_file):
        print(f"⚠️ launch_settings.conf not found at {config_file} (defaulting to STARTUP=false behavior)")
    
    write_conditional_script()
    write_service_file()
    enable_service()
    print("✅ Startup daemon installed successfully.")

if __name__ == "__main__":
    main()
