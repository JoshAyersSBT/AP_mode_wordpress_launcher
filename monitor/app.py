from flask import Flask, render_template, redirect, url_for
import subprocess
from utils.sysinfo import get_status_info

app = Flask(__name__)

@app.route("/")
def dashboard():
    status = get_status_info()
    return render_template("dashboard.html", status=status)

@app.route("/control/<action>")
def control(action):
    if action in ["start", "stop", "restart"]:
        subprocess.run(["sudo", "systemctl", action, "apache2"])
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
