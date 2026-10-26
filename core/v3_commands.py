"""CleyxOS v3 desktop integration, media, workspaces, and productivity commands."""

from __future__ import annotations

import calendar as calendar_module
import datetime as dt
import re
import os
import platform
import secrets
import string
import subprocess
import sys
import time
import uuid as uuid_module
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import psutil
import requests
from rich.panel import Panel
from rich.table import Table

from core import advanced_files, apps, application_services, file_tools, games, media, productivity, workspaces
from core.config import get_config, save_json
from core.version import GITHUB_REPOSITORY, VERSION
from core.filesystem import resolve_path
from core.i18n import command_description, get_language, translate_message
from core import windows_controls
from utils.terminal import console

APPLICATION_COMMANDS = {
    "launch", "openapp", "searchapp", "installed", "appinfo", "appfolder", "closeapp", "recentapps", "favoriteapp",
    "play", "games", "findgame", "gameinfo", "gamefolder", "recentgames", "stopgame", "favoritegame", "registergame",
}
MEDIA_COMMANDS = {"watch", "videos", "findvideo", "video", "music", "playmedia", "youtube", "spotify"}
WINDOWS_COMMANDS = {
    "volume", "mute", "unmute", "brightness", "screenshot", "clipboard", "lock", "sleep", "shutdown", "restart",
    "settings", "taskmanager", "controlpanel", "startupapps", "downloads", "desktop", "documents", "pictures",
    "videosfolder", "musicfolder", "recentfiles", "openfile", "reveal", "findfile", "findfolder", "largestfiles",
    "duplicates", "emptyfolders", "cleanup",
}
PRODUCTIVITY_COMMANDS = {
    "quicknote", "quicknotes", "calendar", "convert", "passwordgen", "uuid", "random", "qr", "focus", "pomodoro",
    "dictionary", "translate", "workspace", "tutorial", "examples", "commands", "searchcommand", "whatsnew", "tips",
    "shortcuts", "doctor", "version", "updatecheck", "searchpath", "workshop",
}
COMMANDS_V3: dict[str, str] = {
    "launch": "Find an installed application and launch it after confirmation",
    "openapp": "Alias for launch", "searchapp": "Search installed applications",
    "installed": "List discovered applications", "appinfo": "Display application information",
    "appfolder": "Open an application's installation folder", "closeapp": "Close an app after confirmation",
    "recentapps": "Show recently launched apps", "favoriteapp": "Manage favorite applications",
    "play": "Find and launch a game through its platform after confirmation",
    "games": "List discovered games", "findgame": "Search discovered games", "gameinfo": "Show game information",
    "gamefolder": "Open a game's installation folder", "recentgames": "Show recently launched games",
    "stopgame": "Stop a game after confirmation", "favoritegame": "Manage favorite games",
    "registergame": "Manually register a game path or platform URI",
    "watch": "Find and play a local video", "videos": "List videos in configured folders",
    "findvideo": "Search configured video folders", "video": "Inspect or configure videos",
    "music": "Find music or list/configure audio folders", "playmedia": "Open a local media file",
    "youtube": "Search YouTube", "spotify": "Search Spotify",
    "volume": "Set or adjust system volume", "mute": "Mute system audio", "unmute": "Unmute system audio",
    "brightness": "Set or adjust display brightness", "screenshot": "Save a desktop screenshot",
    "clipboard": "Copy, inspect, or clear clipboard text", "lock": "Lock the Windows session",
    "sleep": "Put Windows to sleep after confirmation", "shutdown": "Shut down Windows after confirmation",
    "restart": "Restart Windows after confirmation", "settings": "Open a Windows Settings category",
    "taskmanager": "Open Task Manager", "controlpanel": "Open Control Panel", "startupapps": "Open startup app settings",
    "findfile": "Search common user folders for files", "findfolder": "Search common user folders for directories",
    "openfile": "Find and open a file", "reveal": "Reveal a file in Explorer", "downloads": "Open Downloads",
    "desktop": "Open Desktop", "documents": "Open Documents", "pictures": "Open Pictures",
    "videosfolder": "Open Videos", "musicfolder": "Open Music", "recentfiles": "Show files opened through CleyxOS",
    "largestfiles": "List largest files under a directory", "duplicates": "Find duplicate files by SHA-256",
    "emptyfolders": "Find empty directories", "cleanup": "Preview or remove safe old temporary files",
    "quicknote": "Save a persistent quick note", "quicknotes": "List quick notes", "calendar": "Display a monthly calendar",
    "convert": "Convert common measurement units", "passwordgen": "Generate a secure random password", "uuid": "Generate a UUID",
    "random": "Generate a random integer", "qr": "Generate a QR code image", "focus": "Start a focus countdown",
    "pomodoro": "Start a Pomodoro focus interval", "dictionary": "Look up an English word definition",
    "translate": "Translate through an optional configured HTTPS provider",
    "workspace create": "Create a named launch workspace", "workspace addapp": "Add an application to a workspace",
    "workspace addgame": "Add a game to a workspace", "workspace addfolder": "Add a folder to a workspace",
    "workspace addurl": "Add a website to a workspace", "workspace run": "Run all workspace actions",
    "workspace list": "List saved workspaces", "workspace info": "Show workspace actions", "workspace remove": "Remove a workspace",
    "tutorial": "Show beginner guide", "examples": "Show examples for a command", "commands": "Browse all commands",
    "searchcommand": "Search command names and descriptions", "whatsnew": "Show CleyxOS v3 changes",
    "tips": "Show practical CleyxOS tips", "shortcuts": "Show keyboard and command shortcuts",
    "doctor": "Run safe local diagnostics", "version": "Show CleyxOS version", "updatecheck": "Check GitHub releases",
    "searchpath": "Manage folders searched by findfile/findfolder",
    "workshop": "Alias for workspace commands",
}


def handles(command: str) -> bool:
    return command in APPLICATION_COMMANDS | MEDIA_COMMANDS | WINDOWS_COMMANDS | PRODUCTIVITY_COMMANDS


def dispatch(shell, command: str, args: list[str]) -> bool:
    if command == "workshop":
        command = "workspace"
    if command in APPLICATION_COMMANDS:
        return _applications(command, args)
    if command in MEDIA_COMMANDS:
        return _media(shell, command, args)
    if command in WINDOWS_COMMANDS:
        return _windows(shell, command, args)
    if command in PRODUCTIVITY_COMMANDS:
        return _productivity(shell, command, args)
    return True


def _applications(command: str, args: list[str]) -> bool:
    if command in {"launch", "openapp", "searchapp", "appinfo", "appfolder"}:
        query = " ".join(args).strip()
        if not query:
            raise ValueError(f"Usage: {command} <application name>")
        matches = apps.find_apps(query)
        if command == "searchapp":
            _catalog_table(matches, "Application search")
            return True
        selected = application_services.choose_match(query, matches)
        if selected is None:
            return True
        if command in {"launch", "openapp"}:
            if application_services.confirm_launch(selected):
                application_services.launch_application(selected)
            else:
                console.print("[warning]Launch cancelled.[/warning]")
        elif command == "appinfo":
            _app_info(selected)
        else:
            _open_install_folder(selected)
        return True
    if command == "installed":
        _arity(command, args, 0)
        registered = [{"name": name, **item, "source": "CleyxOS registration"} for name, item in apps.list_apps().items()]
        combined = {item.get("name", "").casefold(): item for item in [*apps.discover_apps(), *registered]}
        _catalog_table(sorted(combined.values(), key=lambda item: item.get("name", "").casefold()), "Installed applications")
        return True
    if command in {"closeapp", "stopgame"}:
        query = " ".join(args).strip()
        if not query:
            raise ValueError(f"Usage: {command} <name>")
        is_game = command == "stopgame"
        matches = games.search_games(query) if is_game else apps.find_apps(query)
        selected = application_services.choose_match(query, matches, kind="game" if is_game else "application")
        if selected is None:
            return True
        count = application_services.close_application(selected["name"], game=is_game)
        console.print(f"[success]Closed {count} process(es).[/success]")
        return True
    if command in {"play", "findgame", "gameinfo", "gamefolder"}:
        query = " ".join(args).strip()
        if not query:
            raise ValueError(f"Usage: {command} <game name>")
        matches = games.search_games(query)
        if command == "findgame":
            _catalog_table(matches, "Game search")
            return True
        selected = application_services.choose_match(query, matches, kind="game")
        if selected is None:
            return True
        if command == "play":
            if application_services.confirm_launch(selected, kind="game"):
                application_services.launch_game(selected)
            else:
                console.print("[warning]Launch cancelled.[/warning]")
        elif command == "gameinfo":
            _app_info(selected)
        else:
            _open_install_folder(selected)
        return True
    if command == "games":
        _arity(command, args, 0)
        _catalog_table(games.discover_games(), "Discovered games")
        return True
    if command == "registergame":
        if len(args) < 2:
            raise ValueError("Usage: registergame <name> <executable|platform-uri>")
        entry = games.register_game(args[0], " ".join(args[1:]))
        console.print(f"[success]Registered game {entry['name']}.[/success]")
        return True
    if command in {"recentapps", "recentgames"}:
        _arity(command, args, 0)
        kind = "game" if command == "recentgames" else "app"
        for item in application_services.recent(kind):
            console.print(f"{dt.datetime.fromtimestamp(float(item['time'])).astimezone():%Y-%m-%d %H:%M}  {item['name']}")
        return True
    if command in {"favoriteapp", "favoritegame"}:
        return _favorites("game" if command == "favoritegame" else "app", args)
    raise ValueError("Unknown application command.")


def _favorites(kind: str, args: list[str]) -> bool:
    if not args:
        raise ValueError(f"Usage: favorite{kind} <add|list|remove> [name]")
    action, name_parts = args[0].casefold(), args[1:]
    if action == "list" and not name_parts:
        items = application_services.favorites(kind)
        console.print("\n".join(items) if items else "No favorites yet.")
    elif action == "add" and name_parts:
        query = " ".join(name_parts)
        matches = games.search_games(query) if kind == "game" else apps.find_apps(query)
        selected = application_services.choose_match(query, matches, kind="game" if kind == "game" else "application")
        if selected is None:
            return True
        name = selected["name"]
        application_services.favorite_add(kind, name)
        console.print(translate_message(f"[success]Added favorite {name}.[/success]"))
    elif action == "remove" and name_parts:
        name = " ".join(name_parts)
        application_services.favorite_remove(kind, name)
        console.print(translate_message(f"[success]Removed favorite {name}.[/success]"))
    else:
        raise ValueError(f"Usage: favorite{kind} <add|list|remove> [name]")
    return True


def _catalog_table(items: list[dict[str, str]], title: str) -> None:
    turkish = get_language() == "tr"
    table = Table(title=f"{title} (Türkçe)" if turkish else title, border_style="cyan")
    table.add_column("Ad" if turkish else "Name", style="white")
    table.add_column("Kaynak" if turkish else "Source", style="cyan")
    table.add_column("Konum" if turkish else "Location", overflow="fold")
    for item in items[:300]:
        table.add_row(item.get("name", ""), item.get("source", ""), item.get("path", ""))
    console.print(table if items else f"No {title.casefold()} found.")


def _app_info(item: dict[str, str]) -> None:
    details = [f"Name: {item.get('name', '')}", f"Source: {item.get('source', 'unknown')}", f"Path: {item.get('path') or 'Unavailable'}"]
    for key in ("version", "publisher", "description", "appid"):
        if item.get(key):
            details.append(f"{key.title()}: {item[key]}")
    console.print(Panel("\n".join(details), title="Application information", border_style="cyan"))


def _open_install_folder(item: dict[str, str]) -> None:
    raw = item.get("path", "")
    if raw.startswith("appsfolder:"):
        raise OSError("Windows does not expose a normal installation folder for this packaged app.")
    if not raw:
        raise FileNotFoundError(f"Installation folder is unavailable for {item.get('name', 'this item')}.")
    target = Path(raw)
    folder = target if target.is_dir() else target.parent
    if not folder.is_dir():
        raise FileNotFoundError(f"Installation folder is unavailable: {folder}")
    os.startfile(str(folder))


def _media(shell, command: str, args: list[str]) -> bool:
    if command in {"watch", "findvideo", "videos", "music", "playmedia"}:
        if command == "video":
            pass
        elif command == "videos":
            _media_list("video", "")
            return True
        elif command == "music" and args and args[0].casefold() in {"list", "setfolder"}:
            action = args[0].casefold()
            if action == "list":
                _media_list("audio", "")
            else:
                if len(args) < 2:
                    raise ValueError("Usage: music setfolder <path>")
                media.set_folder("audio", resolve_path(shell.cwd, " ".join(args[1:])))
                console.print("[success]Music folder saved.[/success]")
            return True
        elif command == "playmedia":
            if not args:
                raise ValueError("Usage: playmedia <file>")
            target = resolve_path(shell.cwd, " ".join(args))
            if target.suffix.casefold() not in media.VIDEO_EXTENSIONS | media.AUDIO_EXTENSIONS:
                raise ValueError("Unsupported media format. Use MP4/MKV/AVI/MOV/WEBM or MP3/WAV/FLAC/OGG/M4A.")
            media.open_media(target)
            _record_recent_media(target)
            return True
        elif command == "music":
            query = " ".join(args)
            matches = media.find_media(query, "audio")
            selected = _choose_path(query, matches)
            if selected:
                media.open_media(selected)
                _record_recent_media(selected)
            return True
        else:
            if command == "watch" and args and args[0].casefold() in {"info", "recent", "setfolder"}:
                return _video_subcommand(shell, args)
            query = " ".join(args)
            if not query:
                raise ValueError(f"Usage: {command} <name>")
            matches = media.find_media(query, "video")
            selected = _choose_path(query, matches)
            if selected:
                media.open_media(selected)
                _record_recent_media(selected)
            return True
    if command == "video":
        return _video_subcommand(shell, args)
    if command == "youtube":
        media.open_youtube_search(" ".join(args))
    elif command == "spotify":
        media.open_spotify_search(" ".join(args))
    return True


def _video_subcommand(shell, args: list[str]) -> bool:
    if not args:
        raise ValueError("Usage: video <info <file>|recent|setfolder <path>>")
    action = args[0].casefold()
    if action == "info" and len(args) >= 2:
        target = resolve_path(shell.cwd, " ".join(args[1:]))
        if not target.is_file() or target.suffix.casefold() not in media.VIDEO_EXTENSIONS:
            raise ValueError("The selected file is not a supported video.")
        stat = target.stat()
        console.print(Panel(f"Name: {target.name}\nFormat: {target.suffix}\nSize: {stat.st_size:,} bytes\nModified: {dt.datetime.fromtimestamp(stat.st_mtime).astimezone()}", title="Video information", border_style="cyan"))
    elif action == "recent":
        for item in _recent_media():
            console.print(f"{item.get('time')}  {item.get('path')}")
    elif action == "setfolder" and len(args) >= 2:
        media.set_folder("video", resolve_path(shell.cwd, " ".join(args[1:])))
        console.print("[success]Video folder saved.[/success]")
    else:
        raise ValueError("Usage: video <info <file>|recent|setfolder <path>>")
    return True


def _media_list(kind: str, query: str) -> None:
    files = media.find_media(query, kind)
    for item in files:
        console.print(str(item))
    if not files:
        console.print(f"No {kind} files found in configured folders.")


def _choose_path(query: str, paths: list[Path]) -> Path | None:
    if not paths:
        console.print(f"No media match for '{query}'.")
        return None
    if len(paths) == 1:
        return paths[0]
    for number, path in enumerate(paths[:10], 1):
        console.print(f"{number}. {path}")
    answer = console.input("Choose a number, or Enter to cancel: ").strip()
    if not answer:
        return None
    if not answer.isdigit() or not 1 <= int(answer) <= min(10, len(paths)):
        raise ValueError("Choose one of the displayed numbers.")
    return paths[int(answer) - 1]


def _recent_media() -> list[dict[str, object]]:
    from core.application_services import recent
    return recent("video")


def _record_recent_media(path: Path) -> None:
    from core.application_services import record_launch
    kind = "video" if path.suffix.casefold() in media.VIDEO_EXTENSIONS else "audio"
    record_launch(str(path), kind)


def _windows(shell, command: str, args: list[str]) -> bool:
    if command == "volume":
        if not args:
            console.print(f"Volume: {windows_controls.get_volume()}%")
        elif args[0].casefold() in {"up", "down"}:
            amount = int(args[1]) if len(args) > 1 else 5
            if len(args) > 2 or amount < 1:
                raise ValueError("Usage: volume up|down [amount]")
            new_level = max(0, min(100, windows_controls.get_volume() + (amount if args[0].casefold() == "up" else -amount)))
            windows_controls.set_volume(new_level)
            console.print(f"[success]Volume: {new_level}%[/success]")
        elif len(args) == 1 and args[0].isdigit():
            windows_controls.set_volume(int(args[0]))
            console.print(f"[success]Volume set to {args[0]}%.[/success]")
        else:
            raise ValueError("Usage: volume <0-100>|up [amount]|down [amount]")
    elif command in {"mute", "unmute"}:
        _arity(command, args, 0)
        windows_controls.mute(command == "mute")
        console.print(f"[success]{'Muted' if command == 'mute' else 'Unmuted'}.[/success]")
    elif command == "brightness":
        if not args:
            raise ValueError("Usage: brightness <0-100>|up [amount]|down [amount]")
        if args[0].casefold() in {"up", "down"}:
            if len(args) > 2:
                raise ValueError("Usage: brightness up|down [amount]")
            amount = int(args[1]) if len(args) > 1 else 10
            if amount < 1:
                raise ValueError("Brightness adjustment must be positive.")
            level = max(0, min(100, amount))
            try:
                import screen_brightness_control as sbc
                current = sbc.get_brightness(display=0)[0]
            except Exception as error:
                raise OSError(f"Brightness is unavailable: {error}") from error
            level = max(0, min(100, current + (level if args[0].casefold() == "up" else -level)))
        elif len(args) == 1 and args[0].isdigit():
            level = int(args[0])
        else:
            raise ValueError("Usage: brightness <0-100>|up [amount]|down [amount]")
        windows_controls.set_brightness(level)
        console.print(f"[success]Brightness set to {level}%.[/success]")
    elif command == "screenshot":
        _arity(command, args, 0)
        folder = Path.home() / "Pictures"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"CleyxOS-{dt.datetime.now():%Y%m%d-%H%M%S}.png"
        windows_controls.screenshot(path)
        console.print(f"[success]Screenshot saved: {path}[/success]")
    elif command == "clipboard":
        if not args:
            raise ValueError("Usage: clipboard <copy <text>|show|clear>")
        action = args[0].casefold()
        if action == "copy":
            result = windows_controls.clipboard(action, " ".join(args[1:]))
        elif action in {"show", "clear"} and len(args) == 1:
            if action == "show":
                console.print("[bold yellow]Clipboard may contain private information. Displaying it now.[/bold yellow]")
            result = windows_controls.clipboard(action)
        else:
            raise ValueError("Usage: clipboard <copy <text>|show|clear>")
        console.print(result, markup=False)
    elif command == "lock":
        _arity(command, args, 0)
        windows_controls.lock_session()
    elif command in {"sleep", "shutdown", "restart"}:
        _arity(command, args, 0)
        if not _confirm_windows(f"{command.title()} Windows now?", required="yes"):
            console.print("[warning]Cancelled.[/warning]")
            return True
        if command == "sleep":
            windows_controls.sleep_computer()
        else:
            windows_controls.power_action(command)
    elif command == "settings":
        if len(args) != 1:
            raise ValueError("Usage: settings <sound|display|network|bluetooth|storage|applications|updates|personalization|privacy|power>")
        category = "sound" if args[0].casefold() == "audio" else args[0].casefold()
        windows_controls.open_settings(category)
    elif command in {"taskmanager", "controlpanel", "startupapps"}:
        _arity(command, args, 0)
        windows_controls.open_system_tool(command)
    elif command in {"downloads", "desktop", "documents", "pictures", "videosfolder", "musicfolder"}:
        _arity(command, args, 0)
        windows_controls.open_known_folder(command)
    elif command in {"findfile", "findfolder", "openfile"}:
        query = " ".join(args)
        if not query:
            raise ValueError(f"Usage: {command} <name>")
        matches = file_tools.find_paths(query, directories_only=command == "findfolder", files_only=command in {"findfile", "openfile"})
        if command == "openfile" and matches:
            selected = _choose_path(query, matches)
            if selected:
                if selected.suffix.casefold() in {".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".msi", ".lnk", ".py", ".pyw", ".js", ".jse", ".vbs", ".vbe", ".wsf", ".hta", ".reg", ".url", ".scr"}:
                    if not _confirm_windows(f"Open executable or script {selected}?", required="yes"):
                        console.print("[warning]Cancelled.[/warning]")
                        return True
                os.startfile(str(selected))
                _record_recent_file(selected)
        else:
            for path in matches[:100]:
                console.print(str(path))
            if not matches:
                console.print("No matching files or folders.")
            if len(matches) >= 500:
                console.print("[yellow]Search result limit reached.[/yellow]")
    elif command == "reveal":
        if not args:
            raise ValueError("Usage: reveal <file>")
        windows_controls.reveal_file(resolve_path(shell.cwd, " ".join(args)))
    elif command == "recentfiles":
        _arity(command, args, 0)
        for item in _recent_files():
            console.print(f"{item.get('time')}  {item.get('path')}")
    elif command == "largestfiles":
        if not args:
            raise ValueError("Usage: largestfiles <directory>")
        for size, path in file_tools.largest_files(resolve_path(shell.cwd, " ".join(args))):
            console.print(f"{size:>12,} bytes  {path}")
    elif command == "duplicates":
        if not args:
            raise ValueError("Usage: duplicates <directory>")
        groups = file_tools.duplicate_files(resolve_path(shell.cwd, " ".join(args)))
        for group in groups:
            console.print("Duplicate group (no files deleted):")
            for path in group:
                console.print(f"  {path}")
        if not groups:
            console.print("No duplicate files found.")
    elif command == "emptyfolders":
        if not args:
            raise ValueError("Usage: emptyfolders <directory>")
        folders = file_tools.empty_folders(resolve_path(shell.cwd, " ".join(args)))
        console.print("\n".join(map(str, folders)) if folders else "No empty folders found.")
    elif command == "cleanup":
        if len(args) != 1 or args[0].casefold() not in {"preview", "run"}:
            raise ValueError("Usage: cleanup preview|run")
        candidates = file_tools.cleanup_candidates()
        for path in candidates:
            console.print(str(path))
        console.print(f"{len(candidates)} old temporary file(s) eligible (older than 7 days).")
        if args[0].casefold() == "run" and candidates:
            if _confirm_windows("Remove only these listed temporary files?", required="yes"):
                removed = file_tools.remove_cleanup_candidates(candidates)
                console.print(f"[success]Removed {removed} temporary file(s).[/success]")
            else:
                console.print("[warning]Cancelled.[/warning]")
    return True


def _recent_files() -> list[dict[str, object]]:
    from core.application_services import recent
    return recent("file")


def _record_recent_file(path: Path) -> None:
    from core.application_services import record_launch
    record_launch(str(path), "file")


def _productivity(shell, command: str, args: list[str]) -> bool:
    if command in {"quicknote", "quicknotes"}:
        if command == "quicknote":
            if not args:
                raise ValueError("Usage: quicknote <text>")
            item = productivity.note_add(" ".join(args))
            console.print(f"[success]Saved quick note #{item['id']}.[/success]")
        else:
            for item in productivity.note_list():
                console.print(f"#{item['id']}  {item['text']}")
    elif command == "calendar":
        month, year = dt.date.today().month, dt.date.today().year
        if args:
            if len(args) != 1 or args[0].casefold() not in {"next", "previous"}:
                raise ValueError("Usage: calendar [next|previous]")
            delta = 1 if args[0].casefold() == "next" else -1
            year, month = (year + 1, 1) if month + delta == 13 else (year - 1, 12) if month + delta == 0 else (year, month + delta)
        console.print(calendar_module.month(year, month))
    elif command == "convert":
        if len(args) != 3:
            raise ValueError("Usage: convert <value> <from> <to> (length: m/km/mi/ft, weight: kg/lb, temp: c/f)")
        console.print(_convert(args[0], args[1], args[2]))
    elif command == "passwordgen":
        length = int(args[0]) if args else 20
        if len(args) > 1 or not 8 <= length <= 128:
            raise ValueError("Usage: passwordgen [length 8-128]")
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        console.print("[bold cyan]" + "".join(secrets.choice(alphabet) for _ in range(length)) + "[/bold cyan]")
    elif command == "uuid":
        _arity(command, args, 0)
        console.print(str(uuid_module.uuid4()))
    elif command == "random":
        if len(args) != 2:
            raise ValueError("Usage: random <min> <max>")
        low, high = int(args[0]), int(args[1])
        if low > high or high - low > 2**63:
            raise ValueError("Require min <= max, with a range no larger than 2^63.")
        console.print(secrets.randbelow(high - low + 1) + low)
    elif command == "qr":
        if not args:
            raise ValueError("Usage: qr <text>")
        try:
            import qrcode
        except ImportError as error:
            raise RuntimeError("QR support requires the optional qrcode package.") from error
        output = Path.home() / "Pictures" / f"cleyxos-qr-{dt.datetime.now():%Y%m%d-%H%M%S}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        qrcode.make(" ".join(args)).save(output)
        console.print(f"[success]QR image saved: {output}[/success]")
    elif command in {"focus", "pomodoro"}:
        seconds = productivity.parse_duration(args[0]) if args else 25 * 60
        if command == "pomodoro":
            if args:
                raise ValueError("Usage: pomodoro")
            seconds = 25 * 60
        productivity.countdown(seconds)
    elif command == "dictionary":
        if len(args) != 1:
            raise ValueError("Usage: dictionary <word>")
        response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote_plus(args[0])}", timeout=8)
        if response.status_code == 404:
            raise LookupError(f"No dictionary entry found for '{args[0]}'.")
        response.raise_for_status()
        data = response.json()[0]
        meanings = data.get("meanings", [])
        definitions = [meaning["partOfSpeech"] + ": " + meaning["definitions"][0]["definition"] for meaning in meanings if meaning.get("definitions")]
        console.print(Panel("\n".join(definitions[:8]), title=data.get("word", args[0]), border_style="cyan"))
    elif command == "translate":
        if len(args) < 2:
            raise ValueError("Usage: translate <target-language> <text>; configure with config translate-url <https-url>")
        endpoint = get_config().get("translate_endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            raise ValueError("No translation provider configured. Use config translate-url <HTTPS endpoint>.")
        from urllib.parse import urlsplit
        endpoint_parts = urlsplit(endpoint)
        if not endpoint_parts.hostname or endpoint_parts.username or endpoint_parts.password:
            raise ValueError("Translation endpoint must be a valid HTTPS URL without embedded credentials.")
        response = requests.post(endpoint.rstrip("/") + "/translate", json={"q": " ".join(args[1:]), "source": "auto", "target": args[0], "format": "text"}, timeout=12)
        response.raise_for_status()
        console.print(response.json().get("translatedText", "Translation unavailable."), markup=False)
    elif command == "workspace":
        return _workspace(shell, args)
    elif command in {"tutorial", "examples", "commands", "searchcommand", "whatsnew", "tips", "shortcuts", "doctor", "version", "updatecheck"}:
        return _documentation(command, args)
    elif command == "searchpath":
        return _searchpath(shell, args)
    return True


def _convert(raw: str, source: str, target: str) -> str:
    value = float(raw)
    source, target = source.casefold(), target.casefold()
    tables = {
        "length": {"m": 1, "km": 1000, "cm": 0.01, "mi": 1609.344, "ft": 0.3048, "in": 0.0254},
        "weight": {"kg": 1, "g": .001, "lb": .45359237, "oz": .028349523125},
        "volume": {"l": 1, "ml": .001, "gal": 3.785411784},
    }
    for units in tables.values():
        if source in units and target in units:
            return f"{value:g} {source} = {value * units[source] / units[target]:g} {target}"
    if source in {"c", "f"} and target in {"c", "f"}:
        result = value if source == target else value * 9 / 5 + 32 if source == "c" else (value - 32) * 5 / 9
        return f"{value:g}°{source.upper()} = {result:g}°{target.upper()}"
    raise ValueError("Unsupported units. Length: m/km/cm/mi/ft/in; weight: kg/g/lb/oz; volume: l/ml/gal; temperature: c/f.")


def _workspace(shell, args: list[str]) -> bool:
    if not args:
        raise ValueError("Usage: workspace <create|addapp|addgame|addfolder|addurl|run|list|info|remove> ...")
    action = args[0].casefold()
    values = args[1:]
    if action == "create" and len(values) == 1:
        workspaces.create(values[0])
        console.print(f"[success]Workspace '{values[0]}' created.[/success]")
    elif action == "list" and not values:
        for name, steps in workspaces.list_workspaces().items():
            console.print(f"{name} ({len(steps)} actions)")
    elif action == "info" and len(values) == 1:
        for index, step in enumerate(workspaces.get(values[0]), 1):
            console.print(f"{index}. {step['type']}: {step['value']}")
    elif action == "remove" and len(values) == 1:
        if _confirm_windows(f"Remove workspace '{values[0]}'?", required="yes"):
            workspaces.remove(values[0])
            console.print("[success]Workspace removed.[/success]")
    elif action in {"addapp", "addgame", "addfolder", "addurl"} and len(values) >= 2:
        kind = {"addapp": "app", "addgame": "game", "addfolder": "folder", "addurl": "url"}[action]
        workspaces.add_step(values[0], kind, " ".join(values[1:]), cwd=shell.cwd)
        console.print(f"[success]Added {kind} to workspace '{values[0]}'.[/success]")
    elif action == "run" and len(values) == 1:
        steps = workspaces.get(values[0])
        if not steps:
            console.print("Workspace has no actions.")
            return True
        if not _confirm_windows(f"Run {len(steps)} workspace actions?", required="y"):
            console.print("[warning]Workspace cancelled.[/warning]")
            return True
        for step in steps:
            try:
                _run_workspace_step(step)
            except (OSError, ValueError, LookupError, requests.RequestException) as error:
                console.print(f"[error]{step['type']} {step['value']}: {error}[/error]")
    else:
        raise ValueError("Usage: workspace <create|addapp|addgame|addfolder|addurl|run|list|info|remove> ...")
    return True


def _run_workspace_step(step: dict[str, str]) -> None:
    kind, value = step["type"], step["value"]
    if kind == "folder":
        target = Path(value)
        if not target.is_dir():
            raise FileNotFoundError(target)
        os.startfile(str(target))
        console.print(f"[success]Opened folder {target}.[/success]")
    elif kind == "url":
        if not webbrowser.open(value, new=2):
            raise OSError("Could not open the workspace URL in the default browser.")
        console.print(f"[success]Opened website {value}.[/success]")
    elif kind == "app":
        matches = apps.find_apps(value)
        selected = application_services.choose_match(value, matches)
        if selected and application_services.confirm_launch(selected):
            application_services.launch_application(selected)
    elif kind == "game":
        matches = games.search_games(value)
        selected = application_services.choose_match(value, matches, kind="game")
        if selected and application_services.confirm_launch(selected, kind="game"):
            application_services.launch_game(selected)


def _searchpath(shell, args: list[str]) -> bool:
    config = get_config()
    paths = list(config.get("search_roots", [])) if isinstance(config.get("search_roots", []), list) else []
    if not args or args[0] == "list":
        console.print("\n".join(paths) if paths else "No extra search paths configured.")
    elif args[0] == "add" and len(args) >= 2:
        path = resolve_path(shell.cwd, " ".join(args[1:]))
        if not path.is_dir():
            raise NotADirectoryError(path)
        paths.append(str(path))
        config["search_roots"] = list(dict.fromkeys(paths))
        save_json(__import__("core.config", fromlist=["CONFIG_FILE"]).CONFIG_FILE, config)
        console.print(f"[success]Added search root {path}.[/success]")
    elif args[0] == "remove" and len(args) >= 2:
        query = " ".join(args[1:])
        paths = [path for path in paths if path.casefold() != query.casefold()]
        config["search_roots"] = paths
        save_json(__import__("core.config", fromlist=["CONFIG_FILE"]).CONFIG_FILE, config)
        console.print("[success]Search root removed.[/success]")
    else:
        raise ValueError("Usage: searchpath list|add <folder>|remove <folder>")
    return True


def _documentation(command: str, args: list[str]) -> bool:
    if command == "version":
        console.print("CleyxOS " + VERSION + " | Python " + platform.python_version() + " | " + platform.system())
    elif command == "whatsnew":
        console.print("CleyxOS 3.0 adds cached app/game discovery, media search, Windows controls, workspaces, and desktop productivity commands.")
    elif command == "tutorial":
        examples = {
            "launch": "launch discord  |  searchapp vscode  |  installed",
            "play": "games  |  findgame ultrakill  |  play ultrakill",
            "media": "video setfolder \"C:\\Users\\You\\Videos\"  |  watch sample  |  music list",
            "workspace": "workspace create coding  |  workspace addapp coding vscode  |  workspace run coding",
            "safety": "shutdown and restart always ask for confirmation; cleanup preview lists candidates before cleanup run.",
        }
        subject = args[0].casefold() if args else ""
        if subject:
            console.print(examples.get(subject, COMMANDS_V3.get(subject, "Use `help` or `commands` to browse commands.")))
        else:
            topics = ["launch", "play", "media", "workspace", "safety"]
            console.print("Interactive tutorial. Enter a topic name, or q to quit.")
            console.print("Topics: " + ", ".join(topics))
            from prompt_toolkit import PromptSession
            session: PromptSession[str] = PromptSession()
            while True:
                try:
                    choice = session.prompt("tutorial> ").strip().casefold()
                except (KeyboardInterrupt, EOFError):
                    break
                if choice in {"q", "quit", "exit"}:
                    break
                if choice in examples:
                    console.print(Panel(examples[choice], title=choice.title(), border_style="cyan"))
                else:
                    console.print("Choose one of: " + ", ".join(topics))
    elif command == "examples":
        if not args:
            raise ValueError("Usage: examples <command>")
        name = args[0].casefold()
        samples = {
            "launch": ["launch discord", "launch visual studio code"],
            "play": ['play "people playground"', "findgame ultrakill"],
            "workspace": ["workspace create coding", "workspace addapp coding vscode", "workspace addurl coding https://youtube.com", "workspace run coding"],
            "convert": ["convert 5 km mi", "convert 25 c f"],
            "volume": ["volume 40", "volume up 5", "mute"],
            "findfile": ["findfile report", "searchpath add C:\\Projects"],
        }
        console.print("\n".join(samples.get(name, [f"help {name}", f"tutorial {name}"])))
    elif command == "commands":
        table = Table(title="All CleyxOS commands", border_style="cyan")
        table.add_column("Command", style="white")
        table.add_column("Description", style="cyan")
        from core.commands import COMMANDS
        merged = {**COMMANDS, **COMMANDS_V3}
        for name, description in sorted(merged.items()):
            table.add_row(name, command_description(name, description))
        console.print(table)
    elif command == "searchcommand":
        query = " ".join(args).casefold()
        if not query:
            raise ValueError("Usage: searchcommand <query>")
        from core.commands import COMMANDS
        all_commands = {**COMMANDS, **COMMANDS_V3}
        matches = [(name, description) for name, description in all_commands.items() if query in name.casefold() or query in description.casefold()]
        for name, description in matches:
            console.print(f"{name}: {description}")
        if not matches:
            console.print("No matching commands.")
    elif command == "tips":
        console.print("Tip: quote paths with spaces. Add frequently used actions to a workspace. Run doctor for safe checks. Use searchpath add to limit file searches to your project folders.")
    elif command == "shortcuts":
        console.print("Tab: complete commands/subcommands/paths. Up/Down: command history. Ctrl+C: cancel interactive utilities. Quote multiword app/game names when needed.")
    elif command == "doctor":
        from core.config import APP_DIR
        checks = [
            ("Python", platform.python_version),
            ("Platform", platform.platform),
            ("Config directory", lambda: str(APP_DIR)),
            ("Config writable", lambda: os.access(APP_DIR, os.W_OK)),
            ("Virtual environment", lambda: sys.prefix != sys.base_prefix),
            ("CPU cores", psutil.cpu_count),
            ("Available RAM GiB", lambda: round(psutil.virtual_memory().available / 1024**3, 1)),
        ]
        for label, check in checks:
            try:
                result = check()
            except Exception as error:
                result = f"Unavailable ({type(error).__name__})"
            console.print(f"{label}: {result}", markup=False)
    elif command == "updatecheck":
        response = requests.get(f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest", timeout=8,
                                headers={"Accept": "application/vnd.github+json"})
        if response.status_code == 404:
            console.print("No GitHub release is published yet.")
        else:
            response.raise_for_status()
            release = response.json()
            tag = str(release.get("tag_name", "unknown"))
            latest = _version_tuple(tag)
            current = _version_tuple(VERSION)
            status = "Update available" if latest > current else "CleyxOS is up to date"
            console.print(f"{status}: current {VERSION}, latest {tag}")
            console.print(str(release.get("html_url", "")))
            console.print("Nothing was downloaded or installed.")
    return True


def _version_tuple(value: str) -> tuple[int, ...]:
    numbers = [int(item) for item in re.findall(r"\d+", value)[:4]]
    return tuple((numbers + [0, 0, 0, 0])[:4])


def _confirm_windows(prompt: str, *, required: str) -> bool:
    prompt = translate_message(prompt)
    confirmation = f"Onaylamak için '{required}' yazın: " if get_language() == "tr" else f"Type '{required}' to confirm: "
    answer = console.input(f"[bold yellow]{prompt} {confirmation}[/bold yellow]")
    return answer.strip().casefold() == required


def _arity(command: str, args: list[str], expected: int) -> None:
    if len(args) != expected:
        raise ValueError(f"Usage: {command}" + (" <arguments>" if expected else ""))
