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

# Load settings if config file exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

spinner_pid=""
print_step() {
    local message="$1"
    tput civis  # hide cursor
    printf "\r⏳ %s... " "$message"
}

start_spinner() {
    local spin='|/-\'
    local i=0
    while true; do
        i=$(( (i+1) % 4 ))
        printf "\r⏳ %s... %s" "$1" "${spin:$i:1}"
        sleep 0.1
    done
}

run_with_spinner() {
    local message="$1"
    shift
    start_spinner "$message" &
    spinner_pid=$!
    set +e
    "$@" > /dev/null 2>&1
    local exit_code=$?
    set -e
    kill "$spinner_pid" >/dev/null 2>&1
    wait "$spinner_pid" 2>/dev/null
    tput cnorm
    if [ $exit_code -eq 0 ]; then
        printf "\r✅ %s... Done.\n" "$message"
    else
        printf "\r❌ %s... Failed.\n" "$message"
    fi
    return $exit_code
}

show_status() {
    launch_pid=$(pgrep -f "bash .*launch.sh" | grep -v $$ || true)
    apache_status=$(systemctl is-active apache2 || echo "inactive")
    hostapd_status=$(systemctl is-active hostapd || echo "inactive")
    dnsmasq_status=$(systemctl is-active dnsmasq || echo "inactive")

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
    STATUS_TEXT+="dnsmasq: $dnsmasq_status\n"
    STATUS_TEXT+="System Monitor: $monitor_status\n"

    whiptail --title "PiPress Status Report" --msgbox "$STATUS_TEXT" 20 70
}

# Handle CLI arguments
for arg in "$@"; do
    case $arg in
        -l|--local)
            USE_LOCAL=true
            echo "📡 Local network hosting enabled."
            ;;
        -f|--fastLaunch)
            FAST_LAUNCH=true
            echo "Status: Fast launch: skipping dependency checks."
            ;;
        --config)
            while true; do
                OPTION=$(whiptail --title "PiPress Config Utility" --menu "Select an option:" 20 70 10 \
                "1" "Toggle USE_LOCAL (Currently: $USE_LOCAL)" \
                "2" "Toggle FAST_LAUNCH (Currently: $FAST_LAUNCH)" \
                "3" "Run install_hostapd_service.py" \
                "4" "Run install_dnsmasq_service.py" \
                "5" "Exit config utility" 3>&1 1>&2 2>&3)

                exitstatus=$?
                if [ $exitstatus -ne 0 ]; then
                    echo "Exited config."
                    exit 0
                fi

                case $OPTION in
                    1) USE_LOCAL=$( [ "$USE_LOCAL" = true ] && echo false || echo true ) ;;
                    2) FAST_LAUNCH=$( [ "$FAST_LAUNCH" = true ] && echo false || echo true ) ;;
                    3) sudo python3 install_hostapd_service.py ;;
                    4) sudo python3 install_dnsmasq_service.py ;;
                    5) break ;;
                esac
            done

            cat <<EOF > "$CONFIG_FILE"
USE_LOCAL=$USE_LOCAL
FAST_LAUNCH=$FAST_LAUNCH
EOF
            echo "Status: Settings saved."
            exit 0
            ;;
        -s|--status)
            show_status
            exit 0
            ;;
        *)
            echo "❌ Unknown argument: $arg"
            echo "Usage: $0 [--local] [--fastLaunch] [--config] [--status]"
            exit 1
            ;;
    esac
done

cat <<EOF > "$CONFIG_FILE"
USE_LOCAL=$USE_LOCAL
FAST_LAUNCH=$FAST_LAUNCH
EOF

DEPENDENCIES=(apache2 php libapache2-mod-php php-mysql mariadb-server hostapd dnsmasq iptables iw curl wget dnsutils net-tools python3 python3-flask python3-psutil)

check_and_install() {
    local pkg="$1"
    PKG_STATUS=$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)
    if [[ "$PKG_STATUS" != *"install ok installed"* ]]; then
        sudo apt-get install -y "$pkg"
    fi
}

if [ "$FAST_LAUNCH" = false ]; then
    print_step "Checking and installing missing dependencies"
    for pkg in "${DEPENDENCIES[@]}"; do
        run_with_spinner "Installing $pkg" check_and_install "$pkg"
    done
fi

# Run AP setup if USE_LOCAL is false
if [ "$USE_LOCAL" = false ]; then
    print_step "Running AP mode setup"
    if [ "$EUID" -ne 0 ]; then
        echo "Error: This script must be run as root for AP setup."
        exit 1
    fi

    if [ -d "$BASE_DIR/MOnitorEnv" ]; then
        print_step "Activating virtual environment"
        source "$BASE_DIR/MOnitorEnv/bin/activate"
        if python3 "$BASE_DIR/settupAP.py"; then
            deactivate
        else
            deactivate
            sudo python3 "$BASE_DIR/settupAP.py"
        fi
    else
        sudo python3 "$BASE_DIR/settupAP.py"
    fi
fi

# Detect IP address
print_step "Detecting IP address"
if [ "$USE_LOCAL" = true ]; then
    AP_IP=$(hostname -I | awk '{print $1}')
else
    AP_IP=$(ip -4 addr show uap0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
fi

if [ -z "$AP_IP" ]; then
    echo "Error: Failed to detect IP address."
    exit 1
fi

echo "Detected IP: $AP_IP"

# Start Apache
run_with_spinner "Starting Apache server" sudo systemctl restart apache2
sudo systemctl enable apache2

# Launch monitor server
print_step "Launching Flask monitor app"
cd "$MONITOR_DIR"
rm -f "$LOG_FILE" "$PORT_FILE"
nohup python3 app.py >> "$LOG_FILE" 2>&1 &

# Wait for port to be written
print_step "Waiting for monitor port file"
MONITOR_PORT=""
for i in {1..10}; do
    if [ -f "$PORT_FILE" ]; then
        MONITOR_PORT=$(cat "$PORT_FILE")
        break
    fi
    sleep 1
done

if [ -z "$MONITOR_PORT" ]; then
    echo "!! Flask port not found in time. Check $PORT_FILE or monitor.log."
    MONITOR_PORT="???"
fi

echo "Monitor running with PID $!"
echo "Logs: $LOG_FILE"

echo ""
echo "=============================="
echo "PiPress setup complete."
echo "- Web Portal:  http://$AP_IP"
echo "- Monitor UI:  http://$AP_IP:$MONITOR_PORT"
echo "- Logs:        $LOG_FILE"
echo "=============================="
