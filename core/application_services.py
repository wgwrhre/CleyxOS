"""User-facing app/game catalog services and safe confirmation helpers."""

from __future__ import annotations

import getpass
import os
import time
from pathlib import Path

import psutil
from rich.table import Table

from core import apps, games
from core.config import FAVORITES_FILE, RECENTS_FILE, ensure_app_dir, load_json, save_json
from core.i18n import get_language, translate_message
from utils.terminal import console


def choose_match(query: str, matches: list[dict[str, str]], *, kind: str = "application") -> dict[str, str] | None:
    if not matches:
        raise LookupError(f"No {kind} matches '{query}'.")
    top_score = matches[0].get("_score", "0")
    exact = [item for item in matches if item.get("_score", "0") == top_score]
    if len(exact) == 1 and float(top_score) <= 1:
        return exact[0]
    options = matches[:10]
    turkish = get_language() == "tr"
    table = Table(title=f"{kind} seçin" if turkish else f"Choose {kind}", border_style="cyan")
    table.add_column("#", justify="right")
    table.add_column("Ad" if turkish else "Name", style="white")
    table.add_column("Kaynak" if turkish else "Source", style="cyan")
    table.add_column("Konum" if turkish else "Location")
    for index, item in enumerate(options, 1):
        table.add_row(str(index), item.get("name", ""), item.get("source", ""), item.get("path", "")[:80])
    console.print(table)
    answer = console.input("Bir sayı girin, iptal için Enter: " if turkish else "Enter a number, or press Enter to cancel: ").strip()
    if not answer:
        return None
    if not answer.isdigit() or not 1 <= int(answer) <= len(options):
        raise ValueError("Selection must be one of the displayed numbers.")
    return options[int(answer) - 1]


def confirm_launch(item: dict[str, str], *, kind: str = "application") -> bool:
    prompt = f"Launch {kind} '{item.get('name', 'unknown')}' from {item.get('source', 'registered source')}? [y/N]: "
    answer = console.input(translate_message(prompt))
    return answer.strip().casefold() == "y"


def launch_application(item: dict[str, str], *, arguments: list[str] | None = None) -> None:
    if not item.get("path"):
        raise FileNotFoundError(f"{item.get('name', 'Application')} was discovered, but Windows did not provide a launch path. Register a verified executable with 'app add'.")
    source = item.get("source", "")
    if source == "registered":
        process = apps.launch_app(item["name"], arguments or [], resolved=item)
    else:
        process = apps.launch_app(item["name"], arguments or [], resolved=item)
    record_launch(item.get("name", "application"), "app")
    suffix = f" (PID {process.pid})" if process is not None else ""
    console.print(f"[success]Launched {item['name']}{suffix}.[/success]")


def launch_game(item: dict[str, str]) -> None:
    games.launch_game(item)
    record_launch(item.get("name", "game"), "game")
    console.print(f"[success]Launched {item['name']} through {item.get('source', 'registered target')}.[/success]")


def record_launch(name: str, kind: str, *, limit: int = 30) -> None:
    ensure_app_dir()
    entries = load_json(RECENTS_FILE, [])
    recent = entries if isinstance(entries, list) else []
    recent = [item for item in recent if not (item.get("name", "").casefold() == name.casefold() and item.get("kind") == kind)]
    recent.insert(0, {"name": name, "kind": kind, "time": time.time()})
    save_json(RECENTS_FILE, recent[:limit])


def recent(kind: str) -> list[dict[str, object]]:
    ensure_app_dir()
    entries = load_json(RECENTS_FILE, [])
    return [item for item in entries if isinstance(item, dict) and item.get("kind") == kind] if isinstance(entries, list) else []


def favorites(kind: str) -> list[str]:
    ensure_app_dir()
    value = load_json(FAVORITES_FILE, {})
    return list(value.get(kind, [])) if isinstance(value, dict) and isinstance(value.get(kind), list) else []


def favorite_add(kind: str, name: str) -> None:
    value = load_json(FAVORITES_FILE, {})
    values = value if isinstance(value, dict) else {}
    items = values.get(kind, [])
    if not isinstance(items, list):
        items = []
    if not any(str(item).casefold() == name.casefold() for item in items):
        items.append(name)
    values[kind] = items
    save_json(FAVORITES_FILE, values)


def favorite_remove(kind: str, name: str) -> None:
    value = load_json(FAVORITES_FILE, {})
    values = value if isinstance(value, dict) else {}
    items = values.get(kind, [])
    matches = [item for item in items if str(item).casefold() == name.casefold()]
    if not matches:
        raise KeyError(f"Favorite not found: {name}")
    values[kind] = [item for item in items if str(item).casefold() != name.casefold()]
    save_json(FAVORITES_FILE, values)


def close_application(query: str, *, game: bool = False) -> int:
    matches = games.search_games(query) if game else apps.find_apps(query)
    if not matches:
        raise LookupError(f"No running-app catalog match for '{query}'.")
    executable_names = {Path(item.get("path", "")).stem.casefold() for item in matches}
    display_names = {item.get("name", "").casefold() for item in matches}
    to_close = []
    current_user = getpass.getuser().casefold()
    protected_names = {"system", "registry", "smss", "csrss", "wininit", "services", "lsass", "winlogon", "svchost", "dwm", "explorer", "cleyxos"}
    protected_pids = {0, 4, os.getpid(), os.getppid()}
    parent = psutil.Process(os.getpid())
    while True:
        try:
            parent = parent.parent()
            if parent is None:
                break
            protected_pids.add(parent.pid)
        except (psutil.Error, OSError):
            break
    for process in psutil.process_iter(["pid", "name", "username"]):
        try:
            info = process.info
            process_name = Path(info.get("name") or "").stem.casefold()
            username = (info.get("username") or "").split("\\")[-1].casefold()
            if (not process_name or not username or process_name in protected_names
                    or process.pid in protected_pids or username != current_user):
                continue
            display_match = any(candidate and (candidate in process_name or process_name in candidate) for candidate in display_names)
            if process_name in executable_names or display_match:
                to_close.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    if not to_close:
        raise LookupError(f"No matching running process found for '{query}'.")
    console.print("Processes to close: " + ", ".join(f"{proc.name()} ({proc.pid})" for proc in to_close))
    if console.input("Close these processes? Type 'yes' to confirm: ").strip().casefold() != "yes":
        console.print("[warning]Cancelled.[/warning]")
        return 0
    closed = 0
    for process in to_close:
        try:
            process.terminate()
            process.wait(timeout=3)
            closed += 1
        except (psutil.Error, OSError):
            continue
    return closed
