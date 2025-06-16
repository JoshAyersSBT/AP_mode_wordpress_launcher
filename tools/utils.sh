#!/bin/bash

# utils.sh
# Utility functions for PiPress scripts

# Log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if a service is active
is_service_active() {
    local service=$1
    systemctl is-active --quiet "$service"
    return $?
}

# Restart a service and log
restart_service() {
    local service=$1
    log "Restarting service: $service"
    sudo systemctl restart "$service"
}

# Tail last 10 lines of a log file
tail_log() {
    local logfile=$1
    if [ -f "$logfile" ]; then
        tail -n 10 "$logfile"
    else
        echo "Log file not found: $logfile"
    fi
}
