from __future__ import annotations

from rich.console import Console

from .tui import CodexSwitcherTui


def main() -> None:
    console = Console()
    try:
        CodexSwitcherTui(console=console).run()
    except (EOFError, KeyboardInterrupt):
        console.print()
        console.print("[yellow]Interrupted.[/yellow]")
    except Exception as exc:
        console.print(f"[red]error:[/red] {exc}")
