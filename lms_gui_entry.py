#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

USER = "pi"  # Replace if needed
LMS_GUI_PATH = "/home/pi/AP_mode_wordpress_launcher/lms_launcher.py"
X_SESSION_DIR = "/tmp/.X11-unix"
XAUTH_PATH = f"/home/{USER}/.Xauthority"

def find_display():
    if not os.path.isdir(X_SESSION_DIR):
        return None
    for entry in os.listdir(X_SESSION_DIR):
        if entry.startswith("X"):
            return f":{entry[1:]}"
    return None

def main():
    display = find_display()
    if not display:
        print("[ERROR] No X display found.")
        return

    if not Path(XAUTH_PATH).exists():
        print("[ERROR] XAUTHORITY file not found.")
        return

    env = os.environ.copy()
    env["DISPLAY"] = display
    env["XAUTHORITY"] = XAUTH_PATH

    print(f"[INFO] Launching LMS GUI on DISPLAY={display} as root")
    subprocess.run(["/usr/bin/python3", LMS_GUI_PATH], env=env)

if __name__ == "__main__":
    main()
