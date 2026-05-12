from __future__ import annotations

import time
from datetime import datetime

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from .codex_app import CodexApp
from .config import Config
from .limits import LimitReader
from .models import LimitSnapshot, LimitWindow, Session
from .storage import SessionStore


class CodexSwitcherTui:
    def __init__(self, config: Config | None = None, console: Console | None = None) -> None:
        self.config = config or Config.load()
        self.console = console or Console()
        self.store = SessionStore(self.config)
        self.codex_app = CodexApp(self.config)
        self.limit_reader = LimitReader(self.config)
        self.snapshots = self.store.load_cache()

    def run(self) -> None:
        self.store.ensure()

        while True:
            sessions = self.store.list_sessions()
            self._render(sessions)
            choice = Prompt.ask(
                "Action",
                choices=["s", "a", "c", "r", "R", "q"],
                default="s",
                show_choices=False,
            )

            if choice == "q":
                return
            if choice == "s":
                self._switch(sessions)
            elif choice == "a":
                self._prepare_login()
            elif choice == "c":
                self._capture_current()
            elif choice == "r":
                self._refresh_next(sessions)
            elif choice == "R":
                self._refresh_all_slowly(sessions)

    def _render(self, sessions: list[Session]) -> None:
        self.console.clear()
        self.console.print(Panel.fit("[bold]Codex Switcher[/bold]  [dim]for Codex.app auth.json[/dim]"))

        if not sessions:
            self.console.print("[yellow]No saved sessions yet.[/yellow]")
            self.console.print(f"[dim]Session directory: {self.config.sessions_dir}[/dim]")
        else:
            table = Table(show_header=True, header_style="bold")
            table.add_column("#", justify="right", style="dim")
            table.add_column("Account")
            table.add_column("Category")
            table.add_column("Active", justify="center")
            table.add_column("5h limit")
            table.add_column("Weekly limit")
            table.add_column("Updated")

            for index, session in enumerate(sessions, start=1):
                snapshot = self.snapshots.get(self.store.cache_key(session))
                table.add_row(
                    str(index),
                    session.email,
                    session.display_category,
                    "[green]yes[/green]" if session.active else "",
                    format_window(pick_window(snapshot, 300), snapshot),
                    format_window(pick_window(snapshot, 10080), snapshot),
                    format_fetched(snapshot),
                )
            self.console.print(table)

        self.console.print()
        self.console.print(
            Align.left(
                Text.from_markup(
                    "[bold]s[/bold] switch  "
                    "[bold]a[/bold] add/login  "
                    "[bold]c[/bold] capture current  "
                    "[bold]r[/bold] refresh next  "
                    "[bold]R[/bold] refresh all slowly  "
                    "[bold]q[/bold] quit"
                )
            )
        )

    def _switch(self, sessions: list[Session]) -> None:
        session = self._pick_session(sessions)
        if session is None:
            return

        self.console.print(f"Switching to [bold]{session.email}[/bold]...")
        self.codex_app.switch_to(session)
        self.console.print("[green]Done.[/green] Codex.app was closed; open it again when ready.")
        self._pause()

    def _prepare_login(self) -> None:
        self.console.print("This closes Codex.app and removes the active auth.json. Do not use logout inside Codex.")
        if not Confirm.ask("Prepare a clean login?", default=True):
            return
        self.codex_app.prepare_login()
        if Confirm.ask("Open Codex.app now for login?", default=True):
            self.codex_app.open()
        self.console.print("[green]Ready.[/green] After login, choose [bold]c[/bold] to capture the new session.")
        self._pause()

    def _capture_current(self) -> None:
        email = Prompt.ask("Email / session name").strip()
        category = Prompt.ask("Category folder", default="").strip()
        try:
            destination = self.store.destination_for(email, category)
            self.codex_app.save_current_auth(destination)
        except Exception as exc:
            self.console.print(f"[red]Could not save session:[/red] {exc}")
        else:
            self.console.print(f"[green]Saved:[/green] {destination}")
        self._pause()

    def _refresh_next(self, sessions: list[Session]) -> None:
        session = self._next_stale_session(sessions)
        if session is None:
            self.console.print("[yellow]No sessions to refresh.[/yellow]")
            self._pause()
            return
        self._refresh_one(session)
        self._pause()

    def _refresh_all_slowly(self, sessions: list[Session]) -> None:
        if not sessions:
            self.console.print("[yellow]No sessions to refresh.[/yellow]")
            self._pause()
            return
        delay = IntPrompt.ask("Delay between accounts, seconds", default=self.config.refresh_delay_seconds)
        for index, session in enumerate(sessions, start=1):
            self._refresh_one(session, preserve_cache_on_error=True)
            if index < len(sessions):
                self.console.print(f"[dim]Waiting {delay}s before next account...[/dim]")
                time.sleep(max(0, delay))
        self._pause()

    def _refresh_one(self, session: Session, preserve_cache_on_error: bool = False) -> None:
        self.console.print(f"Reading limits for [bold]{session.email}[/bold] ({session.display_category})...")
        snapshot = self.limit_reader.read(session)
        cache_key = self.store.cache_key(session)
        if snapshot.error and preserve_cache_on_error and cache_key in self.snapshots:
            self.console.print(f"[yellow]Limit read failed; keeping cached value:[/yellow] {snapshot.error}")
            return

        self.snapshots[cache_key] = snapshot
        self.store.save_cache(self.snapshots)
        if snapshot.error:
            self.console.print(f"[red]Limit read failed:[/red] {snapshot.error}")
        else:
            self.console.print("[green]Limits updated.[/green]")

    def _next_stale_session(self, sessions: list[Session]) -> Session | None:
        if not sessions:
            return None
        return min(
            sessions,
            key=lambda session: self.snapshots.get(self.store.cache_key(session)).fetched_at
            if self.snapshots.get(self.store.cache_key(session))
            else 0,
        )

    def _pick_session(self, sessions: list[Session]) -> Session | None:
        if not sessions:
            self.console.print("[yellow]No saved sessions yet.[/yellow]")
            self._pause()
            return None
        index = IntPrompt.ask("Session number", default=1)
        if index < 1 or index > len(sessions):
            self.console.print("[red]Invalid session number.[/red]")
            self._pause()
            return None
        return sessions[index - 1]

    def _pause(self) -> None:
        Prompt.ask("Press Enter", default="", show_default=False)


def pick_window(snapshot: LimitSnapshot | None, duration_mins: int) -> LimitWindow | None:
    if snapshot is None:
        return None
    for window in (snapshot.primary, snapshot.secondary):
        if window and window.window_duration_mins == duration_mins:
            return window
    if duration_mins == 300:
        return snapshot.primary
    if duration_mins == 10080:
        return snapshot.secondary
    return None


def format_window(window: LimitWindow | None, snapshot: LimitSnapshot | None) -> str:
    if snapshot and snapshot.error:
        return "[red]error[/red]"
    if window is None:
        return "[dim]not loaded[/dim]"

    if window.used_percent is None:
        percent = "?"
    else:
        percent = f"{max(0, 100 - window.used_percent):.0f}% left"
    reset = format_reset(window.resets_at)
    return f"{percent} [dim]{reset}[/dim]"


def format_reset(resets_at: int | None) -> str:
    if not resets_at:
        return "reset unknown"
    value = datetime.fromtimestamp(resets_at)
    return f"resets {value:%b %d %H:%M}"


def format_fetched(snapshot: LimitSnapshot | None) -> str:
    if snapshot is None:
        return "[dim]never[/dim]"
    value = datetime.fromtimestamp(snapshot.fetched_at)
    return value.strftime("%b %d %H:%M")
