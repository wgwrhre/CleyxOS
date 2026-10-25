"""Interactive prompt-toolkit shell with persistent history and completion."""

from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Callable, Iterable

from prompt_toolkit import PromptSession
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
            for candidate in sorted(COMMANDS):
                if candidate.casefold().startswith(word.casefold()):
                    yield Completion(candidate, start_position=-len(word))
            return

        command = prefix[0].casefold()
        subcommands = {
            "app": ("add", "run", "remove", "info"),
            "config": ("show", "prompt", "language"),
            "todo": ("add", "list", "done", "remove", "clear"),
            "note": ("add", "list", "read", "remove", "search"),
            "alias": ("add", "list", "remove"),
        }
        if command in subcommands and len(prefix) == 1:
            for option in subcommands[command]:
                if option.startswith(word.casefold()):
                    yield Completion(option, start_position=-len(word))
            return
        path_commands = {"cd", "ls", "cat", "touch", "mkdir", "cp", "mv", "rm", "tree", "find", "grep", "head", "tail", "wc", "du", "hash", "zip", "unzip", "edit", "backup", "restore"}
        if command in path_commands:
            if command == "find" and len(prefix) == 1:
                return
            if command == "grep" and len(prefix) == 1:
                return
            yield from self._path_completions(word)
            return
        if command == "app" and len(prefix) >= 2 and prefix[1].casefold() in {"run", "info", "remove"}:
            # Only the persistent registry is queried here; Windows discovery can be slow.
            from core.apps import list_apps
            for name in list_apps():
                if name.casefold().startswith(word.casefold()):
                    yield Completion(name, start_position=-len(word))

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

    def prompt_text(self) -> str:
        template = str(get_config().get("prompt", "root@cleyxos:~$"))
        return template.replace("{cwd}", str(self.cwd)).replace("{home}", str(Path.home()))

    def run(self) -> None:
        console.print(f"[dim]{translate('welcome')}[/dim]")
        while True:
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
    def _notify_reminder(message: str) -> None:
        console.print(f"\n[bold yellow]⏰ Reminder:[/bold yellow] {message}")