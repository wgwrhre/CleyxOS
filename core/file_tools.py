"""User-scope file search and safe disk maintenance utilities."""

from __future__ import annotations

import hashlib
import heapq
import os
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from utils.terminal import console


def default_search_roots() -> list[Path]:
    home = Path.home()
    roots = [home / name for name in ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music")]
    if os.name == "nt":
        try:
            from core.windows_controls import known_folder_path
            roots.extend(known_folder_path(name) for name in ("desktop", "documents", "downloads", "pictures", "videos", "music"))
        except (OSError, ValueError):
            pass
    try:
        from core.config import get_config
        configured = get_config().get("search_roots", [])
        if isinstance(configured, list):
            roots.extend(Path(value).expanduser() for value in configured if isinstance(value, str))
    except (OSError, ValueError):
        pass
    return list(dict.fromkeys(path for path in roots if path.is_dir()))


def find_paths(name: str, *, directories_only: bool = False, files_only: bool = False,
               roots: list[Path] | None = None, limit: int = 500) -> list[Path]:
    if not name.strip():
        raise ValueError("Search name cannot be empty.")
    needle = name.casefold()
    found: list[Path] = []
    try:
        for root in roots or default_search_roots():
            if not root.is_dir():
                continue
            with Progress(SpinnerColumn(), TextColumn("Searching {task.description}"), console=console, transient=True) as progress:
                task = progress.add_task(str(root), total=None)
                try:
                    for folder, directories, filenames in os.walk(root, followlinks=False):
                        directories[:] = [item for item in directories if not (Path(folder) / item).is_symlink()]
                        entries = [] if files_only else directories
                        entries += [] if directories_only else filenames
                        for item in entries:
                            if needle in item.casefold():
                                found.append(Path(folder) / item)
                                if len(found) >= limit:
                                    return found
                except (PermissionError, OSError):
                    continue
                finally:
                    progress.update(task, completed=1)
    except KeyboardInterrupt:
        console.print("[dim]Search cancelled; showing results found so far.[/dim]")
    return found


def largest_files(root: Path, *, count: int = 20) -> list[tuple[int, Path]]:
    found: list[tuple[int, str, Path]] = []
    for folder, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if not (Path(folder) / name).is_symlink()]
        for filename in filenames:
            path = Path(folder) / filename
            try:
                size = path.stat().st_size
                entry = (size, str(path).casefold(), path)
                if len(found) < count:
                    heapq.heappush(found, entry)
                elif count and entry > found[0]:
                    heapq.heapreplace(found, entry)
            except (PermissionError, OSError):
                continue
    return [(size, path) for size, _, path in sorted(found, reverse=True)]


def duplicate_files(root: Path) -> list[list[Path]]:
    size_groups: dict[int, list[Path]] = defaultdict(list)
    for folder, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if not (Path(folder) / name).is_symlink()]
        for filename in filenames:
            path = Path(folder) / filename
            try:
                size_groups[path.stat().st_size].append(path)
            except (PermissionError, OSError):
                continue
    duplicates: dict[tuple[int, str], list[Path]] = defaultdict(list)
    for paths in size_groups.values():
        if len(paths) < 2:
            continue
        for path in paths:
            try:
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                duplicates[(path.stat().st_size, digest.hexdigest())].append(path)
            except (PermissionError, OSError):
                continue
    return [paths for paths in duplicates.values() if len(paths) > 1]


def empty_folders(root: Path) -> list[Path]:
    empty = []
    for folder, directories, filenames in os.walk(root, topdown=False, followlinks=False):
        path = Path(folder)
        try:
            if not any(path.iterdir()):
                empty.append(path)
        except (PermissionError, OSError):
            continue
    return empty


def cleanup_candidates(*, older_than_days: int = 7) -> list[Path]:
    temp_root = Path(tempfile.gettempdir()).resolve()
    cutoff = time.time() - older_than_days * 86400
    found = []
    try:
        entries = temp_root.iterdir()
    except OSError:
        return found
    for path in entries:
        try:
            if path.is_file() and not path.is_symlink() and path.suffix.casefold() in {".tmp", ".temp", ".log"} and path.stat().st_mtime < cutoff:
                found.append(path)
        except (PermissionError, OSError):
            continue
    return found


def remove_cleanup_candidates(paths: list[Path]) -> int:
    temp_root = Path(tempfile.gettempdir()).resolve()
    removed = 0
    for path in paths:
        resolved = path.resolve()
        if resolved.parent != temp_root or path.is_symlink():
            continue
        try:
            path.unlink()
            removed += 1
        except (PermissionError, OSError):
            continue
    return removed
