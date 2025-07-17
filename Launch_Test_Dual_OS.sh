#!/bin/bash

# PiPress Launch Script with AP-STA Mode Support + Configurable Settings

set -e

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
NC='\033[0m'

# Detect distro
DISTRO=""
PKG_MANAGER=""
APACHE_SERVICE=""

TOTAL_STEPS=8
CURRENT_STEP=0

# Load settings if config file exists
if [ -f "$CONFIG_FILE" ]; then
    grep -v '^\s*#' "$CONFIG_FILE" | grep '=' | while IFS='=' read -r key val; do
        case $key in
            USE_LOCAL|FAST_LAUNCH|VERBOSE|SSID|WAP_PASSPHRASE|CAPTIVEPORTAL)
                eval "$key=\"$val\""
                ;;
        esac
    done
fi

detect_distro() {
    if grep -qi 'arch' /etc/os-release; then
        DISTRO="arch"
        PKG_MANAGER="pacman"
        APACHE_SERVICE="httpd"
    elif grep -qi 'debian\|ubuntu\|raspbian' /etc/os-release; then
        DISTRO="debian"
        PKG_MANAGER="apt"
        APACHE_SERVICE="apache2"
    else
        echo -e "${RED}[ERROR]${NC} Unsupported distro."
        exit 1
    fi
}

print_progress() {
    local message="$1"
    CURRENT_STEP=$((CURRENT_STEP + 1))
    local percent=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    local bar_len=$((percent / 10))
    local bar=$(printf '%0.s#' $(seq 1 $bar_len))
    local spaces=$(printf '%0.s-' $(seq 1 $((10 - bar_len))))
    tput civis
    printf "\r[%s%s] %3d%% - %s" "$bar" "$spaces" "$percent" "$message"
    sleep 0.5
}

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
    apache_status=$(systemctl is-active "$APACHE_SERVICE" || echo "inactive")
    hostapd_status=$(systemctl is-active hostapd || echo "inactive")
    dnsmasq_status=$(systemctl is-active dnsmasq || echo "inactive")

    monitor_pid=$(pgrep -f "python3.*app.py" || true)
    monitor_port=$(ss -tuln | grep ":5000 " || true)

    monitor_status="Not Running"
    [ -n "$monitor_pid" ] && monitor_status="Running (PID: $monitor_pid)"
    monitor_status+=" | Port 5000: "
    monitor_status+=$([ -n "$monitor_port" ] && echo "Listening" || echo "Not Listening")

    STATUS_TEXT="Launch Script PID: ${launch_pid:-Not Running}\n"
    STATUS_TEXT+="Apache: $apache_status\n"
    STATUS_TEXT+="hostapd: $hostapd_status\n"
    STATUS_TEXT+="dnsmasq: $dnsmasq_status\n"
    STATUS_TEXT+="System Monitor: $monitor_status\n"

    whiptail --title "PiPress Status Report" --msgbox "$STATUS_TEXT" 20 70
}

# CLI Argument Handling
for arg in "$@"; do
    case $arg in
        -l|--local) USE_LOCAL=true; echo -e "${BLUE}[INFO]${NC} Local network hosting enabled." ;;
        -f|--fastLaunch) FAST_LAUNCH=true; echo -e "${BLUE}[INFO]${NC} Fast launch: skipping dependency checks." ;;
        -v|--verbose) VERBOSE=true; echo -e "${BLUE}[INFO]${NC} Verbose mode enabled." ;;
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
                [ $? -ne 0 ] && echo -e "${YELLOW}[WARN]${NC} Exited config." && exit 0
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
USE_LOCAL=$USE_LOCAL
FAST_LAUNCH=$FAST_LAUNCH
VERBOSE=$VERBOSE
SSID=${CURRENT_SSID:-BetaBox1}
WAP_PASSPHRASE=${CURRENT_PASS:-BetaBox1}
EOF
                        echo -e "${GREEN}[SUCCESS]${NC} Settings saved. Restart required for SSID/passphrase changes."
                        exit 0
                        ;;
                esac
            done ;;
        -s|--status) show_status; exit 0 ;;
        *) echo -e "${RED}[ERROR]${NC} Unknown argument: $arg"; exit 1 ;;
    esac
done

detect_distro

# Save config
cat <<EOF > "$CONFIG_FILE"
USE_LOCAL=$USE_LOCAL
FAST_LAUNCH=$FAST_LAUNCH
VERBOSE=$VERBOSE
EOF

if [ "$DISTRO" = "debian" ]; then
    DEPENDENCIES=(apache2 php libapache2-mod-php php-mysql mariadb-server hostapd dnsmasq iptables iw curl wget dnsutils net-tools python3 python3-flask python3-psutil)
else
    DEPENDENCIES=(httpd php php-apache php-mysql mariadb hostapd dnsmasq iptables iw curl wget bind net-tools python python-flask python-psutil)
fi

install_pkg() {
    local pkg="$1"
    if [ "$PKG_MANAGER" = "apt" ]; then
        PKG_STATUS=$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)
        [[ "$PKG_STATUS" != *"install ok installed"* ]] && maybe_run sudo apt-get install -y "$pkg"
    else
        pacman -Qi "$pkg" > /dev/null 2>&1 || maybe_run sudo pacman -S --noconfirm "$pkg"
    fi
}

if [ "$FAST_LAUNCH" = false ]; then
    print_progress "Installing dependencies"
    for pkg in "${DEPENDENCIES[@]}"; do
        install_pkg "$pkg"
    done
fi

if [ "$USE_LOCAL" = false ]; then
    [ "$EUID" -ne 0 ] && echo -e "${RED}[ERROR]${NC} Must run as root for AP mode." && exit 1
    print_progress "Running AP mode setup"
    if [ -d "$BASE_DIR/MOnitorEnv" ]; then
        maybe_run bash -c "source \"$BASE_DIR/MOnitorEnv/bin/activate\" && python3 \"$BASE_DIR/settupAP.py\" && deactivate"
    else
        maybe_run sudo python3 "$BASE_DIR/settupAP.py"
    fi
fi

print_progress "Detecting IP address"
if [ "$USE_LOCAL" = true ]; then
    AP_IP=$(hostname -I | awk '{print $1}')
else
    AP_IP=$(ip -4 addr show uap0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
fi
[ -z "$AP_IP" ] && echo -e "${RED}[ERROR]${NC} Could not determine IP." && exit 1

print_progress "Restarting Apache"
maybe_run sudo systemctl restart "$APACHE_SERVICE"
maybe_run sudo systemctl enable "$APACHE_SERVICE"

print_progress "Preparing Flask monitor"
cd "$MONITOR_DIR"
rm -f "$LOG_FILE" "$PORT_FILE"

print_progress "Launching monitor server"
maybe_run nohup python3 app.py >> "$LOG_FILE" 2>&1 &

print_progress "Waiting for monitor port"
MONITOR_PORT=""
for i in {1..10}; do
    [ -f "$PORT_FILE" ] && MONITOR_PORT=$(cat "$PORT_FILE") && break
    sleep 1
done

print_progress "Finalizing setup"
tput cnorm

[ -z "$MONITOR_PORT" ] && echo -e "${YELLOW}[WARN]${NC} Flask port not found. Check $PORT_FILE or $LOG_FILE." && MONITOR_PORT="???"

echo ""
echo -e "${GREEN}[SUCCESS]${NC} PiPress setup complete."
echo "=============================="
echo "- Web Portal:  http://learning.betabox (http://$AP_IP)"
echo "- Monitor UI:  http://moitor.betabox (http://$AP_IP:$MONITOR_PORT)"
echo "- Logs:        $LOG_FILE"
echo "=============================="
