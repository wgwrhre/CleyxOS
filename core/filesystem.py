"""Conservative filesystem operations used by documented shell commands."""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.table import Table


def resolve_path(cwd: Path, raw: str | None) -> Path:
    """Resolve a user-supplied path relative to the current shell directory."""
    target = cwd if not raw else Path(raw).expanduser()
    return (target if target.is_absolute() else cwd / target).resolve()


def list_directory(path: Path) -> Table:
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    table = Table(title=str(path), border_style="cyan", header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="white")
    table.add_column("Size", justify="right")
    entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
    for entry in entries:
        kind = "Directory" if entry.is_dir() else "File"
        size = "—" if entry.is_dir() else _format_size(entry.stat().st_size)
        table.add_row(entry.name + ("/" if entry.is_dir() else ""), kind, size)
    return table


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def make_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def create_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)


def read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


def copy_path(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def move_path(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))


def delete_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()