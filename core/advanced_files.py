"""Extended file inspection, archives, and backup helpers."""

from __future__ import annotations

import hashlib
import os
import zipfile
import shutil
from pathlib import Path, PurePosixPath
from typing import Iterator

from rich.text import Text


def tree(path: Path, *, max_depth: int = 5, max_entries: int = 2000) -> Text:
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    output = Text(str(path) + "\n", style="bold cyan")
    visited = 0

    def walk(folder: Path, prefix: str, depth: int) -> None:
        nonlocal visited
        if depth >= max_depth:
            return
        try:
            entries = sorted(folder.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
        except (PermissionError, OSError):
            return
        for index, entry in enumerate(entries):
            visited += 1
            if visited > max_entries:
                output.append(f"{prefix}└── … (entry limit reached)\n", style="yellow")
                return
            last = index == len(entries) - 1
            output.append(f"{prefix}{'└── ' if last else '├── '}{entry.name}{'/' if entry.is_dir() else ''}\n")
            if entry.is_dir() and not entry.is_symlink():
                walk(entry, prefix + ("    " if last else "│   "), depth + 1)

    walk(path, "", 0)
    return output


def find_matches(root: Path, query: str, *, limit: int = 500) -> list[Path]:
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")
    needle = query.casefold()
    matches: list[Path] = []
    for folder, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if not (Path(folder) / name).is_symlink()]
        for name in [*directories, *filenames]:
            if needle in name.casefold():
                matches.append(Path(folder) / name)
                if len(matches) >= limit:
                    return matches
    return matches


def grep_file(path: Path, query: str) -> list[tuple[int, str]]:
    matches = []
    needle = query.casefold()
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for number, line in enumerate(stream, 1):
            if needle in line.casefold():
                matches.append((number, line.rstrip("\r\n")))
    return matches


def read_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        return stream.readlines()


def word_character_counts(path: Path) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0), len(text.split()), len(text)


def directory_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for folder, directories, filenames in os.walk(path, followlinks=False):
        directories[:] = [name for name in directories if not (Path(folder) / name).is_symlink()]
        for filename in filenames:
            try:
                total += (Path(folder) / filename).stat().st_size
            except (PermissionError, OSError):
                continue
    return total


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_zip(archive: Path, paths: list[Path]) -> None:
    if not paths:
        raise ValueError("Provide at least one file or directory to archive.")
    if archive.exists():
        raise FileExistsError(f"Archive already exists: {archive}")
    archive_real = archive.resolve()
    for source in paths:
        if source.is_symlink():
            raise ValueError(f"Refusing to archive a symbolic link: {source}")
        if source.is_dir() and archive_real.is_relative_to(source.resolve()):
            raise ValueError("Archive destination cannot be inside a directory being archived.")
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in paths:
                if not path.exists():
                    raise FileNotFoundError(path)
                if path.is_dir():
                    for folder, directories, filenames in os.walk(path, followlinks=False):
                        directories[:] = [name for name in directories if not (Path(folder) / name).is_symlink()]
                        for filename in filenames:
                            item = Path(folder) / filename
                            if item.is_symlink():
                                continue
                            bundle.write(item, item.relative_to(path.parent))
                else:
                    bundle.write(path, path.name)
    except Exception:
        archive.unlink(missing_ok=True)
        raise


def _safe_member_path(destination: Path, member: str) -> Path:
    pure = PurePosixPath(member)
    if pure.is_absolute() or ".." in pure.parts or "\\" in member or any(part.endswith(":") for part in pure.parts):
        raise ValueError(f"Unsafe archive path rejected: {member}")
    target = (destination / Path(*pure.parts)).resolve()
    base = destination.resolve()
    try:
        target.relative_to(base)
    except ValueError as error:
        raise ValueError(f"Unsafe archive path rejected: {member}") from error
    current = base
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Archive would traverse a symbolic link: {current}")
    return target


def zip_conflicts(archive: Path, destination: Path) -> list[Path]:
    conflicts = []
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = _safe_member_path(destination, member.filename)
            if target.exists():
                conflicts.append(target)
    return conflicts


def extract_zip(archive: Path, destination: Path, *, overwrite: bool = False) -> list[Path]:
    extracted = []
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.infolist()) > 10000:
            raise ValueError("Archive contains too many entries (maximum 10,000).")
        if sum(member.file_size for member in bundle.infolist()) > 2 * 1024 ** 3:
            raise ValueError("Archive exceeds the 2 GiB expanded-size safety limit.")
        members = [(member, _safe_member_path(destination, member.filename)) for member in bundle.infolist()]
        member_paths = [str(target).casefold() for _, target in members]
        if len(member_paths) != len(set(member_paths)):
            raise ValueError("Archive contains duplicate or colliding paths.")
        if not overwrite:
            conflicts = [target for member, target in members if target.exists()]
            if conflicts:
                raise FileExistsError(f"Extraction would overwrite existing paths: {', '.join(map(str, conflicts[:5]))}")
        base = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        for member, target in members:
            # Create each directory component while refusing symlinks that could redirect writes.
            current = target
            missing = []
            while current != base and not current.exists():
                missing.append(current)
                current = current.parent
            if current != base and (current.is_symlink() or not current.resolve().is_relative_to(base)):
                raise ValueError(f"Unsafe extraction parent: {current}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                raise ValueError(f"Refusing to overwrite a symbolic link: {target}")
            with bundle.open(member) as source, target.open("wb" if overwrite else "xb") as output:
                shutil.copyfileobj(source, output)
            extracted.append(target)
    return extracted


def open_in_editor(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if os.name == "nt":
        os.startfile(str(path))
    else:
        import webbrowser
        webbrowser.open(path.resolve().as_uri())


def iter_files(path: Path) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    for folder, directories, filenames in os.walk(path, followlinks=False):
        directories[:] = [name for name in directories if not (Path(folder) / name).is_symlink()]
        for filename in filenames:
            yield Path(folder) / filename