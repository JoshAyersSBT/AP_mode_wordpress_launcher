from flask import Flask, render_template, redirect, url_for, jsonify, request, send_from_directory
import subprocess
import socket
import os
import shutil
from utils.sysinfo import get_status_info

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Flask setup
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# Paths
SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'launch_settings.conf'))
LMS_SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'lms_settings.conf'))
CAPTIVE_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'www', 'captive-portal'))
DEFAULT_CAPTIVE_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'www', 'default-captive-portal'))

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

# -------------------- Main Routes --------------------

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

# -------------------- Captive Portal API --------------------

@app.route("/api/captive/list")
def captive_list():
    try:
        files = os.listdir(CAPTIVE_DIR)
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/captive/preview")
def captive_preview():
    filename = request.args.get("file")
    if not filename:
        return jsonify({"error": "Missing filename"}), 400
    file_path = os.path.join(CAPTIVE_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    try:
        with open(file_path, "r", errors="ignore") as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/captive/upload", methods=["POST"])
def captive_upload():
    if 'files' not in request.files:
        return jsonify({"error": "No files uploaded"}), 400
    try:
        for file in request.files.getlist("files"):
            file.save(os.path.join(CAPTIVE_DIR, file.filename))
        return "OK"
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/captive/restore", methods=["POST"])
def captive_restore():
    try:
        # Clear current files
        for f in os.listdir(CAPTIVE_DIR):
            os.remove(os.path.join(CAPTIVE_DIR, f))
        # Copy from default
        for f in os.listdir(DEFAULT_CAPTIVE_DIR):
            src = os.path.join(DEFAULT_CAPTIVE_DIR, f)
            dst = os.path.join(CAPTIVE_DIR, f)
            shutil.copy2(src, dst)
        return "Restored"
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------- Entry Point --------------------

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

if __name__ == "__main__":
    port = find_free_port()
    with open(os.path.join(BASE_DIR, "monitor_port.txt"), "w") as f:
        f.write(str(port))
    print(f"[Status] PiPress Monitor running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port)
