"""Explicitly registered application launcher (no shell command execution)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

from core.config import APPS_FILE, ensure_app_dir, load_json, save_json


def list_apps() -> dict[str, dict[str, str]]:
    ensure_app_dir()
    value = load_json(APPS_FILE, {})
    return value if isinstance(value, dict) else {}


def add_app(name: str, executable: str, description: str = "") -> dict[str, str]:
    if not name or any(char in name for char in "/\\"):
        raise ValueError("Application name must be a simple, non-empty name.")
    target = Path(executable).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Application file not found: {target}")
    if target.suffix.casefold() not in {".py", ".exe"}:
        raise ValueError("Supported applications: Python scripts (.py) and Windows executables (.exe).")
    apps = list_apps()
    app = {"path": str(target), "description": description}
    apps[name] = app
    save_json(APPS_FILE, apps)
    return app


def remove_app(name: str) -> None:
    apps = list_apps()
    if name not in apps:
        raise KeyError(f"No registered application named '{name}'.")
    del apps[name]
    save_json(APPS_FILE, apps)


def get_app(name: str) -> dict[str, str]:
    apps = list_apps()
    if name not in apps:
        raise KeyError(f"No registered application named '{name}'.")
    return apps[name]


def find_apps(query: str) -> list[dict[str, str]]:
    """Find registered or discoverable applications by exact/partial name."""
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return []
    candidates: list[dict[str, str]] = []
    for name, item in list_apps().items():
        candidates.append({"name": name, **item, "source": "registered"})
    candidates.extend(_discover_windows_apps())
    command_path = shutil.which(query)
    if command_path:
        candidates.append({"name": Path(command_path).stem, "path": command_path,
                           "description": "Application available on PATH", "source": "PATH"})

    unique: dict[tuple[str, str], dict[str, str]] = {}
    for candidate in candidates:
        name = candidate.get("name", "")
        path = candidate.get("path", "")
        name_key = name.casefold()
        if name_key == normalized_query:
            score = 0
        elif name_key.startswith(normalized_query):
            score = 1
        elif normalized_query in name_key:
            score = 2
        else:
            similarity = SequenceMatcher(None, normalized_query, name_key).ratio()
            if similarity < 0.62:
                continue
            score = 3
        candidate["_score"] = str(score)
        key = (name_key, os.path.normcase(path))
        prior = unique.get(key)
        if prior is None or (candidate.get("source") == "registered" and prior.get("source") != "registered"):
            unique[key] = candidate
    by_name: dict[str, dict[str, str]] = {}
    for candidate in unique.values():
        key = candidate["name"].casefold()
        previous = by_name.get(key)
        if previous is None or (not previous.get("path") and candidate.get("path")):
            by_name[key] = candidate
        elif previous.get("source") != "registered" and candidate.get("source") == "registered":
            by_name[key] = candidate
    return sorted(by_name.values(), key=lambda item: (int(item["_score"]), item["name"].casefold()))


def find_registered_app(query: str) -> tuple[str, dict[str, str]] | None:
    """Resolve a registered application using case-insensitive partial matching."""
    matches = []
    for name, item in list_apps().items():
        if query.casefold() == name.casefold():
            return name, item
        if query.casefold() in name.casefold():
            matches.append((name, item))
    return matches[0] if len(matches) == 1 else None


def _discover_windows_apps() -> list[dict[str, str]]:
    """Read public app names/launch shortcuts from Start Menu and uninstall metadata."""
    if os.name != "nt":
        return []
    found: list[dict[str, str]] = []
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    start_menus = [
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        program_data / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for root in start_menus:
        if not root.is_dir():
            continue
        for folder, _, filenames in os.walk(root):
            for filename in filenames:
                if Path(filename).suffix.casefold() not in {".lnk", ".exe"}:
                    continue
                path = Path(folder) / filename
                found.append({"name": path.stem, "path": str(path),
                              "description": "Start Menu application shortcut", "source": "Start Menu"})
    found.extend(_discover_uninstall_registry())
    return found


def _discover_uninstall_registry() -> list[dict[str, str]]:
    """Collect installed app display metadata; never runs uninstall commands."""
    try:
        import winreg
    except ImportError:
        return []
    results: list[dict[str, str]] = []
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    views = (getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0))
    for root in roots:
        for view in views:
            try:
                with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as uninstall_key:
                    count = winreg.QueryInfoKey(uninstall_key)[0]
                    for index in range(count):
                        try:
                            subkey_name = winreg.EnumKey(uninstall_key, index)
                            with winreg.OpenKey(uninstall_key, subkey_name) as app_key:
                                values = {}
                                for value_name in ("DisplayName", "DisplayIcon", "InstallLocation", "DisplayVersion", "Publisher"):
                                    try:
                                        values[value_name] = winreg.QueryValueEx(app_key, value_name)[0]
                                    except OSError:
                                        pass
                            display_name = str(values.get("DisplayName", "")).strip()
                            if not display_name:
                                continue
                            executable = _executable_from_icon(str(values.get("DisplayIcon", "")))
                            if not executable:
                                install_location = Path(str(values.get("InstallLocation", "")))
                                if install_location.is_dir():
                                    matching = sorted(install_location.glob("*.exe"), key=lambda p: p.name.casefold())
                                    executable = str(matching[0]) if matching else ""
                            results.append({
                                "name": display_name, "path": executable,
                                "description": "Installed application",
                                "version": str(values.get("DisplayVersion", "")),
                                "publisher": str(values.get("Publisher", "")),
                                "source": "Windows installed-app registry",
                            })
                        except OSError:
                            continue
            except OSError:
                continue
    return results


def _executable_from_icon(icon: str) -> str:
    """Extract an existing executable path from a DisplayIcon registry value."""
    match = re.search(r'"?(.+?\.exe)(?:"|,\s*-?\d+)?$', icon, re.IGNORECASE)
    if not match:
        return ""
    candidate = Path(os.path.expandvars(match.group(1).strip('" ')))
    return str(candidate) if candidate.is_file() else ""


def launch_app(name: str, arguments: list[str], *, resolved: dict[str, str] | None = None) -> subprocess.Popen[bytes] | None:
    app = resolved or get_app(name)
    target = Path(app["path"])
    if not target.is_file():
        raise FileNotFoundError(f"Registered application no longer exists: {target}")
    if target.suffix.casefold() == ".py":
        command = [sys.executable, str(target), *arguments]
    elif target.suffix.casefold() == ".exe" and os.name == "nt":
        command = [str(target), *arguments]
    elif target.suffix.casefold() == ".lnk" and os.name == "nt":
        if arguments:
            raise ValueError("Arguments are not supported for Start Menu shortcuts.")
        os.startfile(str(target))
        return None
    else:
        raise OSError("This application does not have a supported launch target.")
    return subprocess.Popen(command, cwd=str(target.parent), shell=False)