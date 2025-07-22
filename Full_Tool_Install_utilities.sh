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

    TOOL_DIR="/AP_mode_wordpress_launcher"
    REPO_URL="https://github.com/JoshAyersSBT/AP_mode_wordpress_launcher.git"
    TMP_DIR="/tmp/AP_mode_wordpress_launcher_tmp"
    ENV_DIR="$TOOL_DIR/MOnitorEnv"
    REQUIREMENTS_FILE="$TOOL_DIR/requirements.txt"

    # --- Step 1: Clone latest repo to temporary location
    echo -e "${BLUE}[*] Cloning latest version of the tool from GitHub into temporary directory...${NC}"
    rm -rf "$TMP_DIR"
    git clone --depth=1 "$REPO_URL" "$TMP_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to clone the repository. Aborting.${NC}"
        exit 1
    fi

    # --- Step 2: Move into final location
    echo -e "${YELLOW}[*] Replacing existing install at $TOOL_DIR...${NC}"
    rm -rf "$TOOL_DIR"
    mv "$TMP_DIR" "$TOOL_DIR"
    cd "$TOOL_DIR" || exit 1

    # --- Step 3: Install required system packages
    echo -e "${BLUE}[*] Installing required system packages...${NC}"
    FTI_DEPENDENCIES=(
        apache2 php libapache2-mod-php php-mysql mariadb-server
        hostapd dnsmasq iptables curl wget dnsutils net-tools
        python3 python3-pip python3-venv
    )
    for pkg in "${FTI_DEPENDENCIES[@]}"; do
        if ! dpkg -s "$pkg" &> /dev/null; then
            echo -e "${YELLOW}[missing] Installing $pkg...${NC}"
            apt-get install -y "$pkg"
        else
            echo -e "${GREEN}[installed] $pkg${NC}"
        fi
    done

    # --- Step 4: Rebuild the virtual environment
    if [ -d "$ENV_DIR" ]; then
        echo -e "${YELLOW}[*] Removing existing virtual environment at $ENV_DIR...${NC}"
        rm -rf "$ENV_DIR"
    fi

    echo -e "${BLUE}[*] Creating fresh Python virtual environment at $ENV_DIR...${NC}"
    python3 -m venv "$ENV_DIR"

    echo -e "${BLUE}[*] Activating virtual environment...${NC}"
    source "$ENV_DIR/bin/activate"

    echo -e "${BLUE}[*] Installing Python dependencies...${NC}"
    python3 -m pip install --upgrade pip --break-system-packages

    if [ -f "$REQUIREMENTS_FILE" ]; then
        python3 -m pip install --break-system-packages -r "$REQUIREMENTS_FILE"
    else
        echo -e "${YELLOW}[warn] requirements.txt not found. Skipping Python package installation.${NC}"
    fi

    # --- Step 5: Run setup scripts
    echo -e "${BLUE}[*] Running setup scripts...${NC}"
    python3 "$TOOL_DIR/install_hostapd_service.py"
    python3 "$TOOL_DIR/install_dnsmasq_service.py"
    python3 "$TOOL_DIR/install_startup_daemon.py"

    deactivate

    # --- Step 7: Add system link
# -------- Remove conflicting LMS aliases/functions --------
echo -e "\033[1;34m[INFO]\033[0m Removing any conflicting LMS aliases or functions..."

USER_NAME="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo "~$USER_NAME")
USER_SHELL=$(getent passwd "$USER_NAME" | cut -d: -f7)
SHELL_NAME=$(basename "$USER_SHELL")

# Determine shell config
case "$SHELL_NAME" in
    bash)  SHELL_RC="$USER_HOME/.bashrc" ;;
    zsh)   SHELL_RC="$USER_HOME/.zshrc" ;;
    fish)  SHELL_RC="$USER_HOME/.config/fish/config.fish" ;;
    *)     SHELL_RC="$USER_HOME/.bashrc" ;;
esac

# Remove any LMS alias or function from shell config
sed -i '/alias LMS=/d' "$SHELL_RC"
sed -i '/LMS() {/,+1d' "$SHELL_RC" 2>/dev/null

echo -e "\033[1;32m[SUCCESS]\033[0m Conflicting LMS aliases/functions removed from $SHELL_RC"

# -------- Create global LMS command --------
echo -e "\033[1;34m[INFO]\033[0m Installing global LMS command to /usr/local/bin..."

sudo bash -c 'cat > /usr/local/bin/LMS' <<'EOF'
#!/bin/bash
sudo bash /AP_mode_wordpress_launcher/launch.sh "$@"
EOF

sudo chmod +x /usr/local/bin/LMS

echo -e "\033[1;32m[SUCCESS]\033[0m LMS command installed at /usr/local/bin/LMS"
echo -e "\033[1;34m[INFO]\033[0m You can now run it from anywhere: \033[1;36mLMS --status\033[0m"


    # --- Step 7: Launch configuration UI
    echo -e "${BLUE}[*] Launching configuration utility...${NC}"
    "$TOOL_DIR/launch.sh" --config

    # --- Step 8: Run tool
    "$TOOL_DIR/launch.sh"

    exit 0
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

update_tool() {
    echo -e "${BLUE}[*] Updating AP Mode WordPress Launcher from GitHub...${NC}"

    TOOL_DIR="/AP_mode_wordpress_launcher"
    REPO_URL="https://github.com/JoshAyersSBT/AP_mode_wordpress_launcher.git"

    # Prevent recursion if already inside an FTI-based clone
    if [ "$(pwd)" = "$TOOL_DIR" ]; then
        echo -e "${YELLOW}[WARN] Already running from updated tool directory ($TOOL_DIR). Skipping re-clone.${NC}"
        echo -e "${BLUE}[*] Running full tool install...${NC}"
        "$TOOL_DIR/launch.sh" --FTI
        exit 0
    fi

    TMP_DIR="/tmp/AP_mode_wordpress_launcher_update"
    echo -e "${YELLOW}[*] Cloning latest repo to temporary directory...${NC}"
    rm -rf "$TMP_DIR"
    git clone --depth=1 "$REPO_URL" "$TMP_DIR"

    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to clone repository. Aborting.${NC}"
        exit 1
    fi

    echo -e "${YELLOW}[*] Replacing existing tool at $TOOL_DIR...${NC}"
    rm -rf "$TOOL_DIR"
    mv "$TMP_DIR" "$TOOL_DIR"

    echo -e "${GREEN}[SUCCESS]${NC} Update complete. Running --FTI..."
    "$TOOL_DIR/launch.sh" --FTI
    exit 0
}

