import psutil
import subprocess

def get_status_info():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent

    # Apache status
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "apache2"],
            capture_output=True, text=True, check=True
        )
        apache_status = result.stdout.strip()
    except subprocess.CalledProcessError:
        apache_status = "unknown"

    # Logs
    try:
        log_output = subprocess.run(
            ["journalctl", "-u", "apache2", "-n", "10", "--no-pager"],
            capture_output=True, text=True, check=True
        ).stdout
    except subprocess.CalledProcessError:
        log_output = "Failed to retrieve logs."

    # Temperature
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            raw_temp = int(f.read().strip())
            temp_c = raw_temp / 1000.0
    except:
        temp_c = 0.0

    def usage_color(percent):
        if percent < 50:
            return "#4caf50"
        elif percent < 75:
            return "#ff9800"
        else:
            return "#f44336"

    def temp_color(temp):
        if temp < 55:
            return "#4caf50"
        elif temp < 70:
            return "#ff9800"
        else:
            return "#f44336"

    return {
        "cpu_load": f"{cpu_percent:.1f}%",
        "cpu_percent": cpu_percent,
        "cpu_color": usage_color(cpu_percent),

        "ram_usage": f"{memory_percent:.1f}%",
        "ram_percent": memory_percent,
        "ram_color": usage_color(memory_percent),

        "temp_c": f"{temp_c:.1f}°C",
        "temp_percent": min((temp_c / 85.0) * 100, 100),  # 85°C as high threshold
        "temp_color": temp_color(temp_c),

        "apache_status": apache_status,
        "logs": log_output
    }
