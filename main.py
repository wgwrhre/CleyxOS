"""Entry point for the CleyxOS terminal simulation."""

from __future__ import annotations

import os
import sys
import time

from rich.align import Align
from rich.panel import Panel
from rich.text import Text

from core.config import APP_DIR
from core.shell import Shell
from utils.terminal import console


LOGO = r"""
██████╗██╗     ███████╗██╗   ██╗██╗  ██╗
██╔════╝██║     ██╔════╝╚██╗ ██╔╝╚██╗██╔╝
██║     ██║     █████╗   ╚████╔╝  ╚███╔╝
██║     ██║     ██╔══╝    ╚██╔╝   ██╔██╗
╚██████╗███████╗███████╗   ██║   ██╔╝ ██╗
 ╚═════╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝

       C L E Y X O S
    TERMINAL EDITION v2.0

       MAY THE LAZY GET LAZIER.
"""


def boot(*, animate: bool = True) -> None:
    """Display the startup sequence and CleyxOS branding."""
    messages = (
        "[CLEYXOS] Initializing kernel simulation...",
        "[CLEYXOS] Loading modules...",
        "[CLEYXOS] Checking system integrity...",
        "[CLEYXOS] Starting command interface...",
    )
    for message in messages:
        console.print(message, style="bold cyan")
        if animate:
            time.sleep(0.18)
    console.print(Panel(Align.center(Text(LOGO.strip("\n"), style="bold white")),
                        border_style="cyan", padding=(1, 2)))
    console.print(f"[dim]Configuration: {APP_DIR}[/dim]\n")


def main() -> int:
    """Start the interactive shell."""
    boot(animate=not bool(os.environ.get("CLEYXOS_NO_ANIMATION")))
    try:
        Shell().run()
    except KeyboardInterrupt:
        console.print("\n[bold red]CleyxOS interrupted.[/bold red]")
    return 0


if __name__ == "__main__":
    sys.exit(main())