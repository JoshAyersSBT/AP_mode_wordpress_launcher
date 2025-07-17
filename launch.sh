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
NC='\033[0m'  # No Color

# Load settings if config file exists
if [ -f "$CONFIG_FILE" ]; then
    while IFS='=' read -r key val; do
        case $key in
            USE_LOCAL|FAST_LAUNCH|VERBOSE|SSID|WAP_PASSPHRASE|CAPTIVEPORTAL)
                eval "$key=\"$val\""
                ;;
        esac
    done < <(grep -v '^\s*#' "$CONFIG_FILE" | grep '=')
fi

TOTAL_STEPS=8
CURRENT_STEP=0

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
USE_LOCAL=$USE_LOCAL
FAST_LAUNCH=$FAST_LAUNCH
VERBOSE=$VERBOSE
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

install_dependencies() {
    echo -e "${BLUE}[*] Checking and installing system dependencies...${NC}"

    DEPENDENCIES=(
        apache2 php libapache2-mod-php php-mysql mariadb-server
        hostapd dnsmasq iptables curl wget dnsutils net-tools
        python3 python3-pip python3-venv
    )

    # Detect package manager
    if command -v apt-get &>/dev/null; then
        PKG_MANAGER="apt-get"
        UPDATE_CMD="sudo apt-get update"
        INSTALL_CMD="sudo apt-get install -y"
    elif command -v pacman &>/dev/null; then
        PKG_MANAGER="pacman"
        UPDATE_CMD="sudo pacman -Sy"
        INSTALL_CMD="sudo pacman -S --noconfirm"
    else
        echo -e "${RED}[error] Unsupported package manager. Only apt and pacman are supported.${NC}"
        exit 1
    fi

    echo -e "${YELLOW}[*] Using $PKG_MANAGER to install system packages...${NC}"
    eval "$UPDATE_CMD"

    for pkg in "${DEPENDENCIES[@]}"; do
        if [[ "$PKG_MANAGER" == "apt-get" ]]; then
            if ! dpkg -s "$pkg" &>/dev/null; then
                echo -e "${YELLOW}[missing] Installing $pkg...${NC}"
                eval "$INSTALL_CMD $pkg"
            else
                echo -e "${GREEN}[installed] $pkg${NC}"
            fi
        elif [[ "$PKG_MANAGER" == "pacman" ]]; then
            if ! pacman -Q "$pkg" &>/dev/null; then
                echo -e "${YELLOW}[missing] Installing $pkg...${NC}"
                eval "$INSTALL_CMD $pkg"
            else
                echo -e "${GREEN}[installed] $pkg${NC}"
            fi
        fi
    done

    # Install Python packages
    if [[ -f "requirements.txt" ]]; then
        echo -e "${BLUE}[*] Installing Python dependencies from requirements.txt...${NC}"
        python3 -m pip install --upgrade pip
        python3 -m pip install -r requirements.txt
    else
        echo -e "${YELLOW}[warn] No requirements.txt found. Skipping Python package installation.${NC}"
    fi

    echo -e "${GREEN}[done] All dependencies are up to date.${NC}"
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

DEPENDENCIES=(apache2 php libapache2-mod-php php-mysql mariadb-server hostapd dnsmasq iptables iw curl wget dnsutils net-tools python3 python3-flask python3-psutil)


full_tool_install() {
    echo -e "${BLUE}[*] Performing full tool initialization (--FTI)...${NC}"

    ENV_DIR="$BASE_DIR/MOnitorEnv"
    REQUIREMENTS_FILE="$BASE_DIR/requirements.txt"

    # Check and create virtual environment if missing
    if [ ! -d "$ENV_DIR" ] || [ ! -f "$ENV_DIR/bin/activate" ]; then
        echo -e "${BLUE}[*] Creating Python virtual environment at $ENV_DIR...${NC}"
        python3 -m venv "$ENV_DIR"
    else
        echo -e "${GREEN}[*] Virtual environment already exists. Skipping creation.${NC}"
    fi

    # Activate environment
    echo -e "${BLUE}[*] Activating virtual environment...${NC}"
    source "$ENV_DIR/bin/activate"

    echo -e "${BLUE}[*] Installing/upgrading pip and Python dependencies...${NC}"
    python3 -m pip install --upgrade pip

    if [ -f "$REQUIREMENTS_FILE" ]; then
        python3 -m pip install -r "$REQUIREMENTS_FILE"
    else
        echo -e "${YELLOW}[warn] requirements.txt not found. Skipping Python package installation.${NC}"
    fi

    echo -e "${BLUE}[*] Running setup scripts in environment...${NC}"
    python3 "$BASE_DIR/install_hostapd_service.py"
    python3 "$BASE_DIR/install_dnsmasq_service.py"
    python3 "$BASE_DIR/install_startup_daemon.py"

    deactivate
    echo -e "${GREEN}[done] Full tool installation complete.${NC}"
    exit 0
}


check_and_install() {
    local pkg="$1"
    PKG_STATUS=$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)
    if [[ "$PKG_STATUS" != *"install ok installed"* ]]; then
        maybe_run sudo apt-get install -y "$pkg"
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

if [ -z "$AP_IP" ]; then
    echo -e "${RED}[ERROR]${NC} Failed to detect IP address."
    exit 1
fi

print_progress "Restarting Apache server"
maybe_run sudo systemctl restart apache2
maybe_run sudo systemctl enable apache2

print_progress "Preparing Flask monitor"
cd "$MONITOR_DIR"
rm -f "$LOG_FILE" "$PORT_FILE"

print_progress "Launching monitor server"
maybe_run nohup python3 app.py >> "$LOG_FILE" 2>&1 &

print_progress "Waiting for monitor port"
MONITOR_PORT=""
for i in {1..10}; do
    if [ -f "$PORT_FILE" ]; then
        MONITOR_PORT=$(cat "$PORT_FILE")
        break
    fi
    sleep 1
done

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
echo "- Monitor UI:  http://moitor.betabox (http://$AP_IP:$MONITOR_PORT)"
echo "- Logs:        $LOG_FILE"
echo "=============================="
