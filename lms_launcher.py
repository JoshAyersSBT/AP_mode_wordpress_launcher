#!/usr/bin/env python3
import subprocess
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import os
import sys

SERVICES = ["hostapd", "dnsmasq", "apache2"]
LMS_CMD = ["/usr/bin/sudo", "/AP_mode_wordpress_launcher/launch.sh"]

def is_service_active(service_name):
    try:
        result = subprocess.run(["systemctl", "is-active", "--quiet", service_name])
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] Failed to check service {service_name}: {e}")
        return False

def ensure_service_started(service_name):
    if not is_service_active(service_name):
        print(f"[BOOT] Starting {service_name}...")
        subprocess.run(["systemctl", "start", service_name])
    return is_service_active(service_name)

def create_ap_interface():
    setup_script = "/AP_mode_wordpress_launcher/setupAP.py"
    if not Path(setup_script).exists():
        print("[ERROR] setupAP.py not found.")
        return False

    print("[BOOT] Running setupAP.py to create uap0...")
    result = subprocess.run(["/usr/bin/python3", setup_script])
    return result.returncode == 0

def wait_for_interface(interface, timeout=10):
    print(f"[BOOT] Waiting for interface {interface} to appear...")
    for _ in range(timeout):
        if Path(f"/sys/class/net/{interface}").exists():
            print(f"[OK] Interface {interface} detected.")
            return True
        time.sleep(1)
    print(f"[ERROR] Interface {interface} did not appear.")
    return False

def setup_network_once():
    if not create_ap_interface() or not wait_for_interface("uap0"):
        print("❌ Failed to create uap0 interface.")
        return False
    return True

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
        self.log_box.insert("end", "Starting required services...
")
        self.log_box.configure(state="disabled")

        self.network_setup_done = False
        self.root.after(1000, self.check_loop)

    def append_log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        print(msg)

    def check_and_start_services(self):
        if not self.network_setup_done:
            self.append_log("[BOOT] Setting up AP interface...")
            if not setup_network_once():
                self.append_log("[ERROR] Network setup failed.")
                return False
            self.network_setup_done = True

        all_ok = True
        for svc in SERVICES:
            if not ensure_service_started(svc):
                self.append_log(f"[WARN] {svc} failed to start or isn't active.")
                all_ok = False
        return all_ok

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
            self.append_log(f"[ERROR] LMS failed (code {result.returncode}). Retrying in 5 seconds...")
            self.status_label.config(text="Retrying LMS...")
            self.root.after(5000, self.check_loop)

    def check_loop(self):
        if not self.check_and_start_services():
            self.root.after(3000, self.check_loop)
        else:
            self.try_start_lms()

def headless_fallback():
    print("[LMS Headless Launcher] Starting in non-GUI mode...")

    if not setup_network_once():
        return

    max_attempts = 10
    delay = 3

    for attempt in range(1, max_attempts + 1):
        all_started = True
        for svc in SERVICES:
            if not ensure_service_started(svc):
                print(f"[WARN] {svc} failed to start or isn't active.")
                all_started = False
        if all_started:
            print("[STATUS] All services are active. Launching LMS...")
            result = subprocess.run(LMS_CMD)
            if result.returncode == 0:
                print("[STATUS] LMS started successfully.")
                return
            else:
                print(f"[ERROR] LMS failed to start (exit code {result.returncode}). Retrying...")
        else:
            print(f"[WARN] Attempt {attempt}/{max_attempts} — Not all services ready.")
        time.sleep(delay)

    print("❌ LMS failed to start after multiple attempts.")

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
