"""Shared Rich console and prompt-toolkit presentation helpers."""

from rich.console import Console
from rich.theme import Theme

THEME = Theme({
    "info": "cyan",
    "success": "bold cyan",
    "warning": "bold yellow",
    "error": "bold red",
})
console = Console(theme=THEME, highlight=False)