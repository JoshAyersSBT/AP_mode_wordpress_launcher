#!/usr/bin/env python3
import subprocess
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import os
import sys
import dbus

SERVICES = ["hostapd", "dnsmasq", "apache2"]
LMS_CMD = ["/usr/bin/sudo", "/AP_mode_wordpress_launcher/launch.sh"]
SETUP_AP_SCRIPT = "/AP_mode_wordpress_launcher/setupAP.py"
INTERFACE = "uap0"

def is_service_active(service_name: str) -> bool:
    try:
        bus = dbus.SystemBus()
        systemd = bus.get_object("org.freedesktop.systemd1",
                                 "/org/freedesktop/systemd1")
        manager = dbus.Interface(systemd, "org.freedesktop.systemd1.Manager")

        unit_path = manager.GetUnit(service_name)
        unit = bus.get_object("org.freedesktop.systemd1", unit_path)
        props = dbus.Interface(unit, "org.freedesktop.DBus.Properties")

        active_state = props.Get("org.freedesktop.systemd1.Unit", "ActiveState")
        return active_state == "active"

    except dbus.DBusException:
        return False


def ensure_service_started(service_name: str) -> bool:
    if not is_service_active(service_name):
        print(f"[BOOT] Starting {service_name}...")
        try:
            bus = dbus.SystemBus()
            systemd = bus.get_object("org.freedesktop.systemd1",
                                     "/org/freedesktop/systemd1")
            manager = dbus.Interface(systemd, "org.freedesktop.systemd1.Manager")

            # StartUnit(mode="replace") mimics `systemctl restart`
            manager.StartUnit(service_name, "replace")
        except dbus.DBusException as e:
            print(f"[ERROR] Failed to start {service_name}: {e}")
            return False
    return is_service_active(service_name)

def create_ap_interface():
    if not Path(SETUP_AP_SCRIPT).exists():
        print("[ERROR] setupAP.py not found.")
        return False
    print("[BOOT] Running setupAP.py to create uap0...")
    result = subprocess.run(["/usr/bin/python3", SETUP_AP_SCRIPT])
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
        self.log_box.insert("end", "Starting required services...\n")
        self.log_box.configure(state="disabled")

        self.root.after(1000, self.boot_sequence)

    def append_log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        print(msg)

    def boot_sequence(self):
        self.append_log("[BOOT] Running setupAP.py...")
        if not create_ap_interface():
            self.append_log("[ERROR] Failed to execute setupAP.py.")
            self.status_label.config(text="Failed to setup AP.")
            return
        if not wait_for_interface(INTERFACE):
            self.append_log("[ERROR] uap0 not detected.")
            self.status_label.config(text="Missing interface.")
            return

        self.append_log("[OK] Interface ready. Starting services...")
        self.root.after(1000, self.check_and_start_services)

    def check_and_start_services(self):
        all_ok = True
        for svc in SERVICES:
            if not ensure_service_started(svc):
                self.append_log(f"[WARN] {svc} failed to start.")
                all_ok = False
        if all_ok:
            self.try_start_lms()
        else:
            self.status_label.config(text="Retrying service startup...")
            self.root.after(5000, self.check_and_start_services)

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
            self.append_log(f"[ERROR] LMS failed (code {result.returncode}). Retrying in 5s...")
            self.status_label.config(text="Retrying LMS...")
            self.root.after(5000, self.check_and_start_services)

def headless_fallback():
    print("[LMS Headless Launcher] Starting in non-GUI mode...")

    if not create_ap_interface():
        print("[ERROR] setupAP.py failed.")
        return
    if not wait_for_interface(INTERFACE):
        print("[ERROR] uap0 not detected.")
        return

    max_attempts = 10
    delay = 3
    for attempt in range(1, max_attempts + 1):
        all_started = all(ensure_service_started(svc) for svc in SERVICES)
        if all_started:
            print("[STATUS] All services active. Launching LMS...")
            result = subprocess.run(LMS_CMD)
            if result.returncode == 0:
                print("[STATUS] LMS started successfully.")
                return
            else:
                print(f"[ERROR] LMS failed (code {result.returncode}). Retrying...")
        else:
            print(f"[WARN] Attempt {attempt}/{max_attempts} — Services not ready.")
        time.sleep(delay)

    print("❌ LMS failed after multiple attempts.")

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
