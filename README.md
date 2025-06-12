# 🛰️ PiPress: WordPress AP Server for Raspberry Pi

**PiPress** is a self-contained tool designed to launch a fully functional WordPress server on a headless Raspberry Pi. It sets up the Pi as a wireless access point (AP mode) and hosts a LAN-based WordPress site that automatically redirects any connected client to the homepage.

---

## 🚀 Project Purpose

The goal of this project is to provide a plug-and-play Raspberry Pi WordPress server that:

- ✅ Works without a monitor (headless setup)
- ✅ Creates a local Wi-Fi hotspot using AP mode
- ✅ Hosts a WordPress site accessible by any connected client
- ✅ Automatically redirects connected clients to the WordPress homepage
- ✅ Checks for and installs required dependencies at launch

---

## 🎯 Project Goals

1. **Dependency Checker & Installer**
   - Verify presence of required packages (Apache, PHP, MariaDB, Hostapd, Dnsmasq, etc.)
   - Automatically install missing dependencies

2. **Wi-Fi Access Point Setup**
   - Configure Raspberry Pi to act as a standalone Wi-Fi access point (AP mode)
   - Serve static IP (e.g. `192.168.4.1`) to connected clients

3. **WordPress Hosting**
   - Automatically install and configure WordPress
   - Set up LAMP or Docker-based stack for easy deployment

4. **Client Redirection**
   - Automatically redirect any HTTP browser requests from connected clients to the WordPress site
   - Serve a captive portal or force redirect via DNS hijacking and iptables rules

5. **Headless Operation**
   - All operations are controlled via startup scripts
   - No need for external monitor, keyboard, or GUI

---

## 🛠️ Planned Features

- [ ] `launch.sh`: One-click setup and launch script
- [ ] Modular components: separate scripts for dependency check, AP config, WordPress install, redirect setup
- [ ] Captive portal with customizable landing page
- [ ] Support for both LAMP and Docker WordPress deployments
- [ ] Optional settings via config file

---

## 📦 Dependencies

- `apache2`, `php`, `php-mysql`, `mariadb-server`
- `hostapd`, `dnsmasq`, `iptables`
- `curl`, `wget`, `dnsutils`, `net-tools`

---

## 📁 Folder Structure (Planned)

```
PiPress/
├── README.md
├── launch.sh
├── tools/
│   ├── install_dependencies.sh
│   ├── configure_ap.sh
│   ├── setup_wordpress.sh
│   ├── redirect_clients.sh
│   └── utils.sh
├── config/
│   └── hostapd.conf
│   └── dnsmasq.conf
└── www/
    └── captive-portal/index.html
```

---

## 📋 License

MIT License — open to contributions and customization.
