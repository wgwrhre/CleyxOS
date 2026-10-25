"""Read-only host system information for the CleyxOS simulation."""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
import getpass
import shutil
from datetime import timedelta
from pathlib import Path

import psutil
from rich.table import Table


def _gpu_name() -> str:
    """Return a best-effort graphics adapter name without requiring elevation."""
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name)"],
                capture_output=True, text=True, timeout=4, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            name = result.stdout.strip()
            if result.returncode == 0 and name:
                return name
        except (OSError, subprocess.SubprocessError):
            pass
    return "Unavailable"


def system_rows() -> list[tuple[str, str]]:
    memory = psutil.virtual_memory()
    return [
        ("OS", f"{platform.system()} {platform.release()} ({platform.machine()})"),
        ("CPU", platform.processor() or f"{psutil.cpu_count(logical=False) or '?'} cores"),
        ("CPU cores", f"{psutil.cpu_count(logical=False) or '?'} physical / {psutil.cpu_count() or '?'} logical"),
        ("RAM", f"{memory.total / (1024 ** 3):.1f} GiB total, {memory.percent:.0f}% used"),
        ("GPU", _gpu_name()),
        ("Python", platform.python_version()),
        ("CleyxOS", "Terminal Edition v1.0"),
    ]


def system_table() -> Table:
    table = Table(title="System Information", border_style="cyan", header_style="bold cyan")
    table.add_column("Component", style="white")
    table.add_column("Details", style="cyan")
    for label, value in system_rows():
        table.add_row(label, value)
    return table


def uptime_text(started_at: float) -> str:
    elapsed = max(0, int(time.monotonic() - started_at))
    return str(timedelta(seconds=elapsed))


def process_table(limit: int = 30) -> Table:
    table = Table(title="Running Processes (top by memory)", border_style="cyan", header_style="bold cyan")
    table.add_column("PID", justify="right", style="white")
    table.add_column("Name", style="cyan", overflow="fold")
    table.add_column("CPU %", justify="right")
    table.add_column("Memory", justify="right")
    rows = []
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
        try:
            info = proc.info
            rss = info["memory_info"].rss if info["memory_info"] else 0
            rows.append((rss, str(info["pid"]), info["name"] or "?", info["cpu_percent"] or 0))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    for rss, pid, name, cpu in sorted(rows, reverse=True)[:limit]:
        table.add_row(pid, name, f"{cpu:.1f}", f"{rss / (1024 ** 2):.1f} MiB")
    return table


def performance_table() -> Table:
    cpu = psutil.cpu_percent(interval=0.35)
    memory = psutil.virtual_memory()
    table = Table(title="Live Performance", border_style="cyan", header_style="bold cyan")
    table.add_column("Metric", style="white")
    table.add_column("Usage", style="cyan")
    table.add_row("CPU", f"{cpu:.1f}%")
    table.add_row("RAM", f"{memory.percent:.1f}% ({memory.used / (1024 ** 3):.1f} / {memory.total / (1024 ** 3):.1f} GiB)")
    return table


def disk_table() -> Table:
    table = Table(title="Available Drives", border_style="cyan", header_style="bold cyan")
    table.add_column("Drive", style="white")
    table.add_column("Total", justify="right")
    table.add_column("Used", justify="right")
    table.add_column("Free", justify="right")
    table.add_column("Usage", justify="right", style="cyan")
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            continue
        table.add_row(partition.device or partition.mountpoint,
                      _bytes(usage.total), _bytes(usage.used), _bytes(usage.free), f"{usage.percent:.1f}%")
    return table


def _bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def cpu_info() -> tuple[str, int, int, float]:
    return (platform.processor() or "Unknown", psutil.cpu_count(logical=False) or 0,
            psutil.cpu_count(logical=True) or 0, psutil.cpu_percent(interval=0.25))


def gpu_names() -> list[str]:
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=5, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return list(dict.fromkeys(line.strip() for line in result.stdout.splitlines() if line.strip()))
    except (OSError, subprocess.SubprocessError):
        return []


def battery_text() -> str:
    battery = psutil.sensors_battery()
    if battery is None:
        return "Battery information is unavailable (desktop or unsupported device)."
    remaining = "Unknown"
    if battery.secsleft >= 0:
        remaining = str(timedelta(seconds=battery.secsleft))
    return f"{battery.percent:.0f}% | {'Charging' if battery.power_plugged else 'On battery'} | Remaining: {remaining}"


def safe_environment() -> list[tuple[str, str]]:
    secret_markers = ("PASSWORD", "PASSWD", "TOKEN", "SECRET", "API_KEY", "APIKEY", "ACCESS_KEY", "CREDENTIAL", "AUTH", "COOKIE", "PRIVATE_KEY", "CONNECTION_STRING", "CLIENT_SECRET")
    rows = []
    for key, value in sorted(os.environ.items(), key=lambda entry: entry[0].casefold()):
        sensitive = any(marker in key.upper() for marker in secret_markers)
        rows.append((key, "<masked>" if sensitive else value))
    return rows


def network_interfaces() -> Table:
    table = Table(title="Network Interfaces", border_style="cyan", header_style="bold cyan")
    table.add_column("Interface", style="white")
    table.add_column("Address family")
    table.add_column("Address", style="cyan")
    table.add_column("Netmask")
    for interface, addresses in psutil.net_if_addrs().items():
        for address in addresses:
            family = "IPv4" if address.family == socket.AF_INET else "IPv6" if address.family == socket.AF_INET6 else "Link"
            if family == "Link" and not address.address:
                continue
            table.add_row(interface, family, address.address, address.netmask or "—")
    return table


def connection_table() -> Table:
    table = Table(title="Network Connections", border_style="cyan", header_style="bold cyan")
    table.add_column("Local", style="cyan")
    table.add_column("Remote")
    table.add_column("State")
    table.add_column("PID", justify="right")
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError):
        connections = []
    for conn in connections:
        local = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "—"
        remote = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "—"
        table.add_row(local, remote, conn.status or "—", str(conn.pid or "—"))
    return table