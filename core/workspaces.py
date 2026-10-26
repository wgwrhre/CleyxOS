"""Persistent, data-only launch workspaces; no shell commands are stored or run."""

from __future__ import annotations

import webbrowser
import re
from pathlib import Path
from urllib.parse import urlsplit

from core.config import WORKSPACES_FILE, ensure_app_dir, load_json, save_json
from core.filesystem import resolve_path


def list_workspaces() -> dict[str, list[dict[str, str]]]:
    ensure_app_dir()
    value = load_json(WORKSPACES_FILE, {})
    return value if isinstance(value, dict) else {}


def create(name: str) -> None:
    name = _validate_name(name)
    values = list_workspaces()
    if name in values:
        raise FileExistsError(f"Workspace already exists: {name}")
    values[name] = []
    save_json(WORKSPACES_FILE, values)


def add_step(name: str, step_type: str, value: str, *, cwd: Path) -> None:
    values = list_workspaces()
    if name not in values:
        raise KeyError(f"Workspace not found: {name}")
    if step_type == "folder":
        target = resolve_path(cwd, value)
        if not target.is_dir():
            raise NotADirectoryError(f"Folder not found: {target}")
        value = str(target)
    elif step_type == "url":
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) and not value.startswith(("http://", "https://")):
            raise ValueError("Only HTTP and HTTPS workspace URLs are supported.")
        address = value if value.startswith(("http://", "https://")) else "https://" + value
        parsed = urlsplit(address)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
                or any(char.isspace() for char in address)):
            raise ValueError("Enter a valid HTTP or HTTPS URL.")
        value = address
    elif step_type not in {"app", "game"}:
        raise ValueError("Unsupported workspace item type.")
    values[name].append({"type": step_type, "value": value})
    save_json(WORKSPACES_FILE, values)


def get(name: str) -> list[dict[str, str]]:
    values = list_workspaces()
    if name not in values:
        matches = [key for key in values if key.casefold().startswith(name.casefold())]
        if len(matches) == 1:
            name = matches[0]
        elif matches:
            raise ValueError(f"Ambiguous workspace name: {', '.join(matches)}")
        else:
            raise KeyError(f"Workspace not found: {name}")
    return values[name]


def remove(name: str) -> None:
    values = list_workspaces()
    if name not in values:
        raise KeyError(f"Workspace not found: {name}")
    del values[name]
    save_json(WORKSPACES_FILE, values)


def _validate_name(name: str) -> str:
    normalized = name.strip()
    if not normalized or len(normalized) > 64 or any(char in normalized for char in "/\\"):
        raise ValueError("Workspace name must be 1–64 characters and cannot contain path separators.")
    return normalized
