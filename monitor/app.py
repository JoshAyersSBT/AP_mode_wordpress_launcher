from flask import Flask, render_template, redirect, url_for, jsonify, request
import subprocess
import socket
import os
from utils.sysinfo import get_status_info

app = Flask(__name__)

# Config file paths
SETTINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'launch_settings.conf'))
LMS_SETTINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lms_settings.conf'))

# -------------------- Config Helpers --------------------

def load_launch_settings():
    defaults = {"USE_LOCAL": False, "FAST_LAUNCH": False}
    if not os.path.isfile(SETTINGS_PATH):
        return defaults

    settings = {}
    with open(SETTINGS_PATH, "r") as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split("=", 1)
                settings[key.strip()] = value.strip().lower() == "true"
    return {
        "USE_LOCAL": settings.get("USE_LOCAL", False),
        "FAST_LAUNCH": settings.get("FAST_LAUNCH", False)
    }

def save_launch_settings(use_local, fast_launch):
    with open(SETTINGS_PATH, "w") as f:
        f.write(f"USE_LOCAL={'true' if use_local else 'false'}\n")
        f.write(f"FAST_LAUNCH={'true' if fast_launch else 'false'}\n")

def load_lms_settings():
    defaults = {"LMS_PORT": "8080", "LMS_DIR": "/var/www/lms"}
    if not os.path.isfile(LMS_SETTINGS_PATH):
        return defaults

    settings = {}
    with open(LMS_SETTINGS_PATH, "r") as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split("=", 1)
                settings[key.strip()] = value.strip()
    return {
        "LMS_PORT": settings.get("LMS_PORT", defaults["LMS_PORT"]),
        "LMS_DIR": settings.get("LMS_DIR", defaults["LMS_DIR"])
    }

def save_lms_settings(port, directory):
    with open(LMS_SETTINGS_PATH, "w") as f:
        f.write(f"LMS_PORT={port.strip()}\n")
        f.write(f"LMS_DIR={directory.strip()}\n")

# -------------------- Routes --------------------

@app.route("/")
def dashboard():
    status = get_status_info()

    settings = load_launch_settings()
    lms_settings = load_lms_settings()

    return render_template(
        "dashboard.html",
        status=status,
        use_local=settings["USE_LOCAL"],
        fast_launch=settings["FAST_LAUNCH"],
        lms_port=lms_settings["LMS_PORT"],
        lms_dir=lms_settings["LMS_DIR"]
    )

@app.route("/status")
def status():
    return jsonify(get_status_info())

@app.route("/control/<action>")
def control(action):
    if action in ["start", "stop", "restart"]:
        subprocess.run(["sudo", "systemctl", action, "apache2"])
    return redirect(url_for("dashboard"))

@app.route("/update-settings", methods=["POST"])
def update_settings():
    use_local = 'use_local' in request.form
    fast_launch = 'fast_launch' in request.form
    save_launch_settings(use_local, fast_launch)
    return redirect(url_for("dashboard"))

@app.route("/update-lms", methods=["POST"])
def update_lms():
    lms_port = request.form.get("lms_port")
    lms_dir = request.form.get("lms_dir")
    save_lms_settings(lms_port, lms_dir)
    return redirect(url_for("dashboard"))

# -------------------- Utility --------------------

def find_free_port():
    """Find an available port by binding to port 0."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))  # Bind to any free port
        return s.getsockname()[1]

# -------------------- Entry Point --------------------

if __name__ == "__main__":
    port = find_free_port()
    with open("monitor_port.txt", "w") as f:
        f.write(str(port))
    print(f"🚀 PiPress Monitor running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port)
