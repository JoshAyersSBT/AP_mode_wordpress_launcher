# utils/status.py

RED = '\033[1;31m'
GREEN = '\033[1;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[1;34m'
NC = '\033[0m'  # No Color

def status(msg, level="INFO"):
    color = {
        "INFO": BLUE,
        "WARN": YELLOW,
        "ERROR": RED,
        "SUCCESS": GREEN
    }.get(level, NC)
    print(f"{color}[{level}] {msg}{NC}")

def log_info(msg): status(msg, "INFO")
def log_success(msg): status(msg, "SUCCESS")
def log_warn(msg): status(msg, "WARN")
def log_error(msg): status(msg, "ERROR")
