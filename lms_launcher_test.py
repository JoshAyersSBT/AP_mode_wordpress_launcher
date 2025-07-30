#!/usr/bin/env python3
import subprocess
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import os
import sys

SERVICES = ["hostapd", "dnsmasq", "apache2"]
LMS_CMD = ["/usr/bin/sudo", "/AP_mode_wordpress_launcher/launch.sh"]  # Replace with actual path to LMS


def is_service_active(service_name):
    try:
        result = subprocess.run(["systemctl", "is-active", "--quiet", service_name])
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] Service check for {service_name} failed: {e}")
        return False


class LMSLauncherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LMS Boot Launcher")
        self.root.geometry("400x200")
        self.root.resizable(False, False)

        self.status_label = ttk.Label(root, text="Initializing...", font=("Arial", 14))
        self.status_label.pack(pady=20)

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(pady=10, fill="x", padx=20)
        self.progress.start(10)

        self.log_box = tk.Text(root, height=6, width=50, font=("Courier", 10))
        self.log_box.pack(pady=5)
        self.log_box.insert("end", "Waiting for required services...\n")
        self.log_box.configure(state="disabled")

        self.root.after(1000, self.check_loop)

    def append_log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        print(msg)

    def check_service(self, name):
        return is_service_active(name)

    def all_services_ready(self):
        return all(self.check_service(svc) for svc in SERVICES)

    def try_start_lms(self):
        self.append_log("All services ready. Launching LMS...")
        self.status_label.config(text="Launching LMS...")

        result = subprocess.run(LMS_CMD)
        if result.returncode == 0:
            self.append_log("[STATUS] LMS started successfully.")
            self.status_label.config(text="LMS is running.")
            self.progress.stop()
            self.root.after(3000, self.root.destroy)
        else:
            self.append_log(f"[ERROR] LMS failed with code {result.returncode}. Retrying in 5 seconds...")
            self.status_label.config(text="Retrying LMS...")
            self.root.after(5000, self.check_loop)

    def check_loop(self):
        if not self.all_services_ready():
            self.append_log("Waiting for services: " +
                            ", ".join(s for s in SERVICES if not self.check_service(s)))
            self.root.after(3000, self.check_loop)
        else:
            self.try_start_lms()


def headless_fallback():
    print("[LMS Headless Launcher] Starting in non-GUI mode...")
    max_attempts = 10
    delay = 3

    for attempt in range(1, max_attempts + 1):
        missing = [svc for svc in SERVICES if not is_service_active(svc)]

        if not missing:
            print("[STATUS] All services are active. Launching LMS...")
            result = subprocess.run(LMS_CMD)
            if result.returncode == 0:
                print("[STATUS] LMS started successfully.")
                return
            else:
                print("[ERROR] LMS failed to start (exit code {}). Retrying...".format(result.returncode))
        else:
            print(f"[WARN] Attempt {attempt}/{max_attempts} — Waiting on: {', '.join(missing)}")

        time.sleep(delay)

    print("❌ LMS failed to start after multiple attempts.")
    return


def main():
    if not (Path("/usr/bin/sudo").exists() and Path(LMS_CMD[-1]).exists()):
        print("❌ Missing sudo or LMS binary.")
        return

    if os.environ.get("DISPLAY", "") == "":
        headless_fallback()
        return

    root = tk.Tk()
    app = LMSLauncherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
