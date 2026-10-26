"""Handlers for CleyxOS v2 system, file, network, and productivity commands."""

from __future__ import annotations

import getpass
import os
import shutil
import socket
import subprocess
import time
import webbrowser
from pathlib import Path

import psutil
from rich.panel import Panel
from rich.markup import escape
from rich.table import Table

from core import advanced_files, interactive, network, productivity, system
from core.filesystem import resolve_path
from core.i18n import translate, translate_message
from core.version import VERSION
from utils.terminal import console


SYSTEM_COMMANDS = {"whoami", "hostname", "disk", "ram", "cpu", "gpu", "battery", "top", "env", "which", "kill", "reboot-shell"}
FILE_COMMANDS = {"tree", "find", "grep", "head", "tail", "wc", "du", "df", "hash", "zip", "unzip", "edit", "backup", "restore"}
NETWORK_COMMANDS = {"ip", "publicip", "dns", "http", "download", "netstat", "speedtest"}
PRODUCTIVITY_COMMANDS = {"todo", "note", "timer", "stopwatch", "remind", "alias"}
SPECIAL_COMMANDS = {"matrix", "cleyx"}


def handles(command: str) -> bool:
    return command in (SYSTEM_COMMANDS | FILE_COMMANDS | NETWORK_COMMANDS | PRODUCTIVITY_COMMANDS | SPECIAL_COMMANDS)


def dispatch(shell, command: str, args: list[str]) -> bool:
    if command in SYSTEM_COMMANDS:
        return _system(shell, command, args)
    if command in FILE_COMMANDS:
        return _files(shell, command, args)
    if command in NETWORK_COMMANDS:
        return _network(shell, command, args)
    if command in PRODUCTIVITY_COMMANDS:
        return _productivity(shell, command, args)
    if command in SPECIAL_COMMANDS:
        return _special(command, args)
    return True


def _system(shell, command: str, args: list[str]) -> bool:
    if command == "whoami":
        _arity(command, args, 0)
        console.print(getpass.getuser())
    elif command == "hostname":
        _arity(command, args, 0)
        console.print(socket.gethostname())
    elif command == "disk":
        _arity(command, args, 0)
        console.print(system.disk_table())
    elif command == "ram":
        _arity(command, args, 0)
        memory = psutil.virtual_memory()
        console.print(Panel(f"Total: {system._bytes(memory.total)}\nAvailable: {system._bytes(memory.available)}\nUsed: {system._bytes(memory.used)} ({memory.percent:.1f}%)", title="RAM", border_style="cyan"))
    elif command == "cpu":
        _arity(command, args, 0)
        model, physical, logical, usage = system.cpu_info()
        console.print(Panel(f"Model: {model}\nPhysical cores: {physical}\nLogical cores: {logical}\nCurrent usage: {usage:.1f}%", title="CPU", border_style="cyan"))
    elif command == "gpu":
        _arity(command, args, 0)
        names = system.gpu_names()
        console.print("\n".join(f"• {name}" for name in names) if names else translate_message("No graphics adapter information available."))
    elif command == "battery":
        _arity(command, args, 0)
        console.print(system.battery_text())
    elif command == "top":
        refresh = 1.0
        sort_by = "cpu"
        if len(args) > 2:
            raise ValueError("Usage: top [refresh-seconds] [cpu|ram|name]")
        if args and args[0].casefold() in {"cpu", "ram", "name"}:
            sort_by = args[0].casefold()
        elif args:
            refresh = float(args[0])
        if len(args) == 2:
            sort_by = args[1].casefold()
        if sort_by not in {"cpu", "ram", "name"}:
            raise ValueError("Sort order must be cpu, ram, or name.")
        if args and args[0].casefold() not in {"cpu", "ram", "name"}:
            if not 0.25 <= refresh <= 5:
                raise ValueError("Refresh interval must be 0.25–5 seconds.")
        interactive.process_monitor(refresh, sort_by)
    elif command == "env":
        _arity(command, args, 0)
        table = Table(title="Environment Variables (sensitive values masked)", border_style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Value", style="cyan", overflow="fold")
        for name, value in system.safe_environment():
            table.add_row(name, value)
        console.print(table)
    elif command == "which":
        if len(args) != 1:
            raise ValueError("Usage: which <command>")
        path = shutil.which(args[0])
        if path:
            console.print(path)
        else:
            raise FileNotFoundError(f"Executable not found: {args[0]}")
    elif command == "kill":
        if len(args) != 1 or not args[0].isdigit():
            raise ValueError("Usage: kill <pid>")
        _kill_process(int(args[0]))
    elif command == "reboot-shell":
        _arity(command, args, 0)
        shell.restart_requested = True
        console.print(f"[success]{translate('restart_shell')}[/success]")
        return False
    return True


_PROTECTED_NAMES = {
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "winlogon.exe", "svchost.exe", "fontdrvhost.exe", "dwm.exe",
    "explorer.exe", "idle", "memory compression", "secure system",
}


def _kill_process(pid: int) -> None:
    try:
        process = psutil.Process(pid)
        name = process.name()
        username = process.username()
    except psutil.NoSuchProcess as error:
        raise ProcessLookupError(f"Process {pid} does not exist.") from error
    except psutil.AccessDenied as error:
        raise PermissionError("Access denied while inspecting that process.") from error
    protected_pids = {0, 4, os.getpid(), os.getppid()}
    current_parent = psutil.Process(os.getpid())
    while current_parent.pid > 0:
        protected_pids.add(current_parent.pid)
        try:
            current_parent = current_parent.parent()
            if current_parent is None:
                break
        except (psutil.Error, OSError):
            break
    if pid in protected_pids or name.casefold() in _PROTECTED_NAMES:
        raise PermissionError("Refusing to terminate a protected or CleyxOS process.")
    current_user = getpass.getuser().casefold()
    if username and username.split("\\")[-1].casefold() != current_user:
        raise PermissionError("You may only terminate processes owned by your current user.")
    console.print(f"Process details — PID: {pid} | Name: {name} | User: {username}")
    if not _confirm(f"Terminate process {name} ({pid})?", destructive=True):
        console.print(translate_message("[warning]Cancelled.[/warning]"))
        return
    try:
        process.terminate()
        process.wait(timeout=3)
        console.print(f"[success]Process {pid} terminated.[/success]")
    except psutil.AccessDenied as error:
        raise PermissionError("Windows denied permission to terminate that process.") from error
    except psutil.TimeoutExpired:
        raise TimeoutError("Process did not exit within 3 seconds; it was not force-killed.")


def _files(shell, command: str, args: list[str]) -> bool:
    cwd = shell.cwd
    if command == "tree":
        if len(args) > 1:
            raise ValueError("Usage: tree [path]")
        console.print(advanced_files.tree(resolve_path(cwd, args[0] if args else None)))
    elif command == "find":
        if not 1 <= len(args) <= 2:
            raise ValueError("Usage: find <filename> [directory]")
        results = advanced_files.find_matches(resolve_path(cwd, args[1] if len(args) == 2 else "."), args[0])
        if not results:
            console.print(translate_message("No matches found."))
        for result in results:
            console.print(result)
        if len(results) >= 500:
            console.print("[yellow]Result limit reached (500).[/yellow]")
    elif command == "grep":
        if len(args) != 2:
            raise ValueError("Usage: grep <text> <file>")
        path = resolve_path(cwd, args[1])
        matches = advanced_files.grep_file(path, args[0])
        for number, line in matches:
            console.print(f"{number}: {line}", markup=False)
        if not matches:
            console.print(translate_message("No matches found."))
    elif command in {"head", "tail"}:
        if not 1 <= len(args) <= 2:
            raise ValueError(f"Usage: {command} <file> [lines]")
        count = int(args[1]) if len(args) == 2 else 10
        if not 0 <= count <= 10000:
            raise ValueError("Line count must be between 0 and 10000.")
        lines = advanced_files.read_lines(resolve_path(cwd, args[0]))
        chosen = lines[:count] if command == "head" else lines[-count:] if count else []
        console.print("".join(chosen), end="")
    elif command == "wc":
        if len(args) != 1:
            raise ValueError("Usage: wc <file>")
        counts = advanced_files.word_character_counts(resolve_path(cwd, args[0]))
        console.print(f"Lines: {counts[0]}  Words: {counts[1]}  Characters: {counts[2]}")
    elif command == "du":
        if len(args) > 1:
            raise ValueError("Usage: du [path]")
        target = resolve_path(cwd, args[0] if args else None)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        console.print(f"{advanced_files._human_size(advanced_files.directory_size(target))}  {target}")
    elif command == "df":
        if args:
            raise ValueError("Usage: df")
        console.print(system.disk_table())
    elif command == "hash":
        if len(args) != 1:
            raise ValueError("Usage: hash <file>")
        target = resolve_path(cwd, args[0])
        console.print(f"SHA-256  {advanced_files.sha256_file(target)}  {target.name}")
    elif command == "zip":
        if len(args) < 2:
            raise ValueError("Usage: zip <archive.zip> <files...>")
        archive = resolve_path(cwd, args[0])
        if archive.suffix.casefold() != ".zip":
            raise ValueError("Archive filename must end in .zip.")
        advanced_files.create_zip(archive, [resolve_path(cwd, arg) for arg in args[1:]])
        console.print(f"[success]Created archive {archive}.[/success]")
    elif command in {"unzip", "restore"}:
        expected = "Usage: unzip <archive.zip> [destination]" if command == "unzip" else "Usage: restore <backup.zip> <destination>"
        minimum, maximum = (1, 2) if command == "unzip" else (2, 2)
        if not minimum <= len(args) <= maximum:
            raise ValueError(expected)
        archive = resolve_path(cwd, args[0])
        destination = resolve_path(cwd, args[1] if len(args) > 1 else ".")
        conflicts = advanced_files.zip_conflicts(archive, destination)
        overwrite = False
        if conflicts:
            console.print(f"[warning]{len(conflicts)} existing path(s) would be overwritten.[/warning]")
            overwrite = _confirm("Overwrite existing files?", destructive=True)
            if not overwrite:
                console.print(translate_message("[warning]Extraction cancelled.[/warning]"))
                return True
        extracted = advanced_files.extract_zip(archive, destination, overwrite=overwrite)
        console.print(f"[success]Extracted {len(extracted)} file(s) to {destination}.[/success]")
    elif command == "edit":
        if len(args) != 1:
            raise ValueError("Usage: edit <file>")
        advanced_files.open_in_editor(resolve_path(cwd, args[0]))
    elif command == "backup":
        if len(args) != 2:
            raise ValueError("Usage: backup <source> <destination.zip>")
        source, destination = (resolve_path(cwd, arg) for arg in args)
        productivity.backup(source, destination)
        console.print(translate_message(f"[success]Backup created: {destination}[/success]"))
    return True


def _network(shell, command: str, args: list[str]) -> bool:
    if command == "ip":
        _arity(command, args, 0)
        console.print(system.network_interfaces())
    elif command == "publicip":
        _arity(command, args, 0)
        console.print(network.public_ip())
    elif command == "dns":
        if not 1 <= len(args) <= 2:
            raise ValueError("Usage: dns <domain> [A|AAAA|MX|TXT|CNAME]")
        record_type = args[1].upper() if len(args) == 2 else "A"
        answers = network.dns_records(args[0], record_type)
        console.print(f"{record_type} records for {args[0]}:")
        console.print("\n".join(answers) if answers else "No records found.")
    elif command == "http":
        if len(args) != 1:
            raise ValueError("Usage: http <url>")
        status, elapsed, content_type, server, final_url = network.http_info(args[0])
        console.print(Panel(f"Status: {status}\nResponse time: {elapsed * 1000:.0f} ms\nContent-Type: {content_type}\nServer: {server}\nFinal URL: {final_url}", title="HTTP Response", border_style="cyan"))
    elif command == "download":
        if not 1 <= len(args) <= 2:
            raise ValueError("Usage: download <https-url> [destination]")
        url = network.validate_url(args[0], https_only=True)
        default_name = Path(url.split("?", 1)[0].rstrip("/")).name or "download.bin"
        destination = resolve_path(shell.cwd, args[1] if len(args) == 2 else default_name)
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        if not _confirm(f"Download {url} to {destination}? Downloaded files are never run automatically."):
            console.print(translate_message("[warning]Download cancelled.[/warning]"))
            return True
        count = network.download(url, destination)
        console.print(translate_message(f"[success]Downloaded {system._bytes(count)} to {destination}.[/success]"))
    elif command == "netstat":
        _arity(command, args, 0)
        console.print(system.connection_table())
    elif command == "speedtest":
        _arity(command, args, 0)
        if not _confirm("Run a bandwidth test (about 6 MiB of traffic)?"):
            console.print(translate_message("[warning]Speed test cancelled.[/warning]"))
            return True
        latency, download_mbps, upload_mbps = network.speed_test()
        console.print(Panel(f"Latency: {latency:.0f} ms\nDownload: {download_mbps:.2f} Mbps\nUpload: {upload_mbps:.2f} Mbps", title="Approximate Speed Test", border_style="cyan"))
    return True


def _productivity(shell, command: str, args: list[str]) -> bool:
    if command in {"todo", "note", "alias"}:
        if not args:
            raise ValueError(f"Usage: {command} <subcommand> ...")
        subcommand, values = args[0].casefold(), args[1:]
        if command == "todo":
            if subcommand == "add" and values:
                item = productivity.todo_add(" ".join(values))
                console.print(translate_message(f"[success]Added task #{item['id']}.[/success]"))
            elif subcommand == "list" and not values:
                table = Table(title="To-do", border_style="cyan")
                table.add_column("ID", justify="right")
                table.add_column("Status")
                table.add_column("Task")
                for item in productivity.todo_list():
                    table.add_row(str(item["id"]), "✓" if item["done"] else "○", str(item["text"]))
                console.print(table)
            elif subcommand in {"done", "remove"} and len(values) == 1:
                item_id = _id(values[0])
                if subcommand == "done":
                    productivity.todo_done(item_id)
                    console.print(translate_message(f"[success]Task #{item_id} completed.[/success]"))
                elif _confirm(f"Remove task #{item_id}?", destructive=True):
                    productivity.todo_remove(item_id)
                    console.print(translate_message("[success]Task removed.[/success]"))
                else:
                    console.print(translate_message("[warning]Cancelled.[/warning]"))
            elif subcommand == "clear" and not values:
                if _confirm("Remove all tasks?", destructive=True):
                    productivity.todo_clear()
                    console.print(translate_message("[success]Tasks cleared.[/success]"))
            else:
                raise ValueError("Usage: todo add <task> | list | done <id> | remove <id> | clear")
        elif command == "note":
            if subcommand == "add" and values:
                item = productivity.note_add(" ".join(values))
                console.print(translate_message(f"[success]Added note #{item['id']}.[/success]"))
            elif subcommand == "list" and not values:
                for item in productivity.note_list():
                    console.print(f"#{item['id']}  {item['text']}")
            elif subcommand == "read" and len(values) == 1:
                item = productivity.note_read(_id(values[0]))
                console.print(Panel(str(item["text"]), title=f"Note #{item['id']}", border_style="cyan"))
            elif subcommand == "remove" and len(values) == 1:
                item_id = _id(values[0])
                if _confirm(f"Remove note #{item_id}?", destructive=True):
                    productivity.note_remove(item_id)
                    console.print(translate_message("[success]Note removed.[/success]"))
            elif subcommand == "search" and values:
                results = productivity.note_search(" ".join(values))
                for item in results:
                    console.print(f"#{item['id']}  {item['text']}")
                if not results:
                    console.print(translate_message("No matching notes."))
            else:
                raise ValueError("Usage: note add <text> | list | read <id> | remove <id> | search <query>")
        else:
            if subcommand == "add" and len(values) >= 2:
                productivity.alias_add(values[0], " ".join(values[1:]))
                console.print(translate_message(f"[success]Alias '{values[0]}' saved.[/success]"))
            elif subcommand == "list" and not values:
                for name, target in productivity.aliases().items():
                    console.print(f"{name} → {target}")
            elif subcommand == "remove" and len(values) == 1:
                productivity.alias_remove(values[0])
                console.print(translate_message(f"[success]Alias '{values[0]}' removed.[/success]"))
            else:
                raise ValueError("Usage: alias add <name> <command> | list | remove <name>")
    elif command == "timer":
        if len(args) != 1:
            raise ValueError("Usage: timer <duration> (such as 30s, 5m, 1h)")
        seconds = productivity.parse_duration(args[0])
        console.print(f"[dim]{translate('timer_cancel')}[/dim]")
        productivity.countdown(seconds)
    elif command == "stopwatch":
        _arity(command, args, 0)
        interactive.stopwatch()
    elif command == "remind":
        if len(args) < 2:
            raise ValueError("Usage: remind <duration> <message>")
        seconds = productivity.parse_duration(args[0])
        shell.reminders.schedule(seconds, " ".join(args[1:]))
        console.print(translate_message(f"[success]Reminder scheduled in {args[0]}.[/success]"))
    return True


def _special(command: str, args: list[str]) -> bool:
    if command == "matrix":
        speed = float(args[0]) if args else 0.08
        if len(args) > 1 or not 0.03 <= speed <= 0.5:
            raise ValueError("Usage: matrix [speed 0.03–0.5 seconds]")
        interactive.matrix_rain(speed)
    else:
        _arity(command, args, 0)
        console.print(Panel(
            f"[bold cyan]CLEYXOS TERMINAL EDITION[/bold cyan]\n\nVersion: {VERSION}\nCreator: Cleyx\n"
            f"Platform: {__import__('platform').system()}\nLanguage: Python {__import__('platform').python_version()}\n"
            "Motto: MAY THE LAZY GET LAZIER.",
            title="C L E Y X O S", border_style="cyan"))
    return True


def _id(raw: str) -> int:
    if not raw.isdigit() or int(raw) <= 0:
        raise ValueError("ID must be a positive integer.")
    return int(raw)


def _arity(command: str, args: list[str], expected: int) -> None:
    if len(args) != expected:
        raise ValueError(f"Usage: {command}" + (" <arguments>" if expected else ""))


def _confirm(prompt: str, *, destructive: bool = False) -> bool:
    prompt = translate_message(prompt)
    label = f"{prompt} Type 'yes' to confirm: " if destructive else f"{prompt} [y/N]: "
    answer = console.input(f"[bold yellow]{label}[/bold yellow]").strip().casefold()
    return answer == ("yes" if destructive else "y")