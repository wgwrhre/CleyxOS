"""Persistent personal productivity tools for the CleyxOS session."""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from core import advanced_files
from core.config import ALIASES_FILE, NOTES_FILE, TODO_FILE, ensure_app_dir, load_json, save_json


def _items(path: Path) -> list[dict[str, object]]:
    ensure_app_dir()
    value = load_json(path, [])
    return value if isinstance(value, list) else []


def _next_id(items: list[dict[str, object]]) -> int:
    return max((int(item.get("id", 0)) for item in items), default=0) + 1


def todo_add(text: str) -> dict[str, object]:
    if not text.strip():
        raise ValueError("Task text cannot be empty.")
    items = _items(TODO_FILE)
    task = {"id": _next_id(items), "text": text.strip(), "done": False,
            "created": datetime.now().astimezone().isoformat(timespec="seconds")}
    items.append(task)
    save_json(TODO_FILE, items)
    return task


def todo_list() -> list[dict[str, object]]:
    return _items(TODO_FILE)


def _find_item(path: Path, item_id: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    items = _items(path)
    for item in items:
        if item.get("id") == item_id:
            return items, item
    raise KeyError(f"No item with ID {item_id}.")


def todo_done(item_id: int) -> dict[str, object]:
    items, task = _find_item(TODO_FILE, item_id)
    task["done"] = True
    save_json(TODO_FILE, items)
    return task


def todo_remove(item_id: int) -> None:
    items, _ = _find_item(TODO_FILE, item_id)
    save_json(TODO_FILE, [item for item in items if item.get("id") != item_id])


def todo_clear() -> None:
    save_json(TODO_FILE, [])


def note_add(text: str) -> dict[str, object]:
    if not text.strip():
        raise ValueError("Note text cannot be empty.")
    notes = _items(NOTES_FILE)
    note = {"id": _next_id(notes), "text": text.strip(),
            "created": datetime.now().astimezone().isoformat(timespec="seconds")}
    notes.append(note)
    save_json(NOTES_FILE, notes)
    return note


def note_list() -> list[dict[str, object]]:
    return _items(NOTES_FILE)


def note_read(note_id: int) -> dict[str, object]:
    return _find_item(NOTES_FILE, note_id)[1]


def note_remove(note_id: int) -> None:
    notes, _ = _find_item(NOTES_FILE, note_id)
    save_json(NOTES_FILE, [note for note in notes if note.get("id") != note_id])


def note_search(query: str) -> list[dict[str, object]]:
    needle = query.casefold()
    return [note for note in note_list() if needle in str(note.get("text", "")).casefold()]


def aliases() -> dict[str, str]:
    ensure_app_dir()
    value = load_json(ALIASES_FILE, {})
    return value if isinstance(value, dict) else {}


def alias_add(name: str, command: str) -> None:
    name = name.casefold().strip()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name):
        raise ValueError("Alias names must start with a letter and contain only letters, digits, '_' or '-'.")
    if not command.strip() or any(char in command for char in ";&|\n\r"):
        raise ValueError("An alias must be one CleyxOS command; shell chaining is not allowed.")
    from core.commands import COMMANDS
    if name in COMMANDS or name in {"todo", "note", "alias", "app", "config", "language"}:
        raise ValueError("Alias name conflicts with a built-in command.")
    import shlex
    target_tokens = shlex.split(command)
    safe_targets = {
        "help", "clear", "sysinfo", "neofetch", "uptime", "processes", "performance", "ls", "cd", "pwd",
        "time", "date", "echo", "history", "whoami", "hostname", "disk", "ram", "cpu", "gpu", "battery",
        "tree", "find", "grep", "head", "tail", "wc", "du", "df", "hash", "ip", "dns", "publicip",
        "http", "open", "calc", "which", "weather", "todo", "note", "matrix", "cleyx",
    }
    existing = aliases()
    if not target_tokens or (target_tokens[0].casefold() not in safe_targets and target_tokens[0].casefold() not in existing):
        raise ValueError("Aliases can target only safe documented CleyxOS commands or other aliases.")
    stored = aliases()
    stored[name] = command.strip()
    save_json(ALIASES_FILE, stored)


def alias_remove(name: str) -> None:
    stored = aliases()
    if name not in stored:
        raise KeyError(f"Alias '{name}' was not found.")
    del stored[name]
    save_json(ALIASES_FILE, stored)


class ReminderScheduler:
    def __init__(self, notify) -> None:
        self._notify = notify
        self._timers: list[threading.Timer] = []

    def schedule(self, seconds: float, message: str) -> None:
        timer = threading.Timer(seconds, self._notify, args=(message,))
        timer.daemon = True
        self._timers.append(timer)
        timer.start()

    def cancel_all(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()


def parse_duration(raw: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(s|m|h|d)", raw.casefold())
    if not match:
        raise ValueError("Duration must look like 30s, 5m, 1h, or 1d.")
    value = float(match.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
    if not 0 < value <= 7 * 86400:
        raise ValueError("Duration must be greater than zero and no longer than 7 days.")
    return value


def countdown(seconds: float) -> None:
    from rich.live import Live
    from rich.text import Text
    from utils.terminal import console

    end = time.monotonic() + seconds
    try:
        with Live(console=console, refresh_per_second=4) as live:
            while True:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    break
                mins, secs = divmod(int(remaining + 0.999), 60)
                hours, mins = divmod(mins, 60)
                live.update(Text(f"Timer: {hours:02d}:{mins:02d}:{secs:02d}  (Ctrl+C to cancel)", style="bold cyan"))
                time.sleep(min(0.25, remaining))
    except KeyboardInterrupt:
        return
    from utils.terminal import console
    console.bell()
    console.print("[bold green]Timer complete![/bold green]")


def backup(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Backup source does not exist: {source}")
    if destination.exists():
        raise FileExistsError(f"Backup destination already exists: {destination}")
    if destination.suffix.casefold() != ".zip":
        raise ValueError("Backup destination must be a new .zip file.")
    advanced_files.create_zip(destination, [source])


def restore_backup(archive: Path, destination: Path, *, overwrite: bool = False) -> list[Path]:
    if not zipfile.is_zipfile(archive):
        raise ValueError("Backup file is not a valid ZIP archive.")
    return advanced_files.extract_zip(archive, destination, overwrite=overwrite)