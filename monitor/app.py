from flask import Flask, render_template, redirect, url_for, jsonify, request, send_from_directory
import subprocess
import os
import shutil
import configparser
from utils.sysinfo import get_status_info
from pathlib import Path
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# paths
SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'launch_settings.conf'))
LMS_SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'lms_settings.conf'))
CAPTIVE_DIR = Path(os.path.abspath(os.path.join(BASE_DIR, '..', 'www', 'captive-portal')))
DEFAULT_CAPTIVE_DIR = Path(os.path.abspath(os.path.join(BASE_DIR, '..', 'www', 'default-captive-portal')))
PORT_FILE = os.path.join(BASE_DIR, "monitor_port.txt")

TRUE_SET = {"1", "true", "yes", "on"}
FALSE_SET = {"0", "false", "no", "off"}


def as_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in TRUE_SET:
        return True
    if s in FALSE_SET:
        return False
    return default


def _ensure_ini_sections(cfg: configparser.ConfigParser):
    if not cfg.has_section('SETTINGS'):
        cfg.add_section('SETTINGS')
    if not cfg.has_section('NETWORK'):
        cfg.add_section('NETWORK')


def _read_legacy_kv_file(path):
    if not os.path.isfile(path):
        return {}
    out = {}
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
    except Exception:
        pass
    return out


def load_launch_settings():
    cfg = configparser.ConfigParser()
    read_ok = False
    try:
        cfg.read(SETTINGS_PATH)
        read_ok = True
    except configparser.MissingSectionHeaderError:
        read_ok = False

    settings = {
        "USE_LOCAL": False,
        "FAST_LAUNCH": False,
        "STARTUP": False,
        "VERBOSE": False,
        "CAPTIVEPORTAL": False,
        "FTI": False,
        "SSID": "",
        "WAP_PASSPHRASE": ""
    }

    if read_ok and cfg.sections():
        _ensure_ini_sections(cfg)
        settings.update({
            "USE_LOCAL":     cfg.getboolean('SETTINGS', 'USE_LOCAL', fallback=settings["USE_LOCAL"]),
            "FAST_LAUNCH":   cfg.getboolean('SETTINGS', 'FAST_LAUNCH', fallback=settings["FAST_LAUNCH"]),
            "STARTUP":       cfg.getboolean('SETTINGS', 'STARTUP', fallback=settings["STARTUP"]),
            "VERBOSE":       cfg.getboolean('SETTINGS', 'VERBOSE', fallback=settings["VERBOSE"]),
            "CAPTIVEPORTAL": cfg.getboolean('SETTINGS', 'CAPTIVEPORTAL', fallback=settings["CAPTIVEPORTAL"]),
            "FTI":           cfg.getboolean('SETTINGS', 'FTI', fallback=settings["FTI"]),
            "SSID":          cfg.get('NETWORK', 'SSID', fallback=settings["SSID"]),
            "WAP_PASSPHRASE": cfg.get('NETWORK', 'WAP_PASSPHRASE', fallback=settings["WAP_PASSPHRASE"]),
        })
    else:
        # legacy flat file
        legacy = _read_legacy_kv_file(SETTINGS_PATH)
        settings.update({
            "USE_LOCAL":     as_bool(legacy.get("USE_LOCAL"), settings["USE_LOCAL"]),
            "FAST_LAUNCH":   as_bool(legacy.get("FAST_LAUNCH"), settings["FAST_LAUNCH"]),
            "STARTUP":       as_bool(legacy.get("STARTUP"), settings["STARTUP"]),
            "VERBOSE":       as_bool(legacy.get("VERBOSE"), settings["VERBOSE"]),
            "CAPTIVEPORTAL": as_bool(legacy.get("CAPTIVEPORTAL"), settings["CAPTIVEPORTAL"]),
            "FTI":           as_bool(legacy.get("FTI"), settings["FTI"]),
            "SSID":          legacy.get("SSID", settings["SSID"]),
            "WAP_PASSPHRASE": legacy.get("WAP_PASSPHRASE", settings["WAP_PASSPHRASE"]),
        })

    # normalize
    for k in ("USE_LOCAL", "FAST_LAUNCH", "STARTUP", "VERBOSE", "CAPTIVEPORTAL", "FTI"):
        settings[k] = as_bool(settings[k], False)

    return settings


def save_launch_settings(settings_dict):
    cfg = configparser.ConfigParser()
    if os.path.isfile(SETTINGS_PATH):
        try:
            cfg.read(SETTINGS_PATH)
        except configparser.MissingSectionHeaderError:
            cfg = configparser.ConfigParser()
    _ensure_ini_sections(cfg)

    for key in ['USE_LOCAL', 'FAST_LAUNCH', 'STARTUP', 'VERBOSE', 'CAPTIVEPORTAL', 'FTI']:
        cfg.set('SETTINGS', key, 'true' if as_bool(settings_dict.get(key)) else 'false')

    if 'SSID' in settings_dict:
        cfg.set('NETWORK', 'SSID', settings_dict.get('SSID', '') or '')
    if 'WAP_PASSPHRASE' in settings_dict:
        cfg.set('NETWORK', 'WAP_PASSPHRASE', settings_dict.get('WAP_PASSPHRASE', '') or '')

    with open(SETTINGS_PATH, 'w') as configfile:
        cfg.write(configfile)


def load_lms_settings():
    defaults = {"LMS_PORT": "8080", "LMS_DIR": "/var/www/lms"}
    if not os.path.isfile(LMS_SETTINGS_PATH):
        return defaults
    settings = {}
    with open(LMS_SETTINGS_PATH, "r", errors="ignore") as f:
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
        f.write(f"LMS_PORT={str(port).strip()}\n")
        f.write(f"LMS_DIR={str(directory).strip()}\n")


# ==========================
# Routes
# ==========================

@app.route("/")
def dashboard():
    try:
        status = get_status_info()
    except Exception as e:
        # fallback so the page still renders
        status = {
            "cpu_percent": 0,
            "cpu_color": "#777",
            "cpu_load": "0%",
            "ram_usage": "0%",
            "ram_percent": 0,
            "ram_color": "#777",
            "temp_c": "0°C",
            "temp_percent": 0,
            "temp_color": "#777",
            "apache_status": f"error: {e}",
            "logs": "[failed to read logs]",
        }

    settings = load_launch_settings()
    lms_settings = load_lms_settings()
    return render_template(
        "dashboard.html",
        status=status,
        **settings,
        **lms_settings
    )


@app.route("/status")
def status_api():
    info = get_status_info()
    settings = load_launch_settings()
    lms_settings = load_lms_settings()
    return jsonify({**info, **settings, **lms_settings})


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route("/control/<action>")
def control(action):
    # only try on Linux; otherwise just say "ok"
    if platform.system().lower() == "linux" and action in ["start", "stop", "restart"]:
        try:
            subprocess.run(["sudo", "systemctl", action, "apache2"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return redirect(url_for("dashboard"))
    else:
        # on Windows / other OS: just pretend success
        return jsonify({"status": f"control '{action}' not supported on this OS"}), 200


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
    lms_port = request.form.get("lms_port", "")
    lms_dir = request.form.get("lms_dir", "")
    save_lms_settings(lms_port, lms_dir)
    return redirect(url_for("dashboard"))


@app.route("/api/captive/list")
def captive_list():
    try:
        CAPTIVE_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted([p.name for p in CAPTIVE_DIR.iterdir()])
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/captive/preview")
def captive_preview():
    filename = request.args.get("file")
    if not filename:
        return jsonify({"error": "Missing filename"}), 400

    file_path = CAPTIVE_DIR / filename
    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404
    if file_path.is_dir():
        return jsonify({"error": "Path is a directory, cannot preview"}), 400

    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": f"Unable to preview this file: {e}"}), 500


@app.route("/api/captive/clear", methods=["POST"])
def captive_clear():
    try:
        CAPTIVE_DIR.mkdir(parents=True, exist_ok=True)
        for entry in CAPTIVE_DIR.iterdir():
            if entry.is_file():
                entry.unlink()
            else:
                # on Windows, skip directories to avoid Access Denied
                # if you want to fully clear: shutil.rmtree(entry, ignore_errors=True)
                pass
        return "Cleared"
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/captive/upload", methods=["POST"])
def captive_upload():
    if 'files' not in request.files:
        return jsonify({"error": "No files uploaded"}), 400
    try:
        CAPTIVE_DIR.mkdir(parents=True, exist_ok=True)
        for file in request.files.getlist("files"):
            file.save(str(CAPTIVE_DIR / file.filename))
        return "OK"
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/captive/restore", methods=["POST"])
def captive_restore():
    try:
        CAPTIVE_DIR.mkdir(parents=True, exist_ok=True)
        # clear files only
        for entry in CAPTIVE_DIR.iterdir():
            if entry.is_file():
                entry.unlink()
            else:
                # leave dirs
                pass

        # copy defaults (files)
        if DEFAULT_CAPTIVE_DIR.exists():
            for entry in DEFAULT_CAPTIVE_DIR.iterdir():
                target = CAPTIVE_DIR / entry.name
                if entry.is_file():
                    shutil.copy2(entry, target)
                # if you want to copy dirs too:
                # elif entry.is_dir():
                #     shutil.copytree(entry, target, dirs_exist_ok=True)

        return "Restored"
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/logs")
def tail_logs():
    candidates = [
        Path(os.path.dirname(os.path.abspath(__file__))) / "monitor.log",
        Path("/var/log/apache2/error.log"),
        Path("/var/log/apache2/access.log"),
    ]
    path = next((p for p in candidates if p.is_file()), None)
    if not path:
        return jsonify({"logs": "[no log file found]"}), 200

    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            read_back = min(size, 64 * 1024)
            f.seek(-read_back, os.SEEK_END)
            chunk = f.read().decode("utf-8", errors="replace")
        lines = chunk.splitlines()[-200:]
        return jsonify({"logs": "\n".join(lines)}), 200
    except Exception as e:
        return jsonify({"logs": f"[error reading logs: {e}]"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("MONITOR_PORT", "35373"))
    try:
        with open(PORT_FILE, "w") as f:
            f.write(str(port))
    except Exception:
        pass

    print(f"[Status] PiPress Monitor running on http://0.0.0.0:{port}")

    cert_path = os.path.join(BASE_DIR, "cert.pem")
    key_path = os.path.join(BASE_DIR, "key.pem")
    ssl_env = os.environ.get("MONITOR_SSL", "0").strip() == "1"
    ssl_context = (cert_path, key_path) if (
        ssl_env and os.path.exists(cert_path) and os.path.exists(key_path)
    ) else None

    app.run(host="0.0.0.0", port=port, ssl_context=ssl_context, threaded=True)
