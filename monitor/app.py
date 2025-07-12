from flask import Flask, render_template, redirect, url_for, jsonify, request
import subprocess
from utils.sysinfo import get_status_info  # Ensure this works in your env

app = Flask(__name__)

@app.route("/")
def dashboard():
    status = get_status_info()

    # Placeholder settings; replace with actual config loader if needed
    use_local = True
    fast_launch = False
    lms_port = "8080"
    lms_dir = "/var/www/lms"

    return render_template(
        "dashboard.html",
        status=status,
        use_local=use_local,
        fast_launch=fast_launch,
        lms_port=lms_port,
        lms_dir=lms_dir
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

    # For now, just print; later store in config file
    print(f"Received launcher settings: USE_LOCAL={use_local}, FAST_LAUNCH={fast_launch}")
    return redirect(url_for("dashboard"))

@app.route("/update-lms", methods=["POST"])
def update_lms():
    lms_port = request.form.get("lms_port")
    lms_dir = request.form.get("lms_dir")

    # For now, just print; later store in config file
    print(f"Received LMS settings: LMS_PORT={lms_port}, LMS_DIR={lms_dir}")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
