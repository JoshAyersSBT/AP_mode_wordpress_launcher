# monitor/utils/sysinfo.py
import os
import platform
import subprocess
from pathlib import Path

import psutil


def _usage_color(pct: float) -> str:
    """Return a hex-ish color based on usage percentage."""
    if pct < 50:
        return "#5cb85c"  # green
    if pct < 75:
        return "#f0ad4e"  # orange
    return "#d9534f"      # red


def _temp_color(c: float) -> str:
    if c < 50:
        return "#5cb85c"
    if c < 70:
        return "#f0ad4e"
    return "#d9534f"


def _get_apache_status() -> str:
    """
    Try a few ways to detect Apache/httpd status.
    On Windows (or if apache isn't installed), just return a friendly string.
    """
    system = platform.system().lower()

    # Linux / systemd
    if system == "linux":
        cmds = [
            ["systemctl", "is-active", "apache2"],
            ["systemctl", "is-active", "apache"],
            ["service", "apache2", "status"],
            ["service", "apache", "status"],
        ]
        for cmd in cmds:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                out = result.stdout.strip()
                if out:
                    return out
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        return "unknown"

    # Windows or anything else:
    # you could try `sc query Apache2.4` here if you have it installed,
    # but it's safer to just say it's not available.
    return "not available on this OS"


def _get_temp_c() -> float:
    """Best-effort temperature reading."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return 40.0
        # pick first sensor with data
        for name, entries in temps.items():
            if entries:
                # take first
                return float(entries[0].current)
    except Exception:
        pass
    return 40.0


def _tail_logs() -> str:
    """
    Try to read a log file near the monitor, but don't crash if it isn't there.
    """
    candidates = [
        Path(__file__).resolve().parent.parent / "monitor.log",  # monitor/monitor.log
        Path("/var/log/apache2/error.log"),
        Path("/var/log/apache2/access.log"),
    ]
    for p in candidates:
        try:
            p = Path(p)
            if p.is_file():
                data = p.read_bytes()
                # return last ~200 lines
                text = data.decode("utf-8", errors="replace")
                lines = text.splitlines()[-200:]
                return "\n".join(lines)
        except Exception:
            continue
    return "[no logs found]"


def get_status_info() -> dict:
    # CPU and RAM
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    memory_percent = mem.percent

    # Temp (best effort)
    temp_c = _get_temp_c()

    # Apache status (best effort)
    apache_status = _get_apache_status()

    # Logs
    log_output = _tail_logs()

    return {
        # CPU
        "cpu_percent": cpu_percent,
        "cpu_color": _usage_color(cpu_percent),
        "cpu_load": f"{cpu_percent:.1f}%",

        # RAM
        "ram_usage": f"{memory_percent:.1f}%",
        "ram_percent": memory_percent,
        "ram_color": _usage_color(memory_percent),

        # Temp
        "temp_c": f"{temp_c:.1f}°C",
        "temp_percent": min((temp_c / 85.0) * 100.0, 100.0),
        "temp_color": _temp_color(temp_c),

        # Service
        "apache_status": apache_status,

        # Logs
        "logs": log_output,
    }
