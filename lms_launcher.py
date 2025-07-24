#!/usr/bin/env python3
import subprocess
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path

SERVICES = ["hostapd", "dnsmasq", "apache2"]
LMS_CMD = ["/usr/bin/sudo", "/full/path/to/LMS"]  # Replace with actual path to LMS

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
        return subprocess.run(["systemctl", "is-active", "--quiet", name]).returncode == 0

    def all_services_ready(self):
        return all(self.check_service(svc) for svc in SERVICES)

    def try_start_lms(self):
        self.append_log("All services ready. Launching LMS...")
        self.status_label.config(text="Launching LMS...")

        result = subprocess.run(LMS_CMD)
        if result.returncode == 0:
            self.append_log("✅ LMS started successfully.")
            self.status_label.config(text="LMS is running.")
            self.progress.stop()
            self.root.after(3000, self.root.destroy)
        else:
            self.append_log("❌ LMS failed. Retrying in 5 seconds...")
            self.status_label.config(text="Retrying LMS...")
            self.root.after(5000, self.check_loop)

    def check_loop(self):
        if not self.all_services_ready():
            self.append_log("Waiting for services: " +
                            ", ".join(s for s in SERVICES if not self.check_service(s)))
            self.root.after(3000, self.check_loop)
        else:
            self.try_start_lms()

def main():
    if not (Path("/usr/bin/sudo").exists() and Path(LMS_CMD[-1]).exists()):
        print("Missing sudo or LMS binary.")
        return

    root = tk.Tk()
    app = LMSLauncherGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
