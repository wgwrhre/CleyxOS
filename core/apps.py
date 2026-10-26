"""Explicitly registered application launcher (no shell command execution)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path

from core.config import APPS_FILE, ensure_app_dir, load_json, save_json

_DISCOVERY_TTL_SECONDS = 45.0
_discovery_cache: tuple[float, list[dict[str, str]]] | None = None
_discovery_lock = threading.RLock()
_ALIASES = {
    "vscode": "visual studio code", "code": "visual studio code",
    "chrome": "google chrome", "edge": "microsoft edge",
    "discord": "discord", "spotify": "spotify",
}


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
    invalidate_discovery_cache()
    return app


def remove_app(name: str) -> None:
    apps = list_apps()
    if name not in apps:
        raise KeyError(f"No registered application named '{name}'.")
    del apps[name]
    save_json(APPS_FILE, apps)
    invalidate_discovery_cache()


def get_app(name: str) -> dict[str, str]:
    apps = list_apps()
    if name not in apps:
        raise KeyError(f"No registered application named '{name}'.")
    return apps[name]


def find_apps(query: str) -> list[dict[str, str]]:
    """Find registered or discoverable applications by exact/partial name."""
    normalized_query = _normalize_name(query)
    if not normalized_query:
        return []
    alias_query = _ALIASES.get(normalized_query.replace(" ", ""))
    queries = {normalized_query}
    if alias_query:
        queries.add(_normalize_name(alias_query))
    candidates: list[dict[str, str]] = []
    for name, item in list_apps().items():
        candidates.append({"name": name, **item, "source": "registered"})
    candidates.extend(discover_apps())
    command_path = shutil.which(query)
    if command_path:
        candidates.append({"name": Path(command_path).stem, "path": command_path,
                           "description": "Application available on PATH", "source": "PATH"})

    unique: dict[tuple[str, str], dict[str, str]] = {}
    for candidate in candidates:
        name = candidate.get("name", "")
        path = candidate.get("path", "")
        name_key = _normalize_name(name)
        if name_key in queries:
            score = 0
        elif any(name_key.startswith(term) for term in queries):
            score = 1
        elif any(term in name_key for term in queries):
            score = 2
        else:
            similarity = max(SequenceMatcher(None, term, name_key).ratio() for term in queries)
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


def _normalize_name(name: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", name.casefold(), flags=re.UNICODE).split())


def discover_apps(*, refresh: bool = False) -> list[dict[str, str]]:
    """Return cached Windows app candidates; explicitly refresh after installation changes."""
    global _discovery_cache
    with _discovery_lock:
        now = time.monotonic()
        if not refresh and _discovery_cache and now - _discovery_cache[0] < _DISCOVERY_TTL_SECONDS:
            return [item.copy() for item in _discovery_cache[1]]
        candidates = _discover_windows_apps()
        candidates.extend(_discover_standard_install_apps())
        candidates.extend(_discover_path_apps())
        _discovery_cache = (now, candidates)
        return [item.copy() for item in candidates]


def cached_apps() -> list[dict[str, str]]:
    """Return the last completed catalog snapshot immediately; never perform discovery."""
    with _discovery_lock:
        if _discovery_cache is None:
            return []
        return [item.copy() for item in _discovery_cache[1]]


def invalidate_discovery_cache() -> None:
    global _discovery_cache
    _discovery_cache = None


def _discover_standard_install_apps() -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    roots = {
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Programs",
    }
    results = []
    for root in roots:
        try:
            for folder in root.iterdir():
                if not folder.is_dir():
                    continue
                for executable in folder.glob("*.exe"):
                    results.append({"name": folder.name, "path": str(executable),
                                    "description": "Standard installation directory", "source": "Install directory"})
                    break
        except (OSError, PermissionError):
            continue
    return results


def _discover_path_apps(*, limit: int = 1500) -> list[dict[str, str]]:
    """Index executable entries directly inside PATH directories (never recurse)."""
    results = []
    seen: set[str] = set()
    extensions = {".exe"} if os.name == "nt" else {""}
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        root = Path(directory.strip('"')).expanduser()
        if not root.is_dir():
            continue
        try:
            for item in root.iterdir():
                if not item.is_file() or item.suffix.casefold() not in extensions:
                    continue
                key = os.path.normcase(str(item))
                if key in seen:
                    continue
                seen.add(key)
                results.append({"name": item.stem, "path": str(item),
                                "description": "Executable available on PATH", "source": "PATH"})
                if len(results) >= limit:
                    return results
        except (PermissionError, OSError):
            continue
    return results


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
    found.extend(_discover_appsfolder_apps())
    return found


def _discover_appsfolder_apps() -> list[dict[str, str]]:
    """Read packaged-app identities without scanning package-private install files."""
    command = "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=5, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        rows = json.loads(result.stdout.lstrip("\ufeff"))
        if isinstance(rows, dict):
            rows = [rows]
        return [{"name": str(row["Name"]), "path": "appsfolder:" + str(row["AppID"]),
                 "description": "Packaged Windows application", "source": "Windows AppsFolder"}
                for row in rows if isinstance(row, dict) and row.get("Name") and row.get("AppID")]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError):
        return []


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
    target_text = app.get("path", "")
    if target_text.startswith("appsfolder:") and os.name == "nt":
        if arguments:
            raise ValueError("Arguments are not supported for packaged Windows apps.")
        os.startfile("shell:AppsFolder\\" + target_text.removeprefix("appsfolder:"))
        return None
    if not target_text:
        raise FileNotFoundError(f"No launch path is available for {app.get('name', name)}.")
    target = Path(target_text)
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