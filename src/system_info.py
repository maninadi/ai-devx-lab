"""Print host system information with no third-party dependencies."""
import os
import platform
import socket
from pathlib import Path


def format_gib(size: int) -> str:
    return f"{size / 1024**3:.2f} GiB"


def system_info() -> dict[str, str | int]:
    total = free = uptime = "unavailable"
    try:
        memory = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            memory[key] = int(value.split()[0]) * 1024
        total = format_gib(memory["MemTotal"])
        free = format_gib(memory["MemFree"])
    except (OSError, ValueError, KeyError, IndexError):
        pass
    try:
        seconds = float(Path("/proc/uptime").read_text().split()[0])
        uptime = f"{seconds / 3600:.2f} hours"
    except (OSError, ValueError, IndexError):
        pass
    return {
        "Hostname": socket.gethostname(),
        "Operating system": f"{platform.system()} {platform.release()}",
        "Architecture": platform.machine(),
        "Python": platform.python_version(),
        "Logical CPUs": os.cpu_count() or 0,
        "Total memory": total,
        "Free memory": free,
        "System uptime": uptime,
    }


if __name__ == "__main__":
    print("System information")
    for label, value in system_info().items():
        print(f"{label}: {value}")
