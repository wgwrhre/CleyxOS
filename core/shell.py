"""Interactive prompt-toolkit shell with persistent history and completion."""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from collections.abc import Callable, Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexer import RegexLexer
from pygments.token import Comment, Keyword, Name, Number, Operator, String, Text
from rich.markup import escape

from core.commands import COMMANDS, CommandProcessor
from core.config import HISTORY_FILE, ensure_app_dir, get_config
from core.i18n import translate
from core.productivity import ReminderScheduler
from utils.terminal import console


class CleyxCompleter(Completer):
    def __init__(self, cwd_provider: Callable[[], Path] = Path.cwd) -> None:
        self._cwd_provider = cwd_provider

    def get_completions(self, document, complete_event):
        before = document.text_before_cursor
        words = before.split()
        trailing_space = bool(before) and before[-1].isspace()
        word = "" if trailing_space else (before.rsplit(None, 1)[-1] if before.strip() else "")
        prefix = words if trailing_space else words[:-1]
        if not prefix:
            root_commands = {candidate for candidate in COMMANDS if " " not in candidate}
            for candidate in sorted(root_commands):
                if candidate.casefold().startswith(word.casefold()):
                    yield Completion(candidate, start_position=-len(word))
            return

        command = prefix[0].casefold()
        subcommands = {
            "app": ("add", "run", "remove", "info"),
            "config": ("show", "prompt", "language", "translate-url"),
            "todo": ("add", "list", "done", "remove", "clear"),
            "note": ("add", "list", "read", "remove", "search"),
            "alias": ("add", "list", "remove"),
            "favoriteapp": ("add", "list", "remove"),
            "favoritegame": ("add", "list", "remove"),
            "video": ("info", "recent", "setfolder"),
            "cleanup": ("preview", "run"),
            "searchpath": ("list", "add", "remove"),
            "clipboard": ("copy", "show", "clear"),
            "volume": ("up", "down"),
            "brightness": ("up", "down"),
            "settings": ("sound", "display", "network", "bluetooth", "storage", "applications", "updates", "personalization", "privacy", "power"),
            "workspace": ("create", "addapp", "addgame", "addfolder", "addurl", "run", "list", "info", "remove"),
        }
        if len(prefix) == 1:
            registered_subcommands = {
                entry[len(command) + 1:].split()[0]
                for entry in COMMANDS
                if entry.startswith(command + " ")
            }
            options = set(subcommands.get(command, ())) | registered_subcommands
            for option in sorted(options):
                if option.startswith(word.casefold()):
                    yield Completion(option, start_position=-len(word))
            if options:
                return
        if command in {"launch", "openapp", "searchapp", "appinfo", "appfolder", "closeapp", "favoriteapp"}:
            from core.apps import cached_apps
            argument_index = 2 if command == "favoriteapp" and len(prefix) >= 2 and prefix[1].casefold() == "add" else 1
            name_prefix = " ".join(prefix[argument_index:] + ([word] if word else [])).casefold().strip()
            replace_length = len(before) - len(" ".join(prefix[:argument_index])) - int(not trailing_space)
            for item in cached_apps():
                name = item.get("name", "")
                if name.casefold().startswith(name_prefix):
                    yield Completion(name, start_position=-replace_length)
            return
        if command in {"play", "findgame", "gameinfo", "gamefolder", "stopgame", "favoritegame"}:
            from core.games import cached_games
            argument_index = 2 if command == "favoritegame" and len(prefix) >= 2 and prefix[1].casefold() == "add" else 1
            name_prefix = " ".join(prefix[argument_index:] + ([word] if word else [])).casefold().strip()
            replace_length = len(before) - len(" ".join(prefix[:argument_index])) - int(not trailing_space)
            for item in cached_games():
                name = item.get("name", "")
                if name.casefold().startswith(name_prefix):
                    yield Completion(name, start_position=-replace_length)
            return
        if command == "workspace" and len(prefix) >= 2 and prefix[1].casefold() in {"run", "info", "remove"}:
            from core.workspaces import list_workspaces
            for name in list_workspaces():
                name_prefix = " ".join(prefix[2:] + ([word] if word else [])).casefold().strip()
                replace_length = len(before) - len("workspace " + prefix[1]) - 1 + int(trailing_space)
                if name.casefold().startswith(name_prefix):
                    yield Completion(name, start_position=-replace_length)
            return
        if command == "workspace" and len(prefix) >= 2 and prefix[1].casefold() in {"addfolder", "addapp", "addgame", "addurl"} and len(prefix) == 2:
            from core.workspaces import list_workspaces
            for name in list_workspaces():
                if name.casefold().startswith(word.casefold()):
                    yield Completion(name, start_position=-len(word))
            return
        if command == "workspace" and len(prefix) >= 3 and prefix[1].casefold() == "addfolder":
            yield from self._path_completions(word)
            return
        if command == "workspace" and len(prefix) >= 2 and prefix[1].casefold() in {"addapp", "addgame"}:
            if len(prefix) == 2:
                from core.workspaces import list_workspaces
                for name in list_workspaces():
                    if name.casefold().startswith(word.casefold()):
                        yield Completion(name, start_position=-len(word))
                return
            base = " ".join(prefix[:3]) + " "
            argument_text = before[len(base):] if before.startswith(base) else word
            name_prefix = argument_text.strip().casefold()
            replace_length = len(argument_text)
            catalog = ("core.apps", "cached_apps") if prefix[1].casefold() == "addapp" else ("core.games", "cached_games")
            module = __import__(catalog[0], fromlist=[catalog[1]])
            for item in getattr(module, catalog[1])():
                name = item.get("name", "")
                if name.casefold().startswith(name_prefix):
                    yield Completion(name, start_position=-replace_length)
            return
        if command == "config" and len(prefix) == 1:
            for option in ("show", "prompt", "language", "translate-url"):
                if option.startswith(word.casefold()):
                    yield Completion(option, start_position=-len(word))
            return
        if command == "music" and len(prefix) == 1:
            for option in ("list", "setfolder"):
                if option.startswith(word.casefold()):
                    yield Completion(option, start_position=-len(word))
            return
        path_commands = {"cd", "ls", "cat", "touch", "mkdir", "cp", "mv", "rm", "tree", "find", "grep", "head", "tail", "wc", "du", "hash", "zip", "unzip", "edit", "backup", "restore", "findfile", "findfolder", "openfile", "reveal", "largestfiles", "duplicates", "emptyfolders"}
        if command in path_commands:
            if command == "find" and len(prefix) == 1:
                return
            if command == "grep" and len(prefix) == 1:
                return
            yield from self._path_completions(word)
            return
        if command == "app" and len(prefix) >= 2 and prefix[1].casefold() in {"run", "info", "remove"}:
            from core.apps import cached_apps, list_apps
            names = set(list_apps()) | {item.get("name", "") for item in cached_apps()}
            for name in names:
                if name.casefold().startswith(word.casefold()):
                    yield Completion(name, start_position=-len(word))
            return
        if command == "app" and len(prefix) >= 2 and prefix[1].casefold() == "add" and len(prefix) >= 3:
            yield from self._path_completions(word)
            return
        if command == "music" and len(prefix) >= 2 and prefix[1].casefold() == "setfolder":
            yield from self._path_completions(word)
            return
        if command == "video" and len(prefix) >= 2 and prefix[1].casefold() == "setfolder":
            yield from self._path_completions(word)
            return
        if command == "video" and len(prefix) >= 2 and prefix[1].casefold() == "info":
            yield from self._path_completions(word)

    def _path_completions(self, fragment: str) -> Iterable[Completion]:
        from core.filesystem import resolve_path
        raw = fragment.strip('"')
        current = self._cwd_provider()
        candidate = resolve_path(current, raw or ".")
        directory_prefix = not raw or raw.endswith(("/", "\\"))
        parent = candidate if directory_prefix else candidate.parent
        stem = "" if directory_prefix else candidate.name
        try:
            for entry in parent.iterdir():
                if entry.name.casefold().startswith(stem.casefold()):
                    parent_fragment = str(Path(raw).parent)
                    result = str(Path(raw).parent / entry.name) if parent_fragment != "." else entry.name
                    if entry.is_dir():
                        result += os.sep
                    yield Completion(result, start_position=-len(fragment))
        except (PermissionError, OSError):
            return


class CleyxLexer(RegexLexer):
    name = "CleyxOS"
    tokens = {
        "root": [
            (r"\s+", Text),
            (r"#[^\n]*", Comment),
            (r"(?:'[^']*'|\"[^\"]*\")", String),
            (r"\b(?:help|clear|sysinfo|neofetch|uptime|processes|performance|exit|ls|cd|pwd|mkdir|touch|cat|cp|mv|rm|time|date|calc|history|echo|ping|weather|open|language|apps|app|config|whoami|hostname|disk|ram|cpu|gpu|battery|top|env|which|kill|tree|find|grep|head|tail|wc|du|df|hash|zip|unzip|edit|backup|restore|ip|publicip|dns|http|download|netstat|speedtest|todo|note|timer|stopwatch|remind|alias|matrix|cleyx)\b", Keyword),
            (r"\b(?:launch|openapp|searchapp|installed|appinfo|appfolder|closeapp|recentapps|favoriteapp|play|games|findgame|gameinfo|gamefolder|recentgames|stopgame|favoritegame|registergame|watch|videos|findvideo|video|music|playmedia|youtube|spotify|volume|mute|unmute|brightness|screenshot|clipboard|lock|sleep|shutdown|restart|settings|taskmanager|controlpanel|startupapps|findfile|findfolder|openfile|reveal|downloads|desktop|documents|pictures|videosfolder|musicfolder|recentfiles|largestfiles|duplicates|emptyfolders|cleanup|quicknote|quicknotes|calendar|convert|passwordgen|uuid|random|qr|focus|pomodoro|dictionary|translate|workspace|tutorial|examples|commands|searchcommand|whatsnew|tips|shortcuts|doctor|version|updatecheck|searchpath)\b", Keyword),
            (r"\b\d+(?:\.\d+)?\b", Number),
            (r"[+*/%=<>!-]+", Operator),
            (r"[A-Za-z_][\w.-]*", Name),
            (r".", Text),
        ]
    }


PROMPT_STYLE = Style.from_dict({
    "prompt": "bold #00ffff",
    "completion-menu.completion": "bg:#111111 #ffffff",
    "completion-menu.completion.current": "bg:#00aaaa #000000",
    "scrollbar.background": "bg:#222222",
    "scrollbar.button": "bg:#00aaaa",
})


class Shell:
    """Own the interactive shell's current directory and lifecycle."""

    def __init__(self, cwd: Path | None = None) -> None:
        ensure_app_dir()
        self.cwd = (cwd or Path.cwd()).resolve()
        self.restart_requested = False
        self._pending_notifications: queue.SimpleQueue[str] = queue.SimpleQueue()
        self.reminders = ReminderScheduler(self._notify_reminder)
        self.history = FileHistory(str(HISTORY_FILE))
        self.session: PromptSession[str] = PromptSession(
            history=self.history,
            completer=CleyxCompleter(lambda: self.cwd),
            lexer=PygmentsLexer(CleyxLexer),
            style=PROMPT_STYLE,
            complete_while_typing=True,
            # Keep Up/Down as predictable sequential history navigation.
            # Prefix-search mode can unexpectedly replace fresh input with an
            # older command while the user is typing, leading to accidental reruns.
            enable_history_search=False,
        )
        self.processor = CommandProcessor(self)
        threading.Thread(target=self._warm_completion_catalogs, name="cleyxos-catalog-cache", daemon=True).start()

    def prompt_text(self) -> str:
        template = str(get_config().get("prompt", "root@cleyxos:~$"))
        return template.replace("{cwd}", str(self.cwd)).replace("{home}", str(Path.home()))

    def run(self) -> None:
        console.print(f"[dim]{translate('welcome')}[/dim]")
        while True:
            self._flush_notifications()
            try:
                raw = self.session.prompt(
                    [("class:prompt", escape(self.prompt_text()) + " ")],
                    refresh_interval=0,
                )
            except KeyboardInterrupt:
                console.print(f"\n[dim]{translate('interrupted')}[/dim]")
                continue
            except EOFError:
                console.print(f"\n[bold red]{translate('shutdown')}[/bold red]")
                break
            if not self.processor.execute(raw):
                if self.restart_requested:
                    self.restart_requested = False
                    self.processor = CommandProcessor(self)
                    console.print(f"[dim]{translate('welcome')}[/dim]")
                    continue
                break
        self.reminders.cancel_all()

    @staticmethod
    def _warm_completion_catalogs() -> None:
        try:
            from core.apps import discover_apps
            from core.games import discover_games
            discover_apps()
            discover_games()
        except (OSError, ValueError):
            return

    def _notify_reminder(self, message: str) -> None:
        """Avoid writing directly from timer threads while prompt_toolkit owns the terminal."""
        app = self.session.app
        if not app.is_running:
            self._pending_notifications.put(message)
            return

        def print_notification() -> None:
            console.print(f"\n[bold yellow]Reminder:[/bold yellow] {message}")

        app.loop.call_soon_threadsafe(lambda: run_in_terminal(print_notification))

    def _flush_notifications(self) -> None:
        while not self._pending_notifications.empty():
            message = self._pending_notifications.get()
            console.print(f"[bold yellow]Reminder:[/bold yellow] {message}")