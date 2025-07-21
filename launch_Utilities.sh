# File: utils.sh

print_spinner() {
    local pid=$!
    local delay=0.1
    local spinstr='|/-\'
    while ps a | awk '{print $1}' | grep -q "$pid"; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

print_step() {
    echo -e "\033[1;34m[STEP]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

set_alias_LMS() {
    SHELL_NAME=$(basename "$SHELL")
    case "$SHELL_NAME" in
        bash)  SHELL_RC="$HOME/.bashrc" ;;
        zsh)   SHELL_RC="$HOME/.zshrc" ;;
        fish)  SHELL_RC="$HOME/.config/fish/config.fish" ;;
        *)     SHELL_RC="$HOME/.bashrc" ;;
    esac

    ALIAS_CMD='alias LMS="bash ~/AP_mode_wordpress_launcher/launch.sh"'

    if ! grep -Fxq "$ALIAS_CMD" "$SHELL_RC"; then
        echo -e "\033[1;34m[INFO]\033[0m Adding alias 'LMS' to $SHELL_RC"
        echo "$ALIAS_CMD" >> "$SHELL_RC"
        echo -e "\033[1;32m[SUCCESS]\033[0m Alias added. Please restart your terminal or run: \033[1;36msource $SHELL_RC\033[0m"
    else
        echo -e "\033[1;33m[WARN]\033[0m Alias 'LMS' already present in $SHELL_RC"
    fi
}
