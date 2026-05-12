from __future__ import annotations

from .cli import tui as _tui
from .cli.tui import (
    CodexSwitcherTui,
    format_fetched,
    format_reset,
    format_window,
    pick_window,
)

IntPrompt = _tui.IntPrompt
time = _tui.time

__all__ = [
    "CodexSwitcherTui",
    "IntPrompt",
    "format_fetched",
    "format_reset",
    "format_window",
    "pick_window",
    "time",
]
