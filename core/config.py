"""Persistent user configuration and application data paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "CleyxOS"
if os.name == "nt":
    APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
else:
    APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cleyxos"
CONFIG_FILE = APP_DIR / "config.json"
APPS_FILE = APP_DIR / "apps.json"
HISTORY_FILE = APP_DIR / "history.txt"
TODO_FILE = APP_DIR / "todos.json"
NOTES_FILE = APP_DIR / "notes.json"
ALIASES_FILE = APP_DIR / "aliases.json"
WORKSPACES_FILE = APP_DIR / "workspaces.json"
FAVORITES_FILE = APP_DIR / "favorites.json"
RECENTS_FILE = APP_DIR / "recent_launches.json"
MANUAL_GAMES_FILE = APP_DIR / "games.json"
DEFAULT_CONFIG: dict[str, Any] = {"prompt": "root@cleyxos:~$", "language": "en"}


def ensure_app_dir() -> None:
    """Create the per-user data directory and default JSON files."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        save_json(CONFIG_FILE, DEFAULT_CONFIG)
    if not APPS_FILE.exists():
        save_json(APPS_FILE, {})


def load_json(path: Path, default: Any) -> Any:
    """Load JSON, returning a fresh default when absent or invalid."""
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default.copy() if isinstance(default, dict) else default


def save_json(path: Path, value: Any) -> None:
    """Write JSON atomically to avoid partial configuration files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2, ensure_ascii=False)
        file.write("\n")
    temporary.replace(path)


def get_config() -> dict[str, Any]:
    ensure_app_dir()
    value = load_json(CONFIG_FILE, DEFAULT_CONFIG)
    return value if isinstance(value, dict) else DEFAULT_CONFIG.copy()


def set_prompt(prompt: str) -> None:
    config = get_config()
    config["prompt"] = prompt
    save_json(CONFIG_FILE, config)


def set_language(language: str) -> None:
    config = get_config()
    config["language"] = language
    save_json(CONFIG_FILE, config)