import subprocess
import os

DNSMASQ_CONF = "/etc/dnsmasq.uap0.conf"
SYSTEMD_UNIT = "/etc/systemd/system/dnsmasq@.service"

def run(cmd):
    print(f"🔧 {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def write_dnsmasq_conf():
    print("🛠️ Writing dedicated dnsmasq config for uap0...")
    with open(DNSMASQ_CONF, "w") as f:
        f.write("""\
interface=uap0
bind-interfaces
domain-needed
bogus-priv
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h
""")

def write_systemd_unit():
    print("🛠️ Installing systemd service unit: dnsmasq@.service...")
    unit_content = """\
[Unit]
Description=Per-interface dnsmasq instance for %i
After=network.target
Wants=network.target
Requires=network-online.target
ConditionPathExists=/sys/class/net/%i

[Service]
ExecStart=/usr/sbin/dnsmasq --no-daemon --conf-file=/etc/dnsmasq.%i.conf
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""
    with open(SYSTEMD_UNIT, "w") as f:
        f.write(unit_content)

def reload_and_enable():
    print("🔁 Reloading systemd and enabling service...")
    run("systemctl daemon-reexec")
    run("systemctl daemon-reload")
    run("systemctl enable dnsmasq@uap0.service")

def main():
    if os.geteuid() != 0:
        print("❌ This script must be run as root.")
        exit(1)
    write_dnsmasq_conf()
    write_systemd_unit()
    reload_and_enable()
    print("✅ dnsmasq@uap0 systemd service is installed and enabled.")

if __name__ == "__main__":
    main()
