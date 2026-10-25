"""Small terminal-only interactive displays with bounded refresh rates."""

from __future__ import annotations

import os
import random
import select
import shutil
import sys
import time

import psutil
from rich.live import Live
from rich.table import Table
from rich.text import Text

from utils.terminal import console


def _key_pressed() -> str | None:
    if os.name == "nt":
        import msvcrt
        if msvcrt.kbhit():
            try:
                return msvcrt.getwch().casefold()
            except (OSError, UnicodeError):
                return None
        return None
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        return sys.stdin.read(1).casefold() if ready else None
    except (OSError, ValueError):
        return None


def process_monitor(refresh: float = 1.0, sort_by: str = "cpu") -> None:
    """Render a compact process table until Q or Ctrl+C is pressed."""
    refresh = min(max(refresh, 0.25), 5.0)
    try:
        with Live(console=console, screen=True, refresh_per_second=4) as live:
            while True:
                key = _key_pressed()
                if key == "q":
                    break
                table = Table(title=f"CleyxOS TOP · sort {sort_by} · refresh {refresh:.1f}s · press Q to exit", border_style="cyan")
                table.add_column("PID", justify="right")
                table.add_column("CPU %", justify="right")
                table.add_column("RAM", justify="right")
                table.add_column("Process", style="cyan")
                processes = []
                for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
                    try:
                        info = proc.info
                        rss = info["memory_info"].rss if info["memory_info"] else 0
                        processes.append((float(info["cpu_percent"] or 0), rss, info["pid"], info["name"] or "?"))
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                sort_key = {"cpu": lambda row: (row[0], row[1]), "ram": lambda row: (row[1], row[0]),
                            "name": lambda row: row[3].casefold()}[sort_by]
                for cpu, rss, pid, name in sorted(processes, key=sort_key, reverse=sort_by != "name")[:20]:
                    table.add_row(str(pid), f"{cpu:.1f}", f"{rss / 1024 ** 2:.1f} MiB", name)
                live.update(table, refresh=True)
                time.sleep(refresh)
    except KeyboardInterrupt:
        return


def matrix_rain(speed: float = 0.08) -> None:
    """Draw green digital rain using Rich Live and restore the terminal on exit."""
    speed = min(max(speed, 0.03), 0.5)
    glyphs = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZアカサタナハマヤラワ"
    drops: list[int] = []
    try:
        with Live(console=console, screen=True, refresh_per_second=12) as live:
            while True:
                key = _key_pressed()
                if key == "q":
                    break
                width, height = shutil.get_terminal_size((80, 24))
                width, height = max(1, width), max(2, height - 2)
                if len(drops) != width:
                    drops = (drops + [random.randint(-height, 0) for _ in range(width)])[:width]
                canvas = [[" " for _ in range(width)] for _ in range(height)]
                for column, head in enumerate(drops):
                    if random.random() < 0.08:
                        drops[column] += 1
                    head = drops[column]
                    for trail in range(5):
                        row = head - trail
                        if 0 <= row < height:
                            canvas[row][column] = random.choice(glyphs)
                    if head > height + random.randrange(2, 15):
                        drops[column] = random.randint(-height // 2, 0)
                frame = Text()
                for row in canvas:
                    frame.append("".join(row) + "\n", style="green")
                frame.append("MATRIX RAIN · Press Q or Ctrl+C to exit", style="bold green")
                live.update(frame, refresh=True)
                time.sleep(speed)
    except KeyboardInterrupt:
        return


def stopwatch() -> None:
    """Interactive stopwatch with simple textual control commands."""
    from prompt_toolkit import PromptSession

    session: PromptSession[str] = PromptSession()
    elapsed = 0.0
    started: float | None = None
    console.print("Stopwatch commands: start, pause, resume, reset, q")
    while True:
        try:
            action = session.prompt("stopwatch> ").strip().casefold()
        except (KeyboardInterrupt, EOFError):
            break
        if action in {"q", "exit"}:
            break
        if action == "start" and started is None:
            elapsed = 0.0
            started = time.monotonic()
        elif action == "pause" and started is not None:
            elapsed += time.monotonic() - started
            started = None
        elif action == "resume" and started is None:
            started = time.monotonic()
        elif action == "reset":
            elapsed = 0.0
            started = None
        elif action == "time":
            total = elapsed + (time.monotonic() - started if started is not None else 0)
            console.print(f"Elapsed: {total:.2f}s")
        else:
            console.print("Use start, pause, resume, reset, time, or q.")