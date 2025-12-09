#!/bin/bash

# PiPress Launch Script with AP-STA Mode Support + Configurable Settings

source "$(dirname "$0")/launch_Utilities.sh"
source "$(dirname "$0")/Full_Tool_Install_utilities.sh"

cd "/AP_mode_wordpress_launcher"
set -e

# --- Auto-bootstrap if outside /AP_mode_wordpress_launcher or missing files ---
EXPECTED_DIR="/AP_mode_wordpress_launcher"
NEEDED_FILES=("launch.sh" "setupAP.py" "launch_settings.conf")
REPO_URL="https://github.com/JoshAyersSBT/AP_mode_wordpress_launcher.git"

# Get actual location of this script
SCRIPT_DIR="$(cd "$(dirname "$(realpath "$0")")" && pwd)"

if [ "$SCRIPT_DIR" != "$EXPECTED_DIR" ]; then
    echo -e "\033[1;33m[WARN]\033[0m Running from unexpected directory: $SCRIPT_DIR"
    echo -e "\033[1;34m[INFO]\033[0m Bootstrapping project to $EXPECTED_DIR..."

    sudo rm -rf "$EXPECTED_DIR"
    git clone --depth=1 "$REPO_URL" "$EXPECTED_DIR"

    if [ $? -ne 0 ]; then
        echo -e "\033[1;31m[ERROR]\033[0m Failed to clone repository from GitHub."
        exit 1
    fi

    echo -e "\033[1;34m[INFO]\033[0m Launching from cloned directory..."
    exec sudo bash "$EXPECTED_DIR/launch.sh" --FTI
fi

# If in correct directory but files are missing, repair with --FTI
for file in "${NEEDED_FILES[@]}"; do
    if [ ! -f "$EXPECTED_DIR/$file" ]; then
        echo -e "\033[1;33m[WARN]\033[0m Missing required file: $file"
        echo -e "\033[1;34m[INFO]\033[0m Reinstalling using --FTI..."
        exec sudo bash "$EXPECTED_DIR/launch.sh" --FTI
    fi
done

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
MONITOR_DIR="$BASE_DIR/monitor"
CONFIG_FILE="$BASE_DIR/launch_settings.conf"
LOG_FILE="$MONITOR_DIR/monitor.log"
PORT_FILE="$MONITOR_DIR/monitor_port.txt"

USE_LOCAL=false
FAST_LAUNCH=false
VERBOSE=false

# ANSI Colors
RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'  # No Color

# Service retry settings
MAX_SERVICE_RETRIES=3
SERVICE_RETRY_DELAY=3

# Load settings if config file exists
current_section=""
while IFS='=' read -r key val; do
    key=$(echo "$key" | xargs)
    val=$(echo "$val" | xargs)
    if [[ "$key" == \[*\] ]]; then
        current_section="${key//[\[\]]/}"
        continue
    fi

    case "$current_section.$key" in
        SETTINGS.USE_LOCAL) USE_LOCAL="$val" ;;
        SETTINGS.FAST_LAUNCH) FAST_LAUNCH="$val" ;;
        SETTINGS.VERBOSE) VERBOSE="$val" ;;
        SETTINGS.CAPTIVEPORTAL) CAPTIVEPORTAL="$val" ;;
        NETWORK.SSID) SSID="$val" ;;
        NETWORK.WAP_PASSPHRASE) WAP_PASSPHRASE="$val" ;;
    esac
done < "$CONFIG_FILE"

TOTAL_STEPS=10
CURRENT_STEP=0

print_progress() {
    local message="$1"
    CURRENT_STEP=$((CURRENT_STEP + 1))
    local percent=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    if [ $percent -gt 100 ]; then
        percent=100
    fi
    local bar_len=$((percent / 10))
    local bar=$(printf '%0.s#' $(seq 1 $bar_len))
    local spaces=$(printf '%0.s-' $(seq 1 $((10 - bar_len))))
    tput civis
    printf "\r[%s%s] %3d%% - %s" "$bar" "$spaces" "$percent" "$message"
    sleep 0.5
}

# Run a command, optionally quiet, but DO NOT swallow failures here.
maybe_run() {
    if [ "$VERBOSE" = true ]; then
        "$@"
    else
        "$@" > /dev/null 2>&1
    fi
}

tput civis

show_status() {
    launch_pid=$(pgrep -f "bash .*launch.sh" | grep -v $$ || true)
    apache_status=$(systemctl is-active apache2 || echo "inactive")
    hostapd_status=$(systemctl is-active hostapd || echo "inactive")
    dnsmasq_status=$(systemctl is-active dnsmasq || echo "inactive")
    dnsmasq_uap0_status=$(systemctl is-active dnsmasq@uap0 || echo "inactive")

    monitor_pid=$(pgrep -f "python3.*app.py" || true)
    monitor_port=$(ss -tuln | grep ":5000 " || true)

    if [ -n "$monitor_pid" ]; then
        monitor_status="Running (PID: $monitor_pid)"
    else
        monitor_status="Not Running"
    fi

    if [ -n "$monitor_port" ]; then
        monitor_status+=" | Port 5000: Listening"
    else
        monitor_status+=" | Port 5000: Not Listening"
    fi

    STATUS_TEXT="Launch Script PID: ${launch_pid:-Not Running}\n"
    STATUS_TEXT+="Apache2: $apache_status\n"
    STATUS_TEXT+="hostapd: $hostapd_status\n"
    STATUS_TEXT+="dnsmasq (global): $dnsmasq_status\n"
    STATUS_TEXT+="dnsmasq@uap0: $dnsmasq_uap0_status\n"
    STATUS_TEXT+="System Monitor: $monitor_status\n"

    whiptail --title "PiPress Status Report" --msgbox "$STATUS_TEXT" 20 70
}

# Ensure a systemd service is active, with retries and error printing
ensure_service() {
    local svc="$1"
    local friendly="${2:-$svc}"
    local attempt rc

    for attempt in $(seq 1 "$MAX_SERVICE_RETRIES"); do
        print_progress "Starting $friendly (attempt $attempt/$MAX_SERVICE_RETRIES)"

        # Don't let set -e kill the script on restart failure
        set +e
        sudo systemctl restart "$svc"
        rc=$?
        set -e

        sleep "$SERVICE_RETRY_DELAY"

        if systemctl is-active --quiet "$svc"; then
            echo -e "\n${GREEN}[OK]${NC} $friendly is active."
            return 0
        else
            echo -e "\n${YELLOW}[WARN]${NC} $friendly failed to start (attempt $attempt)."
            echo -e "${YELLOW}[WARN]${NC} systemctl status for $svc:"
            # Always show status output, even in non-verbose mode
            sudo systemctl status "$svc" --no-pager | head -n 25 || true
        fi
    done

    echo -e "${RED}[ERROR]${NC} $friendly failed to start after $MAX_SERVICE_RETRIES attempts."
    return 1
}

# Start the Flask monitor with retries; print log errors if it fails
start_monitor_with_retries() {
    local attempt mpid waited
    MONITOR_PORT=""

    cd "$MONITOR_DIR"
    rm -f "$LOG_FILE" "$PORT_FILE"

    for attempt in $(seq 1 "$MAX_SERVICE_RETRIES"); do
        print_progress "Launching monitor server (attempt $attempt/$MAX_SERVICE_RETRIES)"

        set +e
        nohup python3 app.py >> "$LOG_FILE" 2>&1 &
        mpid=$!
        set -e

        waited=0
        MONITOR_PORT=""

        # Wait for monitor_port.txt to appear
        while [ $waited -lt 10 ]; do
            if [ -f "$PORT_FILE" ]; then
                MONITOR_PORT=$(cat "$PORT_FILE")
                break
            fi
            sleep 1
            waited=$((waited + 1))
        done

        if [ -n "$MONITOR_PORT" ]; then
            echo -e "\n${GREEN}[OK]${NC} Monitor running on port $MONITOR_PORT (PID $mpid)."
            return 0
        else
            echo -e "\n${YELLOW}[WARN]${NC} Monitor did not report a port on attempt $attempt."
            echo -e "${YELLOW}[WARN]${NC} Last log lines from $LOG_FILE:"
            tail -n 20 "$LOG_FILE" 2>/dev/null || echo "  (no logs yet)"

            set +e
            kill "$mpid" 2>/dev/null
            set -e
        fi
    done

    echo -e "${RED}[ERROR]${NC} Monitor failed to start after $MAX_SERVICE_RETRIES attempts. See $LOG_FILE for details."
    return 1
}

# Ensure uap0 interface exists (and try to create it from wlan0 if missing)
ensure_uap0_interface() {
    print_progress "Ensuring uap0 network interface exists"
    local attempt
    local created=false

    for attempt in $(seq 1 15); do
        if ip link show uap0 > /dev/null 2>&1; then
            echo -e "\n${GREEN}[OK]${NC} uap0 interface is present."
            # Try to bring it up (ignore failures)
            set +e
            sudo ip link set uap0 up >/dev/null 2>&1
            set -e
            return 0
        fi

        # Try to create it from wlan0 if possible
        if ip link show wlan0 > /dev/null 2>&1; then
            echo -e "\n${YELLOW}[WARN]${NC} uap0 missing; attempting to create from wlan0 (attempt $attempt)..."
            set +e
            sudo iw dev wlan0 interface add uap0 type __ap >/dev/null 2>&1
            local rc=$?
            set -e

            if [ $rc -eq 0 ]; then
                created=true
                # Give kernel a moment to register the interface
                sleep 2
                continue
            fi
        fi

        sleep 1
    done

    if ip link show uap0 > /dev/null 2>&1; then
        echo -e "\n${GREEN}[OK]${NC} uap0 appeared after retries."
        return 0
    fi

    echo -e "\n${RED}[ERROR]${NC} uap0 interface not present after multiple attempts."
    echo -e "${YELLOW}[WARN]${NC} dnsmasq@uap0.service will not be started. Check your AP setup (setupAP.py, hostapd config, and wlan0)."
    return 1
}

DEPENDENCIES=(apache2 php libapache2-mod-php php-mysql mariadb-server hostapd dnsmasq iptables iw curl wget dnsutils net-tools python3 python3-flask python3-psutil)

check_and_install() {
    local pkg="$1"
    PKG_STATUS=$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)

    if [[ "$PKG_STATUS" != *"install ok installed"* ]]; then
        echo -e "${YELLOW}[missing] Installing $pkg...${NC}"
        maybe_run sudo apt-get install -y "$pkg"
        if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
            echo -e "${GREEN}[installed] $pkg successfully installed.${NC}"
        else
            echo -e "${RED}[error] Failed to install $pkg.${NC}"
        fi
    else
        echo -e "${GREEN}[installed] $pkg already present.${NC}"
    fi
}

if [ "$FAST_LAUNCH" = false ]; then
    print_progress "Installing dependencies"
    for pkg in "${DEPENDENCIES[@]}"; do
        check_and_install "$pkg"
    done
fi

if [ "$USE_LOCAL" = false ]; then
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[ERROR]${NC} This script must be run as root for AP setup."
        exit 1
    fi

    print_progress "Running AP mode setup"
    if [ -d "$BASE_DIR/MOnitorEnv" ]; then
        maybe_run bash -c "source \"$BASE_DIR/MOnitorEnv/bin/activate\" && python3 \"$BASE_DIR/setupAP.py\" && deactivate"
    else
        maybe_run sudo python3 "$BASE_DIR/setupAP.py"
    fi
fi

# Handle CLI arguments
for arg in "$@"; do
    case $arg in
        -l|--local)
            USE_LOCAL=true
            echo -e "${BLUE}[INFO]${NC} Local network hosting enabled."
            ;;
        -f|--fastLaunch)
            FAST_LAUNCH=true
            echo -e "${BLUE}[INFO]${NC} Fast launch: skipping dependency checks."
            ;;
        -v|--verbose)
            VERBOSE=true
            echo -e "${BLUE}[INFO]${NC} Verbose mode enabled."
            ;;
        -i|--install)
            install_dependencies
            exit 0
            ;;
        -s|--status)
            show_status
            exit 0
            ;;
        --FTI)
            full_tool_install
            ;;
        --update)
            update_tool
            ;;
        --config)
            while true; do
                CURRENT_SSID=$(awk -F= '/^SSID=/{print $2}' "$CONFIG_FILE" 2>/dev/null)
                CURRENT_PASS=$(awk -F= '/^WAP_PASSPHRASE=/{print $2}' "$CONFIG_FILE" 2>/dev/null)

                OPTION=$(whiptail --title "PiPress Config Utility" --menu "Select an option:" 20 70 10 \
                "1" "Toggle USE_LOCAL (Currently: $USE_LOCAL)" \
                "2" "Toggle FAST_LAUNCH (Currently: $FAST_LAUNCH)" \
                "3" "Toggle VERBOSE (Currently: $VERBOSE)" \
                "4" "Run install_hostapd_service.py" \
                "5" "Run install_dnsmasq_service.py" \
                "6" "Edit SSID and WAP Passphrase" \
                "7" "Exit config utility" 3>&1 1>&2 2>&3)

                exitstatus=$?
                if [ $exitstatus -ne 0 ]; then
                    echo -e "${YELLOW}[WARN]${NC} Exited config."
                    exit 0
                fi

                case $OPTION in
                    1) USE_LOCAL=$( [ "$USE_LOCAL" = true ] && echo false || echo true ) ;;
                    2) FAST_LAUNCH=$( [ "$FAST_LAUNCH" = true ] && echo false || echo true ) ;;
                    3) VERBOSE=$( [ "$VERBOSE" = true ] && echo false || echo true ) ;;
                    4) sudo python3 install_hostapd_service.py ;;
                    5) sudo python3 install_dnsmasq_service.py ;;
                    6)
                        new_ssid=$(whiptail --inputbox "Enter new SSID (leave blank to keep current: $CURRENT_SSID):" 10 60 3>&1 1>&2 2>&3)
                        [ -n "$new_ssid" ] && CURRENT_SSID="$new_ssid"

                        new_pass=$(whiptail --inputbox "Enter new WAP Passphrase (leave blank to keep current):" 10 60 3>&1 1>&2 2>&3)
                        [ -n "$new_pass" ] && CURRENT_PASS="$new_pass"
                        ;;
                    7)
cat <<EOF > "$CONFIG_FILE"
[SETTINGS]
USE_LOCAL=$USE_LOCAL
FAST_LAUNCH=$FAST_LAUNCH
VERBOSE=$VERBOSE
CAPTIVEPORTAL=${CAPTIVEPORTAL:-false}
FTI=true

[NETWORK]
SSID=${CURRENT_SSID:-BetaBox1}
WAP_PASSPHRASE=${CURRENT_PASS:-BetaBox1}
EOF

                        echo -e "${GREEN}[SUCCESS]${NC} Settings saved. If you have changed SSID or WAP_Password please restart your system."
                        exit 0
                        ;;
                esac
            done
            ;;
        *)
            echo -e "${RED}[ERROR]${NC} Unknown argument: $arg"
            echo "Usage: $0 [--local] [--fastLaunch] [--verbose] [--install] [--FTI] [--config] [--status]"
            exit 1
            ;;
    esac
done

# NEW: robust uap0 handling instead of a blind 5-second wait
UAP0_OK=false
if [ "$USE_LOCAL" = false ]; then
    if ensure_uap0_interface; then
        UAP0_OK=true
    else
        UAP0_OK=false
    fi
else
    # In local mode, uap0 may not be needed; don't treat as fatal
    UAP0_OK=false
fi

print_progress "Detecting IP address"
if [ "$USE_LOCAL" = true ]; then
    AP_IP=$(hostname -I | awk '{print $1}')
else
    if [ "$UAP0_OK" = true ]; then
        AP_IP=$(ip -4 addr show uap0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || true)
    fi
fi

if [ -z "$AP_IP" ]; then
    echo -e "${RED}[ERROR]${NC} Failed to detect IP address (AP_IP is empty)."
    tput cnorm
    exit 1
fi

# Ensure hostapd and dnsmasq are actually running
dns_unit="dnsmasq"
if [ -f "/etc/systemd/system/dnsmasq@.service" ]; then
    dns_unit="dnsmasq@uap0.service"
fi

ensure_service "hostapd" "hostapd (Wi-Fi AP)"

if [ "$dns_unit" = "dnsmasq@uap0.service" ]; then
    if [ "$UAP0_OK" = true ]; then
        ensure_service "$dns_unit" "dnsmasq DNS/DHCP ($dns_unit)"
    else
        echo -e "${RED}[ERROR]${NC} Skipping start of dnsmasq@uap0.service because uap0 does not exist."
        echo -e "${YELLOW}[HINT]${NC} Check why uap0 is missing (hostapd config, iw/driver support) and rerun launch.sh."
    fi
else
    # Fallback: global dnsmasq unit
    ensure_service "$dns_unit" "dnsmasq DNS/DHCP ($dns_unit)"
fi

print_progress "Enabling Apache server"
maybe_run sudo systemctl enable apache2

ensure_service "apache2" "Apache web server"

print_progress "Starting Flask monitor"
start_monitor_with_retries

print_progress "Finalizing setup"
tput cnorm

if [ -z "$MONITOR_PORT" ]; then
    echo -e "${YELLOW}[WARN]${NC} Flask monitor port not found. Check $PORT_FILE or $LOG_FILE."
    MONITOR_PORT="???"
fi

echo ""
echo -e "${GREEN}[SUCCESS]${NC} PiPress setup complete."
echo "=============================="
echo "- Web Portal:  http://learning.betabox (http://$AP_IP)"
echo "- Monitor UI:  http://monitor.betabox (http://$AP_IP:$MONITOR_PORT)"
echo "- Logs:        $LOG_FILE"
echo "=============================="

source /home/pi/.bashrc
