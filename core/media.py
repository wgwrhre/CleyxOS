"""Local media catalog using configured folders and the system's default player."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from core.config import get_config, save_json, CONFIG_FILE

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}


def folders(kind: str) -> list[Path]:
    config = get_config()
    saved = config.get(f"{kind}_folders")
    if isinstance(saved, list):
        values = [Path(item).expanduser() for item in saved if isinstance(item, str)]
    else:
        values = [Path.home() / ("Videos" if kind == "video" else "Music")]
    if os.name == "nt":
        try:
            from core.windows_controls import known_folder_path
            values.append(known_folder_path("videos" if kind == "video" else "music"))
        except (OSError, ValueError):
            pass
    fallback = Path(os.environ.get("USERPROFILE", Path.home())) / ("Videos" if kind == "video" else "Music")
    if fallback not in values:
        values.append(fallback)
    return list(dict.fromkeys(path for path in values if path.is_dir()))


def set_folder(kind: str, path: Path) -> None:
    if not path.is_dir():
        raise NotADirectoryError(f"Directory not found: {path}")
    config = get_config()
    config[f"{kind}_folders"] = [str(path)]
    save_json(CONFIG_FILE, config)


def find_media(query: str, kind: str, *, limit: int = 200) -> list[Path]:
    extensions = VIDEO_EXTENSIONS if kind == "video" else AUDIO_EXTENSIONS
    needle = query.casefold().strip()
    results: list[Path] = []
    for root in folders(kind):
        for current, directories, filenames in os.walk(root, followlinks=False):
            directories[:] = [name for name in directories if not (Path(current) / name).is_symlink()]
            for filename in filenames:
                path = Path(current) / filename
                if path.suffix.casefold() in extensions and (not needle or needle in path.stem.casefold()):
                    results.append(path)
                    if len(results) >= limit:
                        return results
    return results


def open_media(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Media file not found: {path}")
    if os.name == "nt":
        os.startfile(str(path))
    else:
        import webbrowser
        webbrowser.open(path.resolve().as_uri())


def open_youtube_search(query: str) -> None:
    if not query.strip():
        raise ValueError("Usage: youtube <query>")
    import webbrowser
    webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(query), new=2)


def open_spotify_search(query: str) -> None:
    if not query.strip():
        raise ValueError("Usage: spotify <query>")
    import webbrowser
    webbrowser.open("https://open.spotify.com/search/" + quote_plus(query), new=2)
