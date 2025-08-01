from flask import Flask, render_template, redirect, url_for, jsonify, request, send_from_directory
import subprocess
import socket
import os
import shutil
import configparser
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
    config = configparser.ConfigParser()
    config.read(SETTINGS_PATH)

    if not config.has_section('SETTINGS'):
        config.add_section('SETTINGS')
    if not config.has_section('NETWORK'):
        config.add_section('NETWORK')

    return {
        "USE_LOCAL": config.getboolean('SETTINGS', 'USE_LOCAL', fallback=False),
        "FAST_LAUNCH": config.getboolean('SETTINGS', 'FAST_LAUNCH', fallback=False),
        "STARTUP": config.getboolean('SETTINGS', 'STARTUP', fallback=False),
        "VERBOSE": config.getboolean('SETTINGS', 'VERBOSE', fallback=False),
        "CAPTIVEPORTAL": config.getboolean('SETTINGS', 'CAPTIVEPORTAL', fallback=False),
        "FTI": config.getboolean('SETTINGS', 'FTI', fallback=False),
        "SSID": config.get('NETWORK', 'SSID', fallback=''),
        "WAP_PASSPHRASE": config.get('NETWORK', 'WAP_PASSPHRASE', fallback='')
    }

def save_launch_settings(settings_dict):
    config = configparser.ConfigParser()
    config.read(SETTINGS_PATH)

    if not config.has_section('SETTINGS'):
        config.add_section('SETTINGS')
    if not config.has_section('NETWORK'):
        config.add_section('NETWORK')

    for key in ['USE_LOCAL', 'FAST_LAUNCH', 'STARTUP', 'VERBOSE', 'CAPTIVEPORTAL', 'FTI']:
        config.set('SETTINGS', key, 'true' if settings_dict.get(key) else 'false')

    if 'SSID' in settings_dict:
        config.set('NETWORK', 'SSID', settings_dict.get('SSID', ''))
    if 'WAP_PASSPHRASE' in settings_dict:
        config.set('NETWORK', 'WAP_PASSPHRASE', settings_dict.get('WAP_PASSPHRASE', ''))

    with open(SETTINGS_PATH, 'w') as configfile:
        config.write(configfile)

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
        **settings,
        **lms_settings
    )

@app.route("/status")
def status():
    info = get_status_info()
    settings = load_launch_settings()
    lms_settings = load_lms_settings()
    return jsonify({**info, **settings, **lms_settings})

@app.route("/control/<action>")
def control(action):
    if action in ["start", "stop", "restart"]:
        subprocess.run(["sudo", "systemctl", action, "apache2"])
    return redirect(url_for("dashboard"))

@app.route("/update-settings", methods=["POST"])
def update_settings():
    form = request.form
    settings_dict = {
        "USE_LOCAL": 'use_local' in form,
        "FAST_LAUNCH": 'fast_launch' in form,
        "STARTUP": 'startup' in form,
        "VERBOSE": 'verbose' in form,
        "CAPTIVEPORTAL": 'captiveportal' in form,
        "FTI": 'fti' in form,
        "SSID": form.get('ssid', ''),
        "WAP_PASSPHRASE": form.get('wap_passphrase', '')
    }
    save_launch_settings(settings_dict)
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
        for f in os.listdir(CAPTIVE_DIR):
            os.remove(os.path.join(CAPTIVE_DIR, f))
        for f in os.listdir(DEFAULT_CAPTIVE_DIR):
            shutil.copy2(os.path.join(DEFAULT_CAPTIVE_DIR, f), os.path.join(CAPTIVE_DIR, f))
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
