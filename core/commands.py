"""Documented CleyxOS command implementations."""

from __future__ import annotations

import ast
import difflib
import math
import platform
import re
import socket
import subprocess
import time
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import psutil
import requests
from rich.panel import Panel
from rich.markup import escape
from rich.table import Table

from core import apps, filesystem, system
from core.config import get_config, set_language, set_prompt
from core import extended_commands, productivity, v3_commands
from core.i18n import SUPPORTED_LANGUAGES, command_description, get_language, translate, translate_message
from utils.terminal import console

COMMANDS: dict[str, str] = {
    "help": "Show available commands",
    "clear": "Clear the terminal",
    "sysinfo": "Show CPU, RAM, GPU, OS, and Python details",
    "neofetch": "Show CleyxOS branding and system information",
    "uptime": "Show this session's uptime",
    "processes": "List running processes",
    "performance": "Show current CPU and RAM usage",
    "exit": "Shut down CleyxOS",
    "ls": "List files and directories",
    "cd": "Change the current directory",
    "pwd": "Print the current directory",
    "mkdir": "Create a directory",
    "touch": "Create an empty file",
    "cat": "Read a UTF-8 text file",
    "cp": "Copy a file or directory",
    "mv": "Move a file or directory",
    "rm": "Delete a path after confirmation",
    "time": "Show the current local time",
    "date": "Show the current local date",
    "calc": "Evaluate a safe arithmetic expression",
    "history": "Show saved command history",
    "echo": "Print text",
    "ping": "Test connectivity to a host",
    "weather": "Show current weather for a city",
    "open": "Open a website in the default browser",
    "language": "Choose the interface language (en/tr)",
    "apps": "List registered applications",
    "app add": "Register a Python script or Windows executable",
    "app run": "Launch a registered application",
    "app remove": "Remove an application registration",
    "app info": "Show application registration details",
    "config show": "Show persistent shell configuration",
    "config prompt": "Set the shell prompt text",
    "config language": "Choose the interface language (en/tr)",
    "config translate-url": "Configure the HTTPS translation provider endpoint",
    "whoami": "Display the current Windows username",
    "hostname": "Display the computer hostname",
    "disk": "Show drive capacity and usage",
    "ram": "Show physical memory usage",
    "cpu": "Show processor details and usage",
    "gpu": "List detected graphics adapters",
    "battery": "Show battery status",
    "top": "Interactive live process monitor (Q to exit)",
    "env": "List environment variables with sensitive values masked",
    "which": "Find an executable on PATH",
    "kill": "Confirm and terminate a user-owned process",
    "reboot-shell": "Restart CleyxOS without restarting Windows",
    "tree": "Display a directory tree",
    "find": "Find matching file or directory names",
    "grep": "Search text in a file",
    "head": "Show the first lines of a file",
    "tail": "Show the last lines of a file",
    "wc": "Count lines, words, and characters",
    "du": "Calculate file or directory size",
    "df": "Show filesystem storage information",
    "hash": "Calculate a file's SHA-256 checksum",
    "zip": "Create a ZIP archive",
    "unzip": "Safely extract a ZIP archive",
    "edit": "Open a file in the system editor",
    "backup": "Create a ZIP backup of a file or directory",
    "restore": "Safely restore a ZIP backup",
    "ip": "List local network interface addresses",
    "publicip": "Retrieve the public IP over HTTPS",
    "dns": "Look up A, AAAA, MX, TXT, or CNAME records",
    "http": "Inspect an HTTP response without downloading its body",
    "download": "Confirm and download a file over HTTPS",
    "netstat": "List network connections and process IDs",
    "speedtest": "Run a confirmed approximate bandwidth test",
    "todo add": "Add a persistent task",
    "todo list": "List tasks",
    "todo done": "Mark a task complete",
    "todo remove": "Remove a task with confirmation",
    "todo clear": "Clear tasks with confirmation",
    "note add": "Save a persistent note",
    "note list": "List notes",
    "note read": "Read a note by ID",
    "note remove": "Remove a note with confirmation",
    "note search": "Search saved notes",
    "timer": "Run a countdown timer",
    "stopwatch": "Interactive stopwatch controls",
    "remind": "Schedule a reminder while CleyxOS runs",
    "alias add": "Create a safe built-in command alias",
    "alias list": "List command aliases",
    "alias remove": "Remove a command alias",
    "todo": "Manage persistent tasks",
    "note": "Manage persistent notes",
    "alias": "Manage safe command aliases",
    "matrix": "Show animated Matrix digital rain (Q to exit)",
    "cleyx": "Show CleyxOS version and platform information",
    **v3_commands.COMMANDS_V3,
}


def _evaluate(expression: str) -> int | float:
    """Evaluate arithmetic with a strict AST allowlist; never calls eval()."""
    if len(expression) > 240:
        raise ValueError("Expression is too long (maximum 240 characters).")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError("Enter a valid arithmetic expression.") from error
    binary_ops: dict[type[ast.operator], Callable[[int | float, int | float], int | float]] = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
    }
    unary_ops: dict[type[ast.unaryop], Callable[[int | float], int | float]] = {
        ast.UAdd: lambda a: a,
        ast.USub: lambda a: -a,
    }
    functions: dict[str, Callable[..., int | float]] = {
        "abs": abs, "round": round, "sqrt": math.sqrt,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log,
    }
    constants = {"pi": math.pi, "e": math.e}

    def visit(node: ast.AST, depth: int = 0) -> int | float:
        if depth > 30:
            raise ValueError("Expression is too deeply nested.")
        if isinstance(node, ast.Expression):
            return visit(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            result: int | float = node.value
        elif isinstance(node, ast.Name) and node.id in constants:
            result = constants[node.id]
        elif isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
            left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent magnitude cannot exceed 100.")
            result = binary_ops[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp) and type(node.op) in unary_ops:
            result = unary_ops[type(node.op)](visit(node.operand, depth + 1))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and not node.keywords:
            result = functions[node.func.id](*(visit(arg, depth + 1) for arg in node.args))
        else:
            raise ValueError("Only arithmetic, pi/e, and safe math functions are allowed.")
        if isinstance(result, int) and result.bit_length() > 4096:
            raise ValueError("Result is too large.")
        if isinstance(result, float) and not math.isfinite(result):
            raise ValueError("Result is not finite.")
        return result

    return visit(tree)


def _usage(command: str, text: str) -> None:
    raise ValueError(f"Usage: {command} {text}")


class CommandProcessor:
    """Dispatch and execute only the built-in CleyxOS commands."""

    def __init__(self, shell: object) -> None:
        self.shell = shell
        self.started_at = time.monotonic()

    def execute(self, raw: str) -> bool:
        """Run a line; return False when the shell should stop."""
        import shlex

        try:
            windows_tokens = platform.system() == "Windows"
            tokens = shlex.split(raw, posix=not windows_tokens)
            if windows_tokens:
                tokens = [token[1:-1] if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'" else token
                          for token in tokens]
        except ValueError as error:
            console.print(f"[error]Could not parse command: {error}[/error]")
            return True
        if not tokens:
            return True
        command = tokens[0].casefold()
        args = tokens[1:]
        try:
            if command == "app":
                if not args:
                    _usage("app", "<add|run|remove|info> ...")
                return self._app(args[0].casefold(), args[1:])
            if command == "config":
                if not args:
                    _usage("config", "<show|prompt|language|translate-url> [value]")
                return self._config(args[0].casefold(), args[1:])
            if command == "language":
                return self.cmd_language(args)
            if v3_commands.handles(command):
                try:
                    return v3_commands.dispatch(self.shell, command, args)
                except (psutil.Error, requests.RequestException) as error:
                    console.print(f"[error]{escape(translate_message(str(error)))}[/error]")
                    return True
            if extended_commands.handles(command):
                try:
                    return extended_commands.dispatch(self.shell, command, args)
                except (psutil.Error, zipfile.BadZipFile) as error:
                    console.print(f"[error]{escape(translate_message(str(error)))}[/error]")
                    return True
            # Aliases are expanded only to documented built-in commands, never a platform shell.
            visited: set[str] = set()
            for _ in range(8):
                alias = productivity.aliases().get(command)
                if alias is None:
                    break
                if command in visited:
                    raise ValueError("Alias cycle detected; remove or redefine the recursive alias.")
                visited.add(command)
                alias_tokens = shlex.split(alias, posix=not windows_tokens)
                if windows_tokens:
                    alias_tokens = [token[1:-1] if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'" else token
                                    for token in alias_tokens]
                if not alias_tokens:
                    raise ValueError("Alias has an empty command.")
                tokens = alias_tokens + args
                command, args = tokens[0].casefold(), tokens[1:]
                if command in {"app", "config", "language"}:
                    raise ValueError("Aliases may not expand to app/config management commands.")
            else:
                raise ValueError("Alias expansion limit reached; possible recursive alias.")
            if v3_commands.handles(command):
                return v3_commands.dispatch(self.shell, command, args)
            if extended_commands.handles(command):
                return extended_commands.dispatch(self.shell, command, args)
            handler = getattr(self, f"cmd_{command}", None)
            if handler is None:
                self._unknown(command)
                return True
            return handler(args)
        except (OSError, ValueError, LookupError, TypeError, ArithmeticError, RuntimeError,
            zipfile.BadZipFile,
            requests.RequestException, subprocess.SubprocessError) as error:
            console.print(f"[error]{escape(translate_message(str(error)))}[/error]")
            return True
        except Exception as error:
            message = translate_message(str(error)) or type(error).__name__
            console.print(f"[error]Command failed safely: {escape(message)}[/error]")
            return True

    def _unknown(self, command: str) -> None:
        match = difflib.get_close_matches(command, COMMANDS, n=1, cutoff=0.58)
        suggestion = f" Did you mean '{match[0]}'?" if match else " Type 'help' to see available commands."
        console.print(f"[error]Unknown command: {command}.[/error]{suggestion}")

    def cmd_help(self, args: list[str]) -> bool:
        table = Table(title=translate("help_title"), border_style="cyan", header_style="bold cyan")
        table.add_column("Command", style="white", no_wrap=True)
        table.add_column(translate("help_column"), style="cyan")
        for name, description in COMMANDS.items():
            table.add_row(name, command_description(name, description))
        console.print(table)
        console.print(f"[dim]{translate('help_hint')}[/dim]")
        return True

    def cmd_clear(self, args: list[str]) -> bool:
        console.clear()
        return True

    def cmd_sysinfo(self, args: list[str]) -> bool:
        console.print(system.system_table())
        return True

    def cmd_neofetch(self, args: list[str]) -> bool:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="white")
        table.add_row("CLEYXOS", "Terminal Edition v1.0")
        for label, value in system.system_rows():
            table.add_row(label, value)
        console.print(Panel(table, title="[bold cyan]C L E Y X O S[/bold cyan]", border_style="cyan"))
        return True

    def cmd_uptime(self, args: list[str]) -> bool:
        console.print(f"CleyxOS session uptime: [cyan]{system.uptime_text(self.started_at)}[/cyan]")
        return True

    def cmd_processes(self, args: list[str]) -> bool:
        console.print(system.process_table())
        return True

    def cmd_performance(self, args: list[str]) -> bool:
        console.print(system.performance_table())
        return True

    def cmd_exit(self, args: list[str]) -> bool:
        console.print("[bold red]Shutting down CleyxOS. See you soon.[/bold red]")
        return False

    def cmd_pwd(self, args: list[str]) -> bool:
        console.print(str(self.shell.cwd))
        return True

    def cmd_ls(self, args: list[str]) -> bool:
        if len(args) > 1:
            _usage("ls", "[path]")
        console.print(filesystem.list_directory(filesystem.resolve_path(self.shell.cwd, args[0] if args else None)))
        return True

    def cmd_cd(self, args: list[str]) -> bool:
        if len(args) > 1:
            _usage("cd", "[path]")
        target = filesystem.resolve_path(self.shell.cwd, args[0] if args else str(Path.home()))
        if not target.is_dir():
            raise NotADirectoryError(f"Directory not found: {target}")
        self.shell.cwd = target
        return True

    def cmd_mkdir(self, args: list[str]) -> bool:
        if len(args) != 1:
            _usage("mkdir", "<directory>")
        filesystem.make_directory(filesystem.resolve_path(self.shell.cwd, args[0]))
        console.print("[success]Directory created.[/success]")
        return True

    def cmd_touch(self, args: list[str]) -> bool:
        if len(args) != 1:
            _usage("touch", "<file>")
        filesystem.create_file(filesystem.resolve_path(self.shell.cwd, args[0]))
        console.print("[success]File created (or already exists).[/success]")
        return True

    def cmd_cat(self, args: list[str]) -> bool:
        if len(args) != 1:
            _usage("cat", "<file>")
        console.print(filesystem.read_text(filesystem.resolve_path(self.shell.cwd, args[0])), end="")
        return True

    def cmd_cp(self, args: list[str]) -> bool:
        if len(args) != 2:
            _usage("cp", "<source> <destination>")
        filesystem.copy_path(*(filesystem.resolve_path(self.shell.cwd, item) for item in args))
        console.print("[success]Copied.[/success]")
        return True

    def cmd_mv(self, args: list[str]) -> bool:
        if len(args) != 2:
            _usage("mv", "<source> <destination>")
        filesystem.move_path(*(filesystem.resolve_path(self.shell.cwd, item) for item in args))
        console.print("[success]Moved.[/success]")
        return True

    def cmd_rm(self, args: list[str]) -> bool:
        if len(args) != 1:
            _usage("rm", "<path>")
        target = filesystem.resolve_path(self.shell.cwd, args[0])
        if target == Path(target.anchor):
            raise ValueError("Refusing to remove a filesystem root.")
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        answer = console.input(f"[bold red]Delete {target}? This cannot be undone. Type 'yes' to confirm: [/bold red]")
        if answer.casefold() == "yes":
            filesystem.delete_path(target)
            console.print("[success]Deleted.[/success]")
        else:
            console.print("[warning]Deletion cancelled.[/warning]")
        return True

    def cmd_time(self, args: list[str]) -> bool:
        console.print(datetime.now().astimezone().strftime("%H:%M:%S %Z"))
        return True

    def cmd_date(self, args: list[str]) -> bool:
        console.print(datetime.now().astimezone().strftime("%A, %B %d, %Y"))
        return True

    def cmd_calc(self, args: list[str]) -> bool:
        expression = " ".join(args)
        if not expression:
            _usage("calc", "<expression>")
        console.print(f"[cyan]{_evaluate(expression)}[/cyan]")
        return True

    def cmd_history(self, args: list[str]) -> bool:
        history = self.shell.history.get_strings()
        if not history:
            console.print("[dim]No commands in history yet.[/dim]")
        else:
            for index, line in enumerate(history[-100:], 1):
                console.print(f"[dim]{index:>3}[/dim]  {line}")
        return True

    def cmd_echo(self, args: list[str]) -> bool:
        console.print(" ".join(args), markup=False)
        return True

    def cmd_language(self, args: list[str]) -> bool:
        if not args:
            console.print(translate("language_current", language=SUPPORTED_LANGUAGES[get_language()]))
            return True
        if len(args) != 1 or args[0].casefold() not in SUPPORTED_LANGUAGES:
            raise ValueError(translate("language_usage"))
        selected = args[0].casefold()
        set_language(selected)
        console.print(translate("language_set", language=SUPPORTED_LANGUAGES[selected]))
        return True

    def cmd_open(self, args: list[str]) -> bool:
        if len(args) != 1:
            raise ValueError(translate("website_usage"))
        address = args[0].strip()
        if not address.startswith(("https://", "http://")):
            address = "https://" + address
        parsed = urlsplit(address)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or any(char.isspace() for char in address)):
            raise ValueError(translate("website_invalid"))
        if not webbrowser.open(address, new=2):
            raise OSError("Could not open the default browser.")
        console.print(translate("website_opened", url=address))
        return True

    def cmd_ping(self, args: list[str]) -> bool:
        if len(args) != 1:
            _usage("ping", "<host>")
        host = args[0]
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,253}", host):
            raise ValueError("Enter a valid hostname or IP address.")
        socket.getaddrinfo(host, None)
        count_flag = "-n" if platform.system() == "Windows" else "-c"
        result = subprocess.run(["ping", count_flag, "1", host], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=8, check=False)
        output = (result.stdout or "").strip() or (result.stderr or "").strip() or "No response."
        console.print(output, style="green" if result.returncode == 0 else "yellow", markup=False)
        return True

    def cmd_weather(self, args: list[str]) -> bool:
        city = " ".join(args).strip()
        if not city:
            _usage("weather", "<city>")
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                           params={"name": city, "count": 1, "language": "en", "format": "json"}, timeout=8)
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            raise ValueError(f"No location found for '{city}'.")
        place = results[0]
        weather = requests.get("https://api.open-meteo.com/v1/forecast",
                               params={"latitude": place["latitude"], "longitude": place["longitude"],
                                       "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"},
                               timeout=8)
        weather.raise_for_status()
        current = weather.json().get("current", {})
        console.print(Panel(
            f"[bold white]{place['name']}, {place.get('country', '')}[/bold white]\n"
            f"Temperature: [cyan]{current.get('temperature_2m', '—')} °C[/cyan]\n"
            f"Feels like: {current.get('apparent_temperature', '—')} °C\n"
            f"Humidity: {current.get('relative_humidity_2m', '—')}%\n"
            f"Wind: {current.get('wind_speed_10m', '—')} km/h\n"
            f"Weather code: {current.get('weather_code', '—')} (WMO)",
            title="[bold cyan]Current Weather[/bold cyan]", border_style="cyan"))
        return True

    def cmd_apps(self, args: list[str]) -> bool:
        registered = apps.list_apps()
        if not registered:
            console.print("[dim]No applications registered. Use 'app add'.[/dim]")
            return True
        table = Table(title="Registered Applications", border_style="cyan", header_style="bold cyan")
        table.add_column("Name", style="white")
        table.add_column("Path", style="cyan")
        table.add_column("Description")
        for name, data in sorted(registered.items()):
            table.add_row(name, data.get("path", ""), data.get("description", ""))
        console.print(table)
        return True

    def _app(self, action: str, args: list[str]) -> bool:
        if action == "add":
            if len(args) < 2:
                _usage("app add", "<name> <path> [description]")
            app_path = filesystem.resolve_path(self.shell.cwd, args[1])
            item = apps.add_app(args[0], str(app_path), " ".join(args[2:]))
            console.print(f"[success]Registered {args[0]}: {item['path']}[/success]")
        elif action == "run":
            if not args:
                _usage("app run", "<application name> [-- arguments ...]")
            if "--" in args:
                separator = args.index("--")
                query, launch_args = " ".join(args[:separator]), args[separator + 1:]
            else:
                query, launch_args = " ".join(args), []
            selected = self._select_app(query, apps.find_apps(query))
            process = apps.launch_app(selected["name"], launch_args, resolved=selected)
            from core.application_services import record_launch
            record_launch(selected["name"], "app")
            pid_text = f" (PID {process.pid})" if process is not None else ""
            console.print(f"[success]Launched {selected['name']}{pid_text}.[/success]")
        elif action == "remove":
            if not args:
                _usage("app remove", "<name>")
            query = " ".join(args)
            registered_matches = [item for item in apps.find_apps(query) if item.get("source") == "registered"]
            if registered_matches:
                top_score = registered_matches[0].get("_score")
                tied = [item for item in registered_matches if item.get("_score") == top_score]
                if len(tied) > 1:
                    console.print(translate("app_ambiguous", query=query))
                    for item in tied:
                        console.print(f"  • {item['name']}")
                    raise ValueError("Refine the application name and try again.")
                registered_name = registered_matches[0]["name"]
                apps.remove_app(registered_name)
                console.print(f"[success]{translate('app_removed', name=registered_name)}[/success]")
            else:
                if apps.find_apps(query):
                    raise ValueError(translate("app_not_registered", name=query))
                raise KeyError(translate("app_not_found", query=query))
        elif action == "info":
            if not args:
                _usage("app info", "<name>")
            self._show_app_info(" ".join(args))
        else:
            _usage("app", "<add|run|remove|info> ...")
        return True

    def _show_app_info(self, query: str) -> None:
        selected = self._select_app(query, apps.find_apps(query))
        details = [f"[bold]{selected['name']}[/bold]", f"Path: {selected.get('path') or 'Unavailable'}"]
        for key, label in (("version", "Version"), ("publisher", "Publisher"), ("description", "Description")):
            if selected.get(key):
                details.append(f"{label}: {selected[key]}")
        details.append(f"Source: {selected.get('source', 'registered')}")
        console.print(Panel("\n".join(details), border_style="cyan", title="Application"))

    @staticmethod
    def _select_app(query: str, matches: list[dict[str, str]]) -> dict[str, str]:
        if not matches:
            raise KeyError(translate("app_not_found", query=query))
        if len(matches) > 1 and matches[0].get("_score") == matches[1].get("_score"):
            console.print(translate("app_ambiguous", query=query))
            for match in matches[:8]:
                console.print(f"  • {match['name']} — {match.get('path') or 'path unavailable'}")
            raise ValueError("Refine the application name and try again.")
        return matches[0]

    def _config(self, action: str, args: list[str]) -> bool:
        if action == "show":
            if args:
                _usage("config show", "")
            console.print_json(data=get_config())
        elif action == "prompt":
            if not args:
                _usage("config prompt", "<prompt text>")
            prompt = " ".join(args)
            if len(prompt) > 100:
                raise ValueError("Prompt must be 100 characters or fewer.")
            set_prompt(prompt)
            console.print("[success]Prompt saved. Available variables: {cwd}, {home}.[/success]")
        elif action == "language":
            return self.cmd_language(args)
        elif action == "translate-url":
            if len(args) != 1 or not args[0].startswith("https://"):
                _usage("config translate-url", "<https-endpoint>")
            endpoint = urlsplit(args[0])
            if not endpoint.hostname or endpoint.username or endpoint.password or any(char.isspace() for char in args[0]):
                raise ValueError("Translation endpoint must be a valid HTTPS URL without embedded credentials.")
            config = get_config()
            config["translate_endpoint"] = args[0].rstrip("/")
            from core.config import save_json, CONFIG_FILE
            save_json(CONFIG_FILE, config)
            console.print("[success]Translation endpoint saved.[/success]")
        else:
            _usage("config", "<show|prompt|language|translate-url> [value]")
        return True