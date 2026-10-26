"""Local game discovery and launch integration; no DRM or authentication bypass."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from difflib import SequenceMatcher
from pathlib import Path

from core import apps
from core.config import MANUAL_GAMES_FILE, ensure_app_dir, load_json, save_json

_GAME_MARKERS = ("steamapps", "epic games", "gog galaxy", "ubisoft", "ea games", "xboxgames", "minecraft", "roblox", "games")
_GAME_CACHE_TTL = 60.0
_game_cache: tuple[float, list[dict[str, str]]] | None = None
_game_cache_lock = __import__("threading").RLock()


def discover_games(*, refresh: bool = False) -> list[dict[str, str]]:
    """Use cached app shortcuts plus Steam/Epic local manifests and manual registrations."""
    global _game_cache
    with _game_cache_lock:
        now = time.monotonic()
        if not refresh and _game_cache and now - _game_cache[0] < _GAME_CACHE_TTL:
            return [game.copy() for game in _game_cache[1]]
        candidates: list[dict[str, str]] = []
        for app in apps.discover_apps(refresh=refresh):
            path = app.get("path", "").casefold()
            if any(marker in path for marker in _GAME_MARKERS) or any(marker in app.get("name", "").casefold() for marker in ("steam", "epic games", "gog", "ubisoft", "ea app", "xbox")):
                candidates.append({**app, "source": app.get("source", "shortcut")})
        candidates.extend(_steam_games())
        candidates.extend(_epic_games())
        candidates.extend(_standalone_games())
        candidates.extend(_manual_games().values())
        games_found = _deduplicate(candidates)
        _game_cache = (now, games_found)
        return [game.copy() for game in games_found]


def cached_games() -> list[dict[str, str]]:
    """Return the last completed game snapshot without scanning manifests or folders."""
    with _game_cache_lock:
        return [game.copy() for game in _game_cache[1]] if _game_cache else []


def _steam_roots() -> list[Path]:
    roots = []
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if base:
            roots.append(Path(base) / "Steam")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Steam")
    return list(dict.fromkeys(root for root in roots if root.is_dir()))


def _steam_games() -> list[dict[str, str]]:
    found = []
    for root in _steam_roots():
        library_file = root / "steamapps" / "libraryfolders.vdf"
        libraries = [root]
        try:
            text = library_file.read_text(encoding="utf-8", errors="replace")
            libraries.extend(Path(value.replace("\\\\", "\\")) for value in re.findall(r'"path"\s+"([^"]+)"', text))
        except OSError:
            pass
        for library in set(libraries):
            manifests = library / "steamapps"
            try:
                for manifest in manifests.glob("appmanifest_*.acf"):
                    contents = manifest.read_text(encoding="utf-8", errors="replace")
                    name = re.search(r'"name"\s+"([^"]+)"', contents)
                    appid = re.search(r'"appid"\s+"(\d+)"', contents)
                    installdir = re.search(r'"installdir"\s+"([^"]+)"', contents)
                    if name and appid:
                        install = manifests / "common" / (installdir.group(1) if installdir else name.group(1))
                        found.append({"name": name.group(1), "path": str(install), "appid": appid.group(1),
                                      "source": "Steam", "launcher": "steam"})
            except OSError:
                continue
    return found


def _epic_games() -> list[dict[str, str]]:
    manifest_root = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    found = []
    try:
        for manifest in manifest_root.glob("*.item"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                name = str(data.get("DisplayName", "")).strip()
                location = str(data.get("InstallLocation", ""))
                if name:
                    found.append({"name": name, "path": location, "appid": str(data.get("AppName") or data.get("CatalogItemId", "")),
                                  "source": "Epic Games", "launcher": "epic"})
            except (OSError, json.JSONDecodeError):
                continue
    except OSError:
        pass
    return found


def _standalone_games() -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    program_files = [Path(os.environ.get(key, "")) for key in ("ProgramFiles", "ProgramFiles(x86)") if os.environ.get(key)]
    roots = [Path(os.environ.get("USERPROFILE", Path.home())) / "Games", Path("C:/Games")]
    for base in program_files:
        roots.extend(base / name for name in ("Games", "EA Games", "Epic Games", "Ubisoft Game Launcher/games", "GOG Galaxy/Games"))
    found = []
    for root in dict.fromkeys(roots):
        try:
            if not root.is_dir():
                continue
            for game_folder in root.iterdir():
                if not game_folder.is_dir() or game_folder.is_symlink():
                    continue
                executables = list(game_folder.glob("*.exe"))
                if not executables:
                    try:
                        for child in game_folder.iterdir():
                            if child.is_dir() and not child.is_symlink():
                                executables.extend(child.glob("*.exe"))
                                if executables:
                                    break
                    except OSError:
                        pass
                if executables:
                    found.append({"name": game_folder.name, "path": str(sorted(executables, key=lambda p: p.name.casefold())[0]),
                                  "source": "Standalone installation", "launcher": "standalone"})
        except (PermissionError, OSError):
            continue
    return found


def _manual_games() -> dict[str, dict[str, str]]:
    ensure_app_dir()
    value = load_json(MANUAL_GAMES_FILE, {})
    return value if isinstance(value, dict) else {}


def register_game(name: str, path_or_uri: str) -> dict[str, str]:
    if not name.strip() or len(name) > 100:
        raise ValueError("Game name must be 1–100 characters.")
    if path_or_uri.startswith(("steam://", "com.epicgames.launcher://", "appsfolder:")):
        target = path_or_uri
    else:
        target_path = Path(path_or_uri).expanduser().resolve()
        if not target_path.exists():
            raise FileNotFoundError(f"Game target not found: {target_path}")
        if not target_path.is_file() or target_path.suffix.casefold() not in {".exe", ".lnk"}:
            raise ValueError("Manual game targets must be .exe/.lnk files or supported Steam/Epic launcher URIs.")
        target = str(target_path)
    games = _manual_games()
    entry = {"name": name.strip(), "path": target, "source": "Manual registration"}
    games[name.strip()] = entry
    save_json(MANUAL_GAMES_FILE, games)
    invalidate_game_cache()
    return entry


def invalidate_game_cache() -> None:
    global _game_cache
    _game_cache = None


def _deduplicate(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        key = candidate.get("name", "").casefold()
        if key and key not in unique:
            unique[key] = candidate
    return sorted(unique.values(), key=lambda item: item["name"].casefold())


def search_games(query: str) -> list[dict[str, str]]:
    needle = _normalize(query)
    results = []
    for candidate in discover_games():
        name = _normalize(candidate.get("name", ""))
        if not name:
            continue
        if needle in name:
            score = 0 if needle == name else 1
        else:
            score = 2 - SequenceMatcher(None, needle, name).ratio()
            if score > 1.25:
                continue
        results.append({**candidate, "_score": f"{score:.3f}"})
    return sorted(results, key=lambda item: (float(item["_score"]), item["name"].casefold()))


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def launch_game(game: dict[str, str]) -> None:
    target = game.get("path", "")
    launcher = game.get("launcher")
    if launcher == "steam" and game.get("appid"):
        os.startfile(f"steam://rungameid/{game['appid']}")
        return
    if launcher == "epic" and game.get("appid"):
        os.startfile(f"com.epicgames.launcher://apps/{game['appid']}?action=launch&silent=true")
        return
    if target.startswith("appsfolder:"):
        if os.name != "nt":
            raise OSError("Packaged Windows games can only launch on Windows.")
        os.startfile("shell:AppsFolder\\" + target.removeprefix("appsfolder:"))
        return
    if target.startswith(("steam://", "com.epicgames.launcher://")):
        os.startfile(target)
        return
    path = Path(target)
    if path.is_file() and path.suffix.casefold() in {".exe", ".lnk"}:
        if path.suffix.casefold() == ".lnk":
            os.startfile(str(path))
        else:
            subprocess.Popen([str(path)], cwd=str(path.parent), shell=False)
        return
    raise FileNotFoundError("No safe launch target found. Register the game with a launcher URI or executable.")


def record_launch(name: str, *, limit: int = 20) -> None:
    from core.config import RECENTS_FILE
    ensure_app_dir()
    value = load_json(RECENTS_FILE, [])
    entries = value if isinstance(value, list) else []
    entries.insert(0, {"name": name, "kind": "game", "time": time.time()})
    save_json(RECENTS_FILE, entries[:limit])
